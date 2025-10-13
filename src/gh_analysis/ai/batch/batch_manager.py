"""Core batch job management for AI processing."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from .config_compat import AIModelConfig, build_ai_config
from .models import (
    BatchJob,
    BatchJobError,
    BatchJobSummary,
    BatchResult,
)
from .openai_provider import OpenAIBatchProvider

console = Console()


class BatchManager:
    """Manages AI batch processing jobs."""

    def __init__(self, base_path: str = "data/batch"):
        """Initialize batch manager.

        Args:
            base_path: Base directory for storing batch job data
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.base_path / "jobs").mkdir(exist_ok=True)
        (self.base_path / "input").mkdir(exist_ok=True)
        (self.base_path / "output").mkdir(exist_ok=True)

    def find_issues(
        self,
        org: str | None = None,
        repo: str | None = None,
        issue_number: int | None = None,
    ) -> list[dict[str, Any]]:
        """Find issue files matching the criteria.

        Args:
            org: GitHub organization name (optional)
            repo: GitHub repository name (optional)
            issue_number: Specific issue number (optional)

        Returns:
            List of issue data dictionaries
        """
        # Validate argument combinations first
        if issue_number and (not org or not repo):
            raise ValueError("org and repo are required when specifying issue_number")

        data_dir = Path("data/issues")
        if not data_dir.exists():
            return []

        issue_files = []

        if issue_number:
            # Find specific issue file

            expected_filename = f"{org}_{repo}_issue_{issue_number}.json"
            expected_path = data_dir / expected_filename

            if expected_path.exists():
                issue_files = [expected_path]
        elif org and repo:
            # Process all issues for specific org/repo
            pattern = f"{org}_{repo}_issue_*.json"
            issue_files = list(data_dir.glob(pattern))
        elif org:
            # Process all issues for specific org (across all repos)
            pattern = f"{org}_*_issue_*.json"
            issue_files = list(data_dir.glob(pattern))
        else:
            # Process all issues
            issue_files = list(data_dir.glob("*_issue_*.json"))

        # Load and return issue data
        issues = []
        for file_path in issue_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    issue_data = json.load(f)
                    issues.append(issue_data)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to load {file_path}: {e}[/yellow]"
                )
                continue

        return issues

    async def create_batch_job(
        self,
        processor_type: str,
        org: str | None = None,
        repo: str | None = None,
        issue_number: int | None = None,
        model_config: AIModelConfig | dict[str, Any] | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> BatchJob:
        """Create batch job using standard filtering options or pre-filtered issues.

        Args:
            processor_type: Type of processor (e.g., 'product-labeling')
            org: GitHub organization name (optional)
            repo: GitHub repository name (optional)
            issue_number: Specific issue number (optional)
            model_config: AI model configuration
            issues: Pre-filtered list of issues (optional)

        Returns:
            Created batch job
        """
        # Handle both old AIModelConfig and new simplified config format
        if model_config is None:
            model_config = build_ai_config()
        elif isinstance(model_config, dict):
            # Convert new simplified config to AIModelConfig
            config_dict = model_config  # Save reference before overwriting
            model_config = build_ai_config(
                model_name=config_dict.get("model", "openai:gpt-4o"),
                thinking_effort=config_dict.get("thinking_effort"),
                thinking_budget=config_dict.get("thinking_budget"),
                temperature=config_dict.get("temperature", 0.0),
            )
            # Note: retry_count is handled at the agent level, not in AIModelConfig
            # Set additional properties
            model_config.include_images = config_dict.get("include_images", True)

        # Use provided issues or find them
        if issues is None:
            issues = self.find_issues(org, repo, issue_number)

        if not issues:
            if issue_number:
                raise ValueError(f"Issue #{issue_number} not found for {org}/{repo}")
            elif org and repo:
                raise ValueError(f"No issues found for {org}/{repo}")
            elif org:
                raise ValueError(f"No issues found for organization {org}")
            else:
                raise ValueError("No issues found to process")

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Create batch job
        batch_job = BatchJob(
            job_id=job_id,
            processor_type=processor_type,
            org=org or "",
            repo=repo,
            issue_number=issue_number,
            ai_model_config=model_config.model_dump(),
            total_items=len(issues),
            openai_batch_id=None,
            input_file_id=None,
            output_file_id=None,
            submitted_at=None,
            completed_at=None,
            processed_items=0,
            failed_items=0,
            input_file_path=None,
            output_file_path=None,
        )

        # Save job metadata
        job_file = self.base_path / "jobs" / f"{job_id}.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(batch_job.model_dump(), f, indent=2, default=str)

        console.print(f"Created batch job {job_id} with {len(issues)} issues")

        # Create JSONL input file
        provider = OpenAIBatchProvider(model_config)
        input_file = self.base_path / "input" / f"{job_id}.jsonl"

        provider.create_jsonl_file(issues, processor_type, input_file)
        batch_job.input_file_path = str(input_file)

        # Upload to OpenAI and submit batch
        try:
            input_file_id = await provider.upload_file(input_file)
            batch_job.input_file_id = input_file_id

            openai_batch_id = await provider.submit_batch(input_file_id)
            batch_job.openai_batch_id = openai_batch_id
            batch_job.status = "validating"
            batch_job.submitted_at = datetime.utcnow()

            # Update job file
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(batch_job.model_dump(), f, indent=2, default=str)

            console.print(f"Submitted to OpenAI: {openai_batch_id}")

        except Exception as e:
            batch_job.status = "failed"
            batch_job.errors = [
                BatchJobError(
                    custom_id="job_submission",
                    error_code="submission_failed",
                    error_message=str(e),
                )
            ]

            # Update job file with error
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(batch_job.model_dump(), f, indent=2, default=str)

            console.print(f"[red]Failed to submit batch job: {e}[/red]")
            raise

        return batch_job

    async def check_job_status(self, job_id: str) -> BatchJob:
        """Check status of batch job.

        Args:
            job_id: Full or partial batch job identifier

        Returns:
            Updated batch job
        """
        # Resolve partial ID to full ID
        full_job_id = self.resolve_job_id(job_id)
        job_file = self.base_path / "jobs" / f"{full_job_id}.json"

        # Load current job state
        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)
            batch_job = BatchJob.model_validate(job_data)

        if not batch_job.openai_batch_id:
            return batch_job

        # Check status with OpenAI
        try:
            model_config = AIModelConfig.model_validate(batch_job.ai_model_config)
            provider = OpenAIBatchProvider(model_config)

            status_data = await provider.get_batch_status(batch_job.openai_batch_id)

            # Store OpenAI's actual status string (no mapping needed)
            openai_status = status_data["status"]
            batch_job.status = openai_status

            # Set completion time and output file when completed
            if openai_status == "completed":
                batch_job.completed_at = datetime.utcnow()
                batch_job.output_file_id = status_data.get("output_file_id")

            # Update counts from OpenAI response for all active statuses
            if openai_status in ["in_progress", "finalizing", "completed"]:
                request_counts = status_data.get("request_counts", {})
                batch_job.processed_items = request_counts.get("completed", 0)
                batch_job.failed_items = request_counts.get("failed", 0)

            # Handle failed status
            if openai_status == "failed":
                # Add error information if available
                if "errors" in status_data:
                    for error in status_data["errors"]:
                        batch_job.errors.append(
                            BatchJobError(
                                custom_id="batch_execution",
                                error_code=error.get("code", "unknown"),
                                error_message=error.get(
                                    "message", "Batch execution failed"
                                ),
                            )
                        )
            elif openai_status == "cancelled":
                batch_job.status = "cancelled"

            # Save updated job state
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(batch_job.model_dump(), f, indent=2, default=str)

        except Exception as e:
            console.print(
                f"[yellow]Warning: Failed to check batch status: {e}[/yellow]"
            )

        return batch_job

    async def collect_results(self, job_id: str) -> BatchResult:
        """Download and process batch results.

        Args:
            job_id: Full or partial batch job identifier

        Returns:
            Batch results with processing summary
        """
        # Check job status first
        batch_job = await self.check_job_status(job_id)

        if batch_job.status != "completed":
            raise ValueError(
                f"Job {job_id} is not completed (status: {batch_job.status})"
            )

        if not batch_job.output_file_id:
            raise ValueError(f"Job {job_id} has no output file")

        # Download results from OpenAI
        model_config = AIModelConfig.model_validate(batch_job.ai_model_config)
        provider = OpenAIBatchProvider(model_config)

        output_file = self.base_path / "output" / f"{job_id}_results.jsonl"
        await provider.download_results(batch_job.output_file_id, output_file)

        batch_job.output_file_path = str(output_file)

        # Parse and process results
        results = provider.parse_batch_results(output_file)

        # Create results directory
        results_dir = Path("data/results")
        results_dir.mkdir(exist_ok=True)

        successful_items = 0
        failed_items = 0
        errors = []

        for result in results:
            custom_id = result["custom_id"]

            if result.get("error"):
                # Handle failed item
                failed_items += 1
                error = result["error"]
                errors.append(
                    BatchJobError(
                        custom_id=custom_id,
                        error_code=error.get("code", "unknown"),
                        error_message=error.get("message", "Processing failed"),
                    )
                )
                continue

            # Process successful result
            response = result.get("response", {})
            # OpenAI Batch API wraps the response in a 'body' field
            body = response.get("body", response)
            choices = body.get("choices", [])

            if not choices:
                failed_items += 1
                errors.append(
                    BatchJobError(
                        custom_id=custom_id,
                        error_code="no_choices",
                        error_message="No response choices in result",
                    )
                )
                continue

            try:
                # Parse the AI response
                content = choices[0]["message"]["content"]
                analysis = json.loads(content)

                # Extract org, repo, issue number from custom_id
                parts = custom_id.split("_")
                if len(parts) < 4 or parts[-2] != "issue":
                    failed_items += 1
                    errors.append(
                        BatchJobError(
                            custom_id=custom_id,
                            error_code="invalid_custom_id",
                            error_message=f"Invalid custom_id format: {custom_id}",
                        )
                    )
                    continue

                issue_number = parts[-1]
                repo = "_".join(parts[1:-2])
                org = parts[0]

                # Create result file
                result_file = results_dir / (
                    f"{custom_id}_{batch_job.processor_type}.json"
                )

                # Construct file_path to match regular processing format
                file_path = f"data/issues/{org}_{repo}_issue_{issue_number}.json"

                result_data = {
                    "issue_reference": {
                        "file_path": file_path,
                        "batch_job_id": job_id,
                        "org": org,
                        "repo": repo,
                        "issue_number": int(issue_number),
                    },
                    "processor": {
                        "name": batch_job.processor_type,
                        "version": "2.1.0",
                        "model": model_config.model_name,
                        "include_images": model_config.include_images,
                        "batch_processing": True,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    },
                    "analysis": analysis,
                }

                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(result_data, f, indent=2)

                successful_items += 1
                console.print(f"[green]✓ Saved result: {result_file.name}[/green]")

            except Exception as e:
                failed_items += 1
                errors.append(
                    BatchJobError(
                        custom_id=custom_id,
                        error_code="result_processing_failed",
                        error_message=f"Failed to process result: {e}",
                    )
                )
                console.print(
                    f"[red]✗ Failed to process result for {custom_id}: {e}[/red]"
                )

        # Update batch job with final counts
        batch_job.processed_items = successful_items
        batch_job.failed_items = failed_items
        batch_job.errors.extend(errors)

        # Save updated job
        job_file = self.base_path / "jobs" / f"{batch_job.job_id}.json"
        with open(job_file, "w", encoding="utf-8") as f:
            json.dump(batch_job.model_dump(), f, indent=2, default=str)

        # Calculate processing time
        processing_time = None
        if batch_job.submitted_at and batch_job.completed_at:
            delta = batch_job.completed_at - batch_job.submitted_at
            processing_time = delta.total_seconds()

        return BatchResult(
            job_id=job_id,
            processor_type=batch_job.processor_type,
            total_items=batch_job.total_items,
            successful_items=successful_items,
            failed_items=failed_items,
            cost_estimate=None,  # TODO: Calculate based on token usage
            processing_time=processing_time,
            results_directory=str(results_dir),
            errors=errors,
        )

    async def list_jobs(self) -> list[BatchJobSummary]:
        """List all batch jobs with real-time status updates.

        Returns:
            List of batch job summaries with current progress
        """
        jobs_dir = self.base_path / "jobs"
        job_files = list(jobs_dir.glob("*.json"))

        summaries = []
        for job_file in job_files:
            try:
                with open(job_file, encoding="utf-8") as f:
                    job_data = json.load(f)
                    batch_job = BatchJob.model_validate(job_data)

                # Auto-refresh status for active jobs to show real-time progress
                if batch_job.status in ["validating", "in_progress", "finalizing"]:
                    try:
                        batch_job = await self.check_job_status(batch_job.job_id)
                    except Exception as e:
                        console.print(
                            f"[yellow]Warning: Failed to refresh status for "
                            f"{batch_job.job_id}: {e}[/yellow]"
                        )

                summaries.append(
                    BatchJobSummary(
                        job_id=batch_job.job_id,
                        processor_type=batch_job.processor_type,
                        org=batch_job.org,
                        repo=batch_job.repo,
                        issue_number=batch_job.issue_number,
                        status=batch_job.status,
                        created_at=batch_job.created_at,
                        total_items=batch_job.total_items,
                        processed_items=batch_job.processed_items,
                        failed_items=batch_job.failed_items,
                    )
                )
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to load job {job_file}: {e}[/yellow]"
                )
                continue

        # Sort by creation time (newest first)
        summaries.sort(key=lambda x: x.created_at, reverse=True)
        return summaries

    async def cancel_job(self, job_id: str) -> BatchJob:
        """Cancel a batch job.

        Args:
            job_id: Full or partial batch job ID

        Returns:
            Updated batch job with cancelled status

        Raises:
            ValueError: If job cannot be cancelled
        """
        # Resolve partial ID to full ID
        full_job_id = self.resolve_job_id(job_id)
        job_file = self.base_path / "jobs" / f"{full_job_id}.json"

        # Load current job state
        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)
            batch_job = BatchJob.model_validate(job_data)

        # Check if job can be cancelled
        cancellable_states = [
            "pending",
            "validating",
            "in_progress",
            "finalizing",
            "cancelling",
        ]
        if batch_job.status not in cancellable_states:
            if batch_job.status == "cancelled":
                console.print(f"[yellow]Job {job_id} is already cancelled[/yellow]")
                return batch_job
            elif batch_job.status == "completed":
                console.print(f"[yellow]Job {job_id} has already completed[/yellow]")
                return batch_job
            elif batch_job.status == "failed":
                console.print(f"[yellow]Job {job_id} has already failed[/yellow]")
                return batch_job
            else:
                raise ValueError(
                    f"Job {job_id} cannot be cancelled (status: {batch_job.status})"
                )

        if not batch_job.openai_batch_id:
            raise ValueError(f"Job {job_id} has no OpenAI batch ID to cancel")

        try:
            # Cancel the batch with OpenAI
            model_config = AIModelConfig.model_validate(batch_job.ai_model_config)
            provider = OpenAIBatchProvider(model_config)

            await provider.cancel_batch(batch_job.openai_batch_id)

            # Update local job status
            batch_job.status = "cancelled"

            # Save updated job state
            with open(job_file, "w", encoding="utf-8") as f:
                json.dump(batch_job.model_dump(), f, indent=2, default=str)

            console.print(f"[green]✓ Cancelled batch job {job_id}[/green]")

        except Exception as e:
            console.print(f"[red]Failed to cancel batch job: {e}[/red]")
            raise

        return batch_job

    def remove_job(self, job_id: str, force: bool = False) -> bool:
        """Remove a batch job record.

        Args:
            job_id: Full or partial batch job ID
            force: Skip confirmation prompt

        Returns:
            True if job was removed, False if cancelled by user

        Raises:
            ValueError: If job doesn't exist
        """
        # Resolve partial ID to full ID
        full_job_id = self.resolve_job_id(job_id)
        job_file = self.base_path / "jobs" / f"{full_job_id}.json"

        # Load job to get details for confirmation and cleanup
        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)
            batch_job = BatchJob.model_validate(job_data)

        # Warn if job is still active
        active_states = [
            "pending",
            "validating",
            "in_progress",
            "finalizing",
            "cancelling",
        ]
        if batch_job.status in active_states:
            console.print(
                f"[yellow]Warning: Job {job_id} is still active "
                f"(status: {batch_job.status})[/yellow]"
            )
            console.print(
                "[yellow]Consider cancelling it first before removing.[/yellow]"
            )
            if not force:
                confirmation = (
                    input("Remove active job anyway? [y/N]: ").strip().lower()
                )
                if confirmation not in ["y", "yes"]:
                    console.print("[yellow]Job removal cancelled[/yellow]")
                    return False
            else:
                console.print(
                    "[yellow]--force flag used: proceeding with removal "
                    "of active job[/yellow]"
                )

        # Ask for confirmation unless force is used
        if not force:
            console.print("[yellow]About to remove batch job:[/yellow]")
            console.print(f"  Job ID: {job_id}")
            console.print(f"  Processor: {batch_job.processor_type}")
            console.print(f"  Status: {batch_job.status}")
            console.print(f"  Created: {batch_job.created_at}")

            confirmation = (
                input("Are you sure you want to remove this job? [y/N]: ")
                .strip()
                .lower()
            )
            if confirmation not in ["y", "yes"]:
                console.print("[yellow]Job removal cancelled[/yellow]")
                return False

        removed_files = []

        try:
            # Remove job metadata file
            job_file.unlink()
            removed_files.append(str(job_file))

            # Remove input file if it exists
            if batch_job.input_file_path:
                input_file = Path(batch_job.input_file_path)
                if input_file.exists():
                    input_file.unlink()
                    removed_files.append(str(input_file))

            # Remove output file if it exists
            if batch_job.output_file_path:
                output_file = Path(batch_job.output_file_path)
                if output_file.exists():
                    output_file.unlink()
                    removed_files.append(str(output_file))

            console.print(f"[green]✓ Removed batch job {full_job_id}[/green]")
            console.print(f"[green]Removed {len(removed_files)} file(s):[/green]")
            for file_path in removed_files:
                console.print(f"  - {file_path}")

            return True

        except Exception as e:
            console.print(f"[red]Failed to remove job files: {e}[/red]")
            console.print("[yellow]Some files may have been partially removed[/yellow]")
            raise

    def resolve_job_id(self, partial_id: str) -> str:
        """Resolve a partial job ID to a full job ID.

        Args:
            partial_id: Full or partial job ID

        Returns:
            Full job ID

        Raises:
            ValueError: If no matching job found or multiple matches
        """
        jobs_dir = self.base_path / "jobs"

        if not jobs_dir.exists():
            raise ValueError("No batch jobs found")

        # If it's already a full UUID (36 chars with dashes), try exact match first
        if len(partial_id) == 36 and partial_id.count("-") == 4:
            job_file = jobs_dir / f"{partial_id}.json"
            if job_file.exists():
                return partial_id

        # Find all job files that start with the partial ID
        matching_files = []
        for job_file in jobs_dir.glob("*.json"):
            job_id = job_file.stem
            if job_id.startswith(partial_id):
                matching_files.append(job_id)

        if not matching_files:
            raise ValueError(f"No batch job found matching '{partial_id}'")

        if len(matching_files) > 1:
            job_list = ", ".join(matching_files[:3])
            extra_count = len(matching_files) - 3
            extra_msg = f" and {extra_count} more" if len(matching_files) > 3 else ""
            raise ValueError(
                f"Multiple batch jobs match '{partial_id}': {job_list}{extra_msg}"
            )

        return matching_files[0]

    def get_job(self, job_id: str) -> BatchJob:
        """Get batch job by ID (supports partial IDs).

        Args:
            job_id: Full or partial batch job identifier

        Returns:
            Batch job
        """
        # Resolve partial ID to full ID
        full_job_id = self.resolve_job_id(job_id)
        job_file = self.base_path / "jobs" / f"{full_job_id}.json"

        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)
            return BatchJob.model_validate(job_data)
