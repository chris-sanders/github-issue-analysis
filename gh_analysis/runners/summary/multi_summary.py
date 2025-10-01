"""Multi-agent summary runner that orchestrates specialized agents in parallel."""

import asyncio
from typing import Dict, Any

from .utils.github_runner import GitHubIssueRunner
from .summary_models import SummaryAnalysis
from .specialized import (
    ProductAgentRunner,
    SymptomsAgentRunner,
    EvidenceAgentRunner,
    CauseAgentRunner,
    FixAgentRunner,
    ConfidenceAgentRunner,
)


class MultiSummaryRunner(GitHubIssueRunner):
    """Runner that coordinates multiple specialized agents to generate comprehensive summaries."""

    # Class variable for timeout configuration - can be set by calling code
    timeout_seconds = (
        2100  # Default 35 minutes (AGENT_EXECUTION_TIMEOUT + 180), can be overridden
    )

    def __init__(self):
        # Initialize all specialized agents
        self.product_runner = ProductAgentRunner()
        self.symptoms_runner = SymptomsAgentRunner()
        self.evidence_runner = EvidenceAgentRunner()
        self.cause_runner = CauseAgentRunner()
        self.fix_runner = FixAgentRunner()
        self.confidence_runner = ConfidenceAgentRunner()

        # Call super with None agent - base class handles this gracefully
        super().__init__("multi-summary", None)

    async def analyze(self, issue: Dict[str, Any]) -> SummaryAnalysis:
        """
        Run all specialized agents in parallel and combine their results.

        Args:
            issue: Issue data to analyze

        Returns:
            Complete SummaryAnalysis with all fields populated
        """
        try:
            # Run all agents concurrently with better cancel scope handling
            print("🔄 Running 6 specialized agents in parallel...")

            # Log start time for debugging hangs
            import time

            start_time = time.time()

            # Create tasks for all agents
            tasks = {
                "product": asyncio.create_task(self.product_runner.analyze(issue)),
                "symptoms": asyncio.create_task(self.symptoms_runner.analyze(issue)),
                "evidence": asyncio.create_task(self.evidence_runner.analyze(issue)),
                "cause": asyncio.create_task(self.cause_runner.analyze(issue)),
                "fix": asyncio.create_task(self.fix_runner.analyze(issue)),
                "confidence": asyncio.create_task(
                    self.confidence_runner.analyze(issue)
                ),
            }

            # Wait for all tasks to complete, handling exceptions individually
            results = {}
            failures = []

            # Use asyncio.wait with timeout to prevent indefinite hangs
            try:
                done, pending = await asyncio.wait(
                    tasks.values(),
                    return_when=asyncio.ALL_COMPLETED,
                    timeout=self.timeout_seconds,
                )

                if pending:
                    timeout_minutes = (
                        self.timeout_seconds / 60
                    )  # Convert seconds to minutes
                    print(
                        f"⚠️ {len(pending)} agents timed out after {timeout_minutes:.0f} minutes, cancelling..."
                    )
                    for task in pending:
                        task.cancel()
            except asyncio.TimeoutError:
                timeout_minutes = (
                    self.timeout_seconds / 60
                )  # Convert seconds to minutes
                print(
                    f"❌ MultiSummaryRunner timed out after {timeout_minutes:.0f} minutes"
                )
                for task in tasks.values():
                    task.cancel()
                return f"❌ MultiSummaryRunner timed out after {timeout_minutes:.0f} minutes"

            # Log completion time for debugging
            elapsed_time = time.time() - start_time
            print(f"⏱️ MultiSummaryRunner completed in {elapsed_time:.1f} seconds")

            # Process completed tasks
            for task_name, task in tasks.items():
                try:
                    results[task_name] = await task
                except Exception as e:
                    failures.append(f"{task_name}: {str(e)}")
                    print(f"❌ {task_name} agent failed: {str(e)}")

            if failures:
                failure_msg = f"❌ Agent failures: {'; '.join(failures)}"
                print(failure_msg)
                return failure_msg

            # Extract results
            product_result = results["product"]
            symptoms_result = results["symptoms"]
            evidence_result = results["evidence"]
            cause_result = results["cause"]
            fix_result = results["fix"]
            confidence_result = results["confidence"]

            # Combine into final SummaryAnalysis
            summary = SummaryAnalysis(
                product=product_result.product,
                symptoms=symptoms_result.symptoms,
                evidence=evidence_result.evidence,
                cause=cause_result.cause,
                fix=fix_result.fix,
                confidence=confidence_result.confidence,
            )

            print("✅ Multi-agent analysis complete")
            return summary

        except Exception as e:
            error_msg = f"❌ Multi-agent summary failed: {str(e)}"
            print(error_msg)
            return error_msg

    def get_last_span_id(self):
        """
        Get the last span ID from one of the specialized runners.
        Since all agents run in parallel, we'll return the confidence runner's span ID.
        """
        return self.confidence_runner.get_last_span_id()

    def get_model_info(self) -> str:
        """Get model information from all sub-agents."""
        # Collect all sub-runners
        sub_runners = [
            self.product_runner,
            self.symptoms_runner,
            self.evidence_runner,
            self.cause_runner,
            self.fix_runner,
            self.confidence_runner,
        ]

        # Get model info from each
        models = []
        for runner in sub_runners:
            if hasattr(runner, "agent") and runner.agent:
                model_info = runner.get_model_info()
                models.append(model_info)

        # Count unique models
        from collections import Counter

        model_counts = Counter(models)

        # Format result
        if len(model_counts) == 1:
            # All agents use the same model
            model_name, count = list(model_counts.items())[0]
            return f"{model_name} ({count} agents)"
        else:
            # Multiple different models
            parts = [f"{model} ({count})" for model, count in model_counts.items()]
            return ", ".join(parts)

    def _build_context(self, issue: Dict[str, Any]) -> str:
        """Required by abstract base class but unused since each specialized agent builds its own context."""
        return ""
