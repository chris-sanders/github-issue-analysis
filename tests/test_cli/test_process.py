"""Test CLI process commands with new agent interface."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from github_issue_analysis.cli.process import _process_single_issue, app


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestProductLabelingBasic:
    """Basic tests for product-labeling CLI command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Provide CLI test runner."""
        return CliRunner(env={"NO_COLOR": "1", "FORCE_COLOR": "0"})

    def test_help_display(self, runner: CliRunner) -> None:
        """Test that help displays correctly."""
        result = runner.invoke(app, ["product-labeling", "--help"])
        assert result.exit_code == 0
        assert "AI Configuration" in result.stdout
        assert "Target Selection" in result.stdout
        assert "Processing Options" in result.stdout

    def test_command_requires_org(self, runner: CliRunner) -> None:
        """Test that org parameter is required."""
        result = runner.invoke(app, ["product-labeling"])
        # Should fail because --org is required
        assert result.exit_code == 2  # Typer validation error
        assert "Missing option '--org'" in strip_ansi(result.stderr)

    def test_concurrency_parameter(self, runner: CliRunner) -> None:
        """Test that concurrency parameter is accepted."""
        result = runner.invoke(app, ["product-labeling", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        assert "--concurrency" in clean_output
        assert "concurrent" in clean_output.lower()

    def test_concurrency_default_value(self, runner: CliRunner) -> None:
        """Test that concurrency has correct default value."""
        result = runner.invoke(app, ["product-labeling", "--help"])
        assert result.exit_code == 0
        # Should show default value of 20
        assert "default: 20" in result.stdout or "[default: 20]" in result.stdout


class TestConcurrentProcessing:
    """Test concurrent processing functionality."""

    @pytest.fixture
    def mock_issue_data(self) -> dict[str, Any]:
        """Create mock issue data."""
        return {
            "org": "test-org",
            "repo": "test-repo",
            "issue": {
                "number": 123,
                "title": "Test issue",
                "body": "Test body",
                "labels": [],
                "attachments": [],
            },
        }

    @pytest.fixture
    def mock_recommendation_manager(self) -> Any:
        """Create mock recommendation manager."""
        with patch("github_issue_analysis.cli.process.RecommendationManager") as mock:
            mock_instance = mock.return_value
            mock_instance.should_reprocess_issue.return_value = True
            yield mock_instance

    @pytest.mark.asyncio
    async def test_process_single_issue_success(
        self,
        mock_issue_data: dict[str, Any],
        mock_recommendation_manager: Any,
        tmp_path: Path,
    ) -> None:
        """Test processing a single issue successfully."""
        # Create temporary issue file
        issue_file = tmp_path / "test_issue.json"
        with open(issue_file, "w") as f:
            json.dump(mock_issue_data, f)

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Mock the runner analysis
        async def mock_analyze(self, data):
            return type(
                "MockResult", (), {"model_dump": lambda self: {"test": "result"}}
            )()

        with patch("github_issue_analysis.runners.get_runner") as mock_get_runner:
            mock_runner = type("MockRunner", (), {"analyze": mock_analyze})()
            mock_get_runner.return_value = mock_runner

            semaphore = asyncio.Semaphore(1)
            result = await _process_single_issue(
                issue_file,
                mock_recommendation_manager,
                results_dir,
                "test-model",
                {},
                True,
                False,
                semaphore,
            )

            assert result == "processed"
            # Check that result file was created
            result_files = list(results_dir.glob("*.json"))
            assert len(result_files) == 1

    @pytest.mark.asyncio
    async def test_process_single_issue_skipped(
        self,
        mock_issue_data: dict[str, Any],
        mock_recommendation_manager: Any,
        tmp_path: Path,
    ) -> None:
        """Test skipping an issue that shouldn't be reprocessed."""
        # Configure mock to skip processing
        mock_recommendation_manager.should_reprocess_issue.return_value = False

        issue_file = tmp_path / "test_issue.json"
        with open(issue_file, "w") as f:
            json.dump(mock_issue_data, f)

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        semaphore = asyncio.Semaphore(1)
        result = await _process_single_issue(
            issue_file,
            mock_recommendation_manager,
            results_dir,
            "test-model",
            {},
            True,
            False,
            semaphore,
        )

        assert result == "skipped"

    @pytest.mark.asyncio
    async def test_concurrent_processing_with_semaphore(
        self, mock_issue_data: dict[str, Any], tmp_path: Path
    ) -> None:
        """Test that concurrent processing respects semaphore limits."""
        # Create multiple issue files
        issue_files = []
        for i in range(5):
            issue_file = tmp_path / f"test_issue_{i}.json"
            issue_data = mock_issue_data.copy()
            issue_data["issue"]["number"] = i + 1
            with open(issue_file, "w") as f:
                json.dump(issue_data, f)
            issue_files.append(issue_file)

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Track concurrency
        active_tasks = []
        max_concurrent = 0

        async def mock_analyze_with_tracking(self, *args, **kwargs):
            """Mock runner analyze that tracks concurrency."""
            nonlocal max_concurrent
            active_tasks.append(asyncio.current_task())
            max_concurrent = max(max_concurrent, len(active_tasks))

            # Simulate some work
            await asyncio.sleep(0.1)

            active_tasks.remove(asyncio.current_task())
            mock_result = type(
                "MockResult", (), {"model_dump": lambda self: {"test": "result"}}
            )()
            return mock_result

        with patch(
            "github_issue_analysis.cli.process.RecommendationManager"
        ) as mock_mgr:
            mock_mgr.return_value.should_reprocess_issue.return_value = True

            with patch("github_issue_analysis.runners.get_runner") as mock_get_runner:
                mock_runner = type(
                    "MockRunner", (), {"analyze": mock_analyze_with_tracking}
                )()
                mock_get_runner.return_value = mock_runner
                # Test with concurrency limit of 2
                semaphore = asyncio.Semaphore(2)
                tasks = []
                for issue_file in issue_files:
                    task = asyncio.create_task(
                        _process_single_issue(
                            issue_file,
                            mock_mgr.return_value,
                            results_dir,
                            "test-model",
                            {},
                            True,
                            False,
                            semaphore,
                        )
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks)

                # All should be processed
                assert all(result == "processed" for result in results)
                # Max concurrency should not exceed semaphore limit
                assert max_concurrent <= 2
