"""Tests for CLI collect command."""

import os
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from gh_analysis.cli.collect import app
from gh_analysis.github_client.models import GitHubIssue


class TestCollectCommand:
    """Test the collect CLI command."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_organization_with_exclusions(
        self, mock_storage: Mock, mock_searcher_class: Mock, mock_client_class: Mock
    ) -> None:
        """Test collecting from organization with repository exclusions."""
        # Mock GitHub client and searcher
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher

        # Mock issue data
        mock_issue = Mock(spec=GitHubIssue)
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.state = "closed"
        mock_issue.comments = []
        mock_issue.repository_name = "test-repo"
        mock_issue.attachments = []

        mock_searcher.search_organization_issues.return_value = [mock_issue]

        # Mock storage
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command with exclusions
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "testorg",
                "--exclude-repo",
                "private-repo",
                "--exclude-repos",
                "test-repo,archived-repo",
                "--limit",
                "5",
                "--no-download-attachments",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify search was called with correct exclusions
        mock_searcher.search_organization_issues.assert_called_once()
        call_args = mock_searcher.search_organization_issues.call_args
        assert call_args.kwargs["org"] == "testorg"
        assert call_args.kwargs["labels"] is None
        assert call_args.kwargs["state"] == "closed"
        assert call_args.kwargs["limit"] == 5
        assert sorted(call_args.kwargs["excluded_repos"]) == [
            "archived-repo",
            "private-repo",
            "test-repo",
        ]

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_organization_single_exclusion(
        self, mock_storage: Mock, mock_searcher_class: Mock, mock_client_class: Mock
    ) -> None:
        """Test collecting from organization with single repository exclusion."""
        # Mock GitHub client and searcher
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher

        # Mock issue data
        mock_issue = Mock(spec=GitHubIssue)
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.state = "open"
        mock_issue.comments = []
        mock_issue.repository_name = "test-repo"
        mock_issue.attachments = []

        mock_searcher.search_organization_issues.return_value = [mock_issue]

        # Mock storage
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command with single exclusion
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "testorg",
                "--exclude-repo",
                "private-repo",
                "--state",
                "open",
                "--limit",
                "10",
                "--no-download-attachments",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify search was called with correct exclusions
        mock_searcher.search_organization_issues.assert_called_once_with(
            org="testorg",
            labels=None,
            state="open",
            limit=10,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
            excluded_repos=["private-repo"],
        )

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_organization_no_exclusions(
        self, mock_storage: Mock, mock_searcher_class: Mock, mock_client_class: Mock
    ) -> None:
        """Test collecting from organization without exclusions."""
        # Mock GitHub client and searcher
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher

        # Mock issue data
        mock_issue = Mock(spec=GitHubIssue)
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.state = "closed"
        mock_issue.comments = []
        mock_issue.repository_name = "test-repo"
        mock_issue.attachments = []

        mock_searcher.search_organization_issues.return_value = [mock_issue]

        # Mock storage
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command without exclusions
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "testorg",
                "--limit",
                "10",
                "--no-download-attachments",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify search was called without exclusions
        mock_searcher.search_organization_issues.assert_called_once_with(
            org="testorg",
            labels=None,
            state="closed",
            limit=10,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
            excluded_repos=[],
        )

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_repository_exclusions_ignored(
        self, mock_storage: Mock, mock_searcher_class: Mock, mock_client_class: Mock
    ) -> None:
        """Test that exclusions are ignored for repository-specific collection."""
        # Mock GitHub client and searcher
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher

        # Mock issue data
        mock_issue = Mock(spec=GitHubIssue)
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.state = "closed"
        mock_issue.comments = []
        mock_issue.repository_name = "test-repo"
        mock_issue.attachments = []

        mock_searcher.search_repository_issues.return_value = [mock_issue]

        # Mock storage
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command for repository-specific collection with exclusions
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "testorg",
                "--repo",
                "test-repo",
                "--exclude-repo",
                "private-repo",
                "--limit",
                "10",
                "--no-download-attachments",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify repository search was called (not organization search)
        mock_searcher.search_repository_issues.assert_called_once_with(
            org="testorg",
            repo="test-repo",
            labels=None,
            state="closed",
            limit=10,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
        )

        # Verify organization search was not called
        mock_searcher.search_organization_issues.assert_not_called()

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    @patch("gh_analysis.cli.collect.GitHubClient")
    @patch("gh_analysis.cli.collect.GitHubSearcher")
    @patch("gh_analysis.cli.collect.StorageManager")
    def test_collect_duplicate_exclusions_handled(
        self, mock_storage: Mock, mock_searcher_class: Mock, mock_client_class: Mock
    ) -> None:
        """Test that duplicate exclusions are handled correctly."""
        # Mock GitHub client and searcher
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_searcher = Mock()
        mock_searcher_class.return_value = mock_searcher

        # Mock issue data
        mock_issue = Mock(spec=GitHubIssue)
        mock_issue.number = 1
        mock_issue.title = "Test Issue"
        mock_issue.state = "closed"
        mock_issue.comments = []
        mock_issue.repository_name = "test-repo"
        mock_issue.attachments = []

        mock_searcher.search_organization_issues.return_value = [mock_issue]

        # Mock storage
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.save_issues.return_value = ["test_path"]
        mock_storage_instance.get_storage_stats.return_value = {
            "total_issues": 1,
            "total_size_mb": 0.1,
            "storage_path": "/test/path",
            "repositories": {"test-repo": 1},
        }

        # Run command with duplicate exclusions
        result = self.runner.invoke(
            app,
            [
                "collect",
                "--org",
                "testorg",
                "--exclude-repo",
                "private-repo",
                "--exclude-repo",
                "private-repo",  # Duplicate
                "--exclude-repos",
                "private-repo,test-repo",  # Another duplicate
                "--limit",
                "5",
                "--no-download-attachments",
            ],
        )

        # Verify command succeeded
        assert result.exit_code == 0

        # Verify search was called with deduplicated exclusions
        mock_searcher.search_organization_issues.assert_called_once()
        call_args = mock_searcher.search_organization_issues.call_args
        excluded_repos = call_args.kwargs["excluded_repos"]

        # Should have unique repositories only
        assert sorted(excluded_repos) == ["private-repo", "test-repo"]
