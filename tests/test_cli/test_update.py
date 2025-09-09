"""Tests for CLI update functionality with new recommendation system."""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gh_analysis.cli.main import app


def strip_ansi(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


class TestUpdateLabelsBasic:
    """Basic tests for update-labels CLI command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Provide CLI test runner."""
        return CliRunner(env={"NO_COLOR": "1", "FORCE_COLOR": "0"})

    def test_help_display(self, runner: CliRunner) -> None:
        """Test that help displays correctly."""
        result = runner.invoke(app, ["update-labels", "--help"])
        assert result.exit_code == 0
        clean_output = strip_ansi(result.stdout)
        assert "Update GitHub issue labels based on AI recommendations" in clean_output
        assert "--org" in clean_output
        assert "--dry-run" in clean_output
        assert "--min-confidence" in clean_output

    def test_command_requires_org(self, runner: CliRunner) -> None:
        """Test that org parameter is required."""
        result = runner.invoke(app, ["update-labels"])
        assert result.exit_code == 1
        assert "Error: --org is required" in result.stdout

    def test_repo_requires_org(self, runner: CliRunner) -> None:
        """Test that repo requires org."""
        result = runner.invoke(app, ["update-labels", "--repo", "test-repo"])
        assert result.exit_code == 1
        assert "Error: --org is required when --repo is specified" in result.stdout

    def test_issue_number_requires_repo(self, runner: CliRunner) -> None:
        """Test that issue number requires both org and repo."""
        result = runner.invoke(
            app, ["update-labels", "--org", "test-org", "--issue-number", "123"]
        )
        assert result.exit_code == 1
        assert (
            "Error: --org and --repo are required when --issue-number is specified"
            in result.stdout
        )

    def test_missing_data_dir(self, runner: CliRunner) -> None:
        """Test error when data directory doesn't exist."""
        result = runner.invoke(
            app,
            [
                "update-labels",
                "--org",
                "test-org",
                "--data-dir",
                "/nonexistent/path",
            ],
        )
        assert result.exit_code == 1
        assert "Error: Data directory" in result.stdout

    def test_no_recommendations_found(
        self, runner: CliRunner, temp_data_dir: Path
    ) -> None:
        """Test when no recommendations are found."""
        result = runner.invoke(
            app,
            [
                "update-labels",
                "--org",
                "nonexistent-org",
                "--data-dir",
                str(temp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "No label changes needed" in result.stdout

    def test_status_filtering_message(
        self, runner: CliRunner, temp_data_dir: Path
    ) -> None:
        """Test that status filtering message is displayed."""
        result = runner.invoke(
            app,
            [
                "update-labels",
                "--org",
                "test-org",
                "--data-dir",
                str(temp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Only processing APPROVED recommendations" in result.stdout

    def test_ignore_status_flag(self, runner: CliRunner, temp_data_dir: Path) -> None:
        """Test ignore status flag."""
        result = runner.invoke(
            app,
            [
                "update-labels",
                "--org",
                "test-org",
                "--ignore-status",
                "--data-dir",
                str(temp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Status filtering disabled" in result.stdout
