"""Tests for GitHub client label update functionality."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from github.GithubException import RateLimitExceededException, UnknownObjectException

from gh_analysis.github_client.client import GitHubClient


@pytest.fixture
def mock_github() -> Generator[MagicMock]:
    """Mock GitHub API client."""
    with patch("gh_analysis.github_client.client.Github") as mock_github_class:
        mock_github = MagicMock()
        mock_github_class.return_value = mock_github

        # Mock rate limit
        mock_rate_limit = MagicMock()
        mock_rate_limit.core.remaining = 1000
        mock_github.get_rate_limit.return_value = mock_rate_limit

        yield mock_github


@pytest.fixture
def github_client(mock_github: MagicMock) -> GitHubClient:
    """GitHub client with mocked dependencies."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "fake-token"}):
        return GitHubClient()


class TestGitHubClientLabelUpdates:
    """Test GitHub client label update methods."""

    def test_update_issue_labels_success(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test successful label update."""
        # Mock repository and issue
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        # Test update
        result = github_client.update_issue_labels(
            "test-org", "test-repo", 123, ["bug", "enhancement"]
        )

        assert result is True
        mock_github.get_repo.assert_called_with("test-org/test-repo")
        mock_repo.get_issue.assert_called_with(123)
        mock_issue.set_labels.assert_called_with("bug", "enhancement")

    def test_update_issue_labels_issue_not_found(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test label update when issue not found."""
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = UnknownObjectException(404, "Not Found", {})

        with pytest.raises(ValueError, match="Issue #123 not found"):
            github_client.update_issue_labels("test-org", "test-repo", 123, ["bug"])

    def test_update_issue_labels_rate_limit(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test label update with rate limit handling."""
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        # First call hits rate limit, second succeeds
        mock_repo.get_issue.side_effect = [
            RateLimitExceededException(403, "Rate limit exceeded", {}),
            mock_issue,
        ]

        with patch("time.sleep") as mock_sleep:
            result = github_client.update_issue_labels(
                "test-org", "test-repo", 123, ["bug"]
            )

        assert result is True
        mock_sleep.assert_called_with(60)
        assert mock_repo.get_issue.call_count == 2

    def test_add_issue_comment_success(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test successful comment addition."""
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        result = github_client.add_issue_comment(
            "test-org", "test-repo", 123, "Test comment"
        )

        assert result is True
        mock_issue.create_comment.assert_called_with("Test comment")

    def test_add_issue_comment_issue_not_found(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test comment addition when issue not found."""
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = UnknownObjectException(404, "Not Found", {})

        with pytest.raises(ValueError, match="Issue #123 not found"):
            github_client.add_issue_comment(
                "test-org", "test-repo", 123, "Test comment"
            )

    def test_add_issue_comment_rate_limit(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test comment addition with rate limit handling."""
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        # First call hits rate limit, second succeeds
        mock_repo.get_issue.side_effect = [
            RateLimitExceededException(403, "Rate limit exceeded", {}),
            mock_issue,
        ]

        with patch("time.sleep") as mock_sleep:
            result = github_client.add_issue_comment(
                "test-org", "test-repo", 123, "Test comment"
            )

        assert result is True
        mock_sleep.assert_called_with(60)

    def test_get_issue_labels_success(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test successful label retrieval."""
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.return_value = mock_issue

        # Mock labels
        mock_label1 = MagicMock()
        mock_label1.name = "bug"
        mock_label2 = MagicMock()
        mock_label2.name = "enhancement"
        mock_issue.labels = [mock_label1, mock_label2]

        labels = github_client.get_issue_labels("test-org", "test-repo", 123)

        assert labels == ["bug", "enhancement"]

    def test_get_issue_labels_issue_not_found(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test label retrieval when issue not found."""
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = UnknownObjectException(404, "Not Found", {})

        with pytest.raises(ValueError, match="Issue #123 not found"):
            github_client.get_issue_labels("test-org", "test-repo", 123)

    def test_get_issue_labels_rate_limit(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test label retrieval with rate limit handling."""
        mock_repo = MagicMock()
        mock_issue = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        # First call hits rate limit, second succeeds
        mock_repo.get_issue.side_effect = [
            RateLimitExceededException(403, "Rate limit exceeded", {}),
            mock_issue,
        ]

        mock_issue.labels = []

        with patch("time.sleep") as mock_sleep:
            labels = github_client.get_issue_labels("test-org", "test-repo", 123)

        assert labels == []
        mock_sleep.assert_called_with(60)

    def test_repository_not_found(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test handling of repository not found."""
        mock_github.get_repo.side_effect = UnknownObjectException(404, "Not Found", {})

        with pytest.raises(ValueError, match="Repository test-org/test-repo not found"):
            github_client.update_issue_labels("test-org", "test-repo", 123, ["bug"])

    def test_generic_error_handling(
        self, github_client: GitHubClient, mock_github: MagicMock
    ) -> None:
        """Test handling of generic errors."""
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo
        mock_repo.get_issue.side_effect = Exception("Generic error")

        with pytest.raises(Exception, match="Generic error"):
            github_client.update_issue_labels("test-org", "test-repo", 123, ["bug"])
