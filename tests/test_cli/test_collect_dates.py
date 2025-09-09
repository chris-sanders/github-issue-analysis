"""Tests for CLI collect command with date filtering functionality."""

from typing import Any
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from gh_analysis.cli.collect import app


class TestCollectDateFiltering:
    """Test collect command with date filtering options."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.mock_issue = Mock()
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = "Test issue body"
        self.mock_issue.state = "open"
        self.mock_issue.comments = []
        self.mock_issue.repository_name = "test-repo"
        self.mock_issue.attachments = []  # Add empty attachments to avoid processing

    @patch("gh_analysis.cli.collect.AttachmentDownloader")
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_with_created_after(
        self,
        mock_storage: Any,
        mock_searcher_class: Any,
        mock_client_class: Any,
        mock_downloader_class: Any,
    ) -> None:
        """Test collect command with --created-after option."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_repository_issues.return_value = [self.mock_issue]

        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.process_issue_attachments.return_value = self.mock_issue

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--created-after",
                "2024-01-01",
                "--limit",
                "5",
            ],
        )

        # Verify command succeeded
        if result.exit_code != 0:
            print(f"Command failed with exit code {result.exit_code}")
            print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Error: {result.stderr}")
        assert result.exit_code == 0

        # Verify searcher was called with date parameter
        mock_searcher.search_repository_issues.assert_called_once()
        call_args = mock_searcher.search_repository_issues.call_args
        assert call_args.kwargs["created_after"] == "2024-01-01"
        assert call_args.kwargs["created_before"] is None

    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_with_date_range(
        self, mock_storage: Any, mock_searcher_class: Any, mock_client_class: Any
    ) -> None:
        """Test collect command with date range (created-after and created-before)."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_repository_issues.return_value = [self.mock_issue]

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--created-after",
                "2024-01-01",
                "--created-before",
                "2024-06-30",
                "--limit",
                "5",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify searcher was called with date parameters
        mock_searcher.search_repository_issues.assert_called_once()
        call_args = mock_searcher.search_repository_issues.call_args
        assert call_args.kwargs["created_after"] == "2024-01-01"
        assert call_args.kwargs["created_before"] == "2024-06-30"

    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_with_updated_dates(
        self, mock_storage: Any, mock_searcher_class: Any, mock_client_class: Any
    ) -> None:
        """Test collect command with updated date filtering."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_repository_issues.return_value = [self.mock_issue]

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--updated-after",
                "2024-06-01",
                "--updated-before",
                "2024-06-30",
                "--limit",
                "5",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify searcher was called with updated date parameters
        mock_searcher.search_repository_issues.assert_called_once()
        call_args = mock_searcher.search_repository_issues.call_args
        assert call_args.kwargs["updated_after"] == "2024-06-01"
        assert call_args.kwargs["updated_before"] == "2024-06-30"

    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_with_last_days(
        self, mock_storage: Any, mock_searcher_class: Any, mock_client_class: Any
    ) -> None:
        """Test collect command with --last-days option."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_repository_issues.return_value = [self.mock_issue]

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--last-days",
                "30",
                "--limit",
                "5",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify searcher was called with created_after parameter (relative date)
        mock_searcher.search_repository_issues.assert_called_once()
        call_args = mock_searcher.search_repository_issues.call_args
        assert (
            call_args.kwargs["created_after"] is not None
        )  # Should be calculated relative date
        assert call_args.kwargs["created_before"] is None

    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_with_last_months(
        self, mock_storage: Any, mock_searcher_class: Any, mock_client_class: Any
    ) -> None:
        """Test collect command with --last-months option."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_repository_issues.return_value = [self.mock_issue]

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--last-months",
                "6",
                "--limit",
                "5",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify searcher was called with created_after parameter (relative date)
        mock_searcher.search_repository_issues.assert_called_once()
        call_args = mock_searcher.search_repository_issues.call_args
        assert (
            call_args.kwargs["created_after"] is not None
        )  # Should be calculated relative date

    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_organization_with_dates(
        self, mock_storage: Any, mock_searcher_class: Any, mock_client_class: Any
    ) -> None:
        """Test organization-wide collect command with date filtering."""
        self.setUp()

        # Setup mocks
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher
        mock_searcher.search_organization_issues.return_value = [self.mock_issue]

        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--created-after",
                "2024-01-01",
                "--limit",
                "10",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify organization searcher was called with date parameter
        mock_searcher.search_organization_issues.assert_called_once()
        call_args = mock_searcher.search_organization_issues.call_args
        assert call_args.kwargs["created_after"] == "2024-01-01"

    def test_collect_invalid_date_format(self) -> None:
        """Test collect command with invalid date format."""
        self.setUp()

        # Run command with invalid date
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--created-after",
                "invalid-date",
            ],
        )

        # Verify command failed with date validation error
        assert result.exit_code == 1
        assert "Date validation error" in result.stdout

    def test_collect_conflicting_date_options(self) -> None:
        """Test collect command with conflicting relative and absolute date options."""
        self.setUp()

        # Run command with conflicting options
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--created-after",
                "2024-01-01",
                "--last-days",
                "30",
            ],
        )

        # Verify command failed with conflict error
        assert result.exit_code == 1
        assert "Cannot combine relative date options" in result.stdout

    def test_collect_invalid_date_range(self) -> None:
        """Test collect command with invalid date range."""
        self.setUp()

        # Run command with start date after end date
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--created-after",
                "2024-12-31",
                "--created-before",
                "2024-01-01",
            ],
        )

        # Verify command failed with validation error
        assert result.exit_code == 1
        assert "Date validation error" in result.stdout

    def test_collect_negative_relative_days(self) -> None:
        """Test collect command with negative relative days."""
        self.setUp()

        # Run command with negative days
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--last-days",
                "-5",
            ],
        )

        # Verify command failed with validation error
        assert result.exit_code == 1
        assert "Date validation error" in result.stdout

    def test_collect_help_includes_date_options(self) -> None:
        """Test that help text includes the new date filtering options."""
        self.setUp()

        # Run help command
        result = self.runner.invoke(app, ["collect", "--help"])

        # Verify command succeeded
        assert result.exit_code == 0

        # Strip ANSI escape codes for reliable text matching
        import re

        help_text = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)

        # Verify help text includes date options
        assert "--created-after" in help_text
        assert "--created-before" in help_text
        assert "--updated-after" in help_text
        assert "--updated-before" in help_text
        assert "--last-days" in help_text
        assert "--last-weeks" in help_text
        assert "--last-months" in help_text

        # Verify help text includes date filtering examples
        assert "Date filtering examples" in help_text
        assert "Absolute date ranges" in help_text
        assert "Relative date filtering" in help_text
