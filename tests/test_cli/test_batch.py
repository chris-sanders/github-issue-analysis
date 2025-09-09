"""Tests for CLI batch processing commands."""

import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from gh_analysis.ai.batch.models import BatchJob
from gh_analysis.cli.batch import app


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI runner for testing."""
    return CliRunner(env={"NO_COLOR": "1", "FORCE_COLOR": "0", "TERM": "dumb"})


@pytest.fixture
def sample_batch_job() -> BatchJob:
    """Create sample batch job for testing."""
    return BatchJob(
        job_id=str(uuid.uuid4()),
        processor_type="product-labeling",
        org="test-org",
        repo="test-repo",
        issue_number=None,
        ai_model_config={
            "model_name": "openai:gpt-4o",
            "temperature": 0.0,
            "retry_count": 2,
            "include_images": True,
        },
        total_items=5,
        openai_batch_id="batch_123",
        input_file_id="file_123",
        output_file_id=None,
        submitted_at=None,
        completed_at=None,
        processed_items=0,
        failed_items=0,
        input_file_path=None,
        output_file_path=None,
        status="validating",
    )


class TestBatchSubmitCommand:
    """Test batch submit command with new AI configuration options."""

    def test_submit_help_displays_rich_panels(self, runner: CliRunner) -> None:
        """Test that help text shows organized rich help panels."""
        result = runner.invoke(app, ["submit", "--help"])

        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        assert "Target Selection" in clean_output
        assert "AI Configuration" in clean_output
        assert "Processing Options" in clean_output
        assert "--model" in clean_output
        assert "--temperature" in clean_output
        assert "--retry-count" in clean_output
        assert "--thinking-effort" in clean_output
        assert "--max-items" in clean_output

    def test_submit_with_new_options_dry_run(self, runner: CliRunner) -> None:
        """Test batch submit with new AI configuration options in dry run mode."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            # Mock the BatchManager instance and its methods
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.find_issues.return_value = [
                {
                    "org": "test-org",
                    "repo": "test-repo",
                    "issue": {"number": 1, "title": "Test issue"},
                }
            ]

            result = runner.invoke(
                app,
                [
                    "submit",
                    "product-labeling",
                    "--org",
                    "test-org",
                    "--repo",
                    "test-repo",
                    "--model",
                    "openai:o4-mini",
                    "--temperature",
                    "0.3",
                    "--retry-count",
                    "3",
                    "--thinking-effort",
                    "medium",
                    "--max-items",
                    "10",
                    "--dry-run",
                ],
            )

        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        assert result.exit_code == 0
        assert "openai:o4-mini" in result.stdout
        assert "Temperature: 0.3" in result.stdout
        assert "Retry count: 3" in result.stdout
        assert "Thinking effort: medium" in result.stdout
        # "Limited to 10 items" only appears when there are more than 10 items
        # With only 1 test issue, this message won't appear
        assert "Dry run - no batch job submitted" in result.stdout

    def test_submit_with_thinking_budget(self, runner: CliRunner) -> None:
        """Test batch submit with thinking budget parameter."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.find_issues.return_value = [
                {
                    "org": "test-org",
                    "repo": "test-repo",
                    "issue": {"number": 1, "title": "Test issue"},
                }
            ]

            result = runner.invoke(
                app,
                [
                    "submit",
                    "product-labeling",
                    "--org",
                    "test-org",
                    "--model",
                    "openai:o4-mini",
                    "--thinking-budget",
                    "5000",
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0
        assert "openai:o4-mini" in result.stdout
        assert "Thinking budget: 5000 tokens" in result.stdout

    def test_submit_creates_batch_job_with_new_config(
        self, runner: CliRunner, sample_batch_job: BatchJob
    ) -> None:
        """Test that batch job is created with new configuration format."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.find_issues.return_value = [
                {
                    "org": "test-org",
                    "repo": "test-repo",
                    "issue": {"number": 1, "title": "Test issue"},
                }
            ]

            # Mock async method
            mock_manager.create_batch_job = AsyncMock(return_value=sample_batch_job)

            with patch("gh_analysis.cli.batch.RecommendationManager"):
                result = runner.invoke(
                    app,
                    [
                        "submit",
                        "product-labeling",
                        "--org",
                        "test-org",
                        "--repo",
                        "test-repo",
                        "--model",
                        "openai:gpt-4o",
                        "--temperature",
                        "0.5",
                        "--retry-count",
                        "1",
                    ],
                )

        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        assert result.exit_code == 0

        # Verify create_batch_job was called with new config format
        mock_manager.create_batch_job.assert_called_once()
        call_args = mock_manager.create_batch_job.call_args

        # Check the model_config parameter was passed as dict with new format
        model_config = call_args.kwargs["model_config"]
        assert model_config["model"] == "openai:gpt-4o"
        assert model_config["temperature"] == 0.5
        assert model_config["retry_count"] == 1

    def test_submit_max_items_filtering(self, runner: CliRunner) -> None:
        """Test that max_items parameter correctly limits the issues."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            # Return more issues than max_items limit
            mock_manager.find_issues.return_value = [
                {
                    "org": "test-org",
                    "repo": "test-repo",
                    "issue": {"number": i, "title": f"Issue {i}"},
                }
                for i in range(1, 16)  # 15 issues
            ]

            result = runner.invoke(
                app,
                [
                    "submit",
                    "product-labeling",
                    "--org",
                    "test-org",
                    "--max-items",
                    "5",
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0
        assert "Limited to 5 items (from 15 total)" in result.stdout
        assert "Found 5 issue(s) to process" in result.stdout

    def test_submit_invalid_processor_type(self, runner: CliRunner) -> None:
        """Test error handling for invalid processor type."""
        result = runner.invoke(
            app, ["submit", "invalid-processor", "--org", "test-org", "--dry-run"]
        )

        assert result.exit_code == 1
        assert "Unsupported processor type: invalid-processor" in result.stdout

    def test_submit_missing_org_for_issue_number(self, runner: CliRunner) -> None:
        """Test error when org is missing (required parameter)."""
        result = runner.invoke(
            app, ["submit", "product-labeling", "--issue-number", "123", "--dry-run"]
        )

        assert (
            result.exit_code == 2
        )  # Typer validation error for missing required parameter
        assert "Missing option '--org'" in strip_ansi(result.stderr)


class TestBatchCliBackwardCompatibility:
    """Test backward compatibility of batch CLI commands."""

    def test_old_style_parameters_still_work(self, runner: CliRunner) -> None:
        """Test that existing parameters without rich help panels still function."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.find_issues.return_value = [
                {
                    "org": "test-org",
                    "repo": "test-repo",
                    "issue": {"number": 1, "title": "Test issue"},
                }
            ]

            # Use traditional style without new options
            result = runner.invoke(
                app,
                [
                    "submit",
                    "product-labeling",
                    "--org",
                    "test-org",
                    "--repo",
                    "test-repo",
                    "--include-images",
                    "--dry-run",
                ],
            )

        assert result.exit_code == 0
        assert "Found 1 issue(s) to process" in result.stdout

    def test_status_command_unchanged(self, runner: CliRunner) -> None:
        """Test that status command functionality is unchanged."""
        job_id = str(uuid.uuid4())

        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager

            # Mock a completed batch job
            mock_batch_job = MagicMock()
            mock_batch_job.processor_type = "product-labeling"
            mock_batch_job.org = "test-org"
            mock_batch_job.repo = "test-repo"
            mock_batch_job.issue_number = None
            mock_batch_job.status = "completed"
            mock_batch_job.total_items = 5
            mock_batch_job.processed_items = 5
            mock_batch_job.failed_items = 0
            mock_batch_job.openai_batch_id = "batch_123"
            mock_batch_job.errors = []
            mock_batch_job.created_at.strftime.return_value = "2024-01-01 12:00:00 UTC"

            mock_manager.check_job_status.return_value = mock_batch_job

            result = runner.invoke(app, ["status", job_id[:8]])

        assert result.exit_code == 0
        assert "Batch Job:" in result.stdout
        assert "Status: COMPLETED" in result.stdout

    def test_list_command_unchanged(self, runner: CliRunner) -> None:
        """Test that list command functionality is unchanged."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = AsyncMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.list_jobs.return_value = []

            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No batch jobs found" in result.stdout


class TestBatchErrorHandling:
    """Test error handling in batch commands."""

    def test_invalid_model_format_error(self, runner: CliRunner) -> None:
        """Test error handling for invalid model format."""
        result = runner.invoke(
            app,
            [
                "submit",
                "product-labeling",
                "--org",
                "test-org",
                "--model",
                "invalid-model",  # No colon, invalid format
            ],
        )

        assert result.exit_code == 1  # Error exit code
        assert "Invalid model format" in result.stdout

    def test_batch_manager_exception_handling(self, runner: CliRunner) -> None:
        """Test error handling when batch manager throws exceptions."""
        with patch(
            "gh_analysis.cli.batch.BatchManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.find_issues.side_effect = Exception(
                "Database connection failed"
            )

            result = runner.invoke(
                app, ["submit", "product-labeling", "--org", "test-org", "--dry-run"]
            )

        assert result.exit_code == 1
        assert "Error finding issues: Database connection failed" in result.stdout
