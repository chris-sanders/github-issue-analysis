"""Tests for GitHub client."""

import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from github.GithubException import UnknownObjectException

from gh_analysis.github_client.client import GitHubClient
from gh_analysis.github_client.models import GitHubIssue


class TestGitHubClient:
    """Test GitHubClient class."""

    @patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})
    def test_init_with_env_token(self) -> None:
        """Test initialization with environment token."""
        with patch("gh_analysis.github_client.client.Github") as mock_github:
            GitHubClient()
            mock_github.assert_called_once_with("test_token")

    def test_init_with_explicit_token(self) -> None:
        """Test initialization with explicit token."""
        with patch("gh_analysis.github_client.client.Github") as mock_github:
            GitHubClient(token="explicit_token")
            mock_github.assert_called_once_with("explicit_token")

    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_token(self) -> None:
        """Test initialization without token raises error."""
        with pytest.raises(ValueError, match="GitHub token is required"):
            GitHubClient()

    @patch("gh_analysis.github_client.client.Github")
    def test_check_rate_limit(self, mock_github_class: Mock) -> None:
        """Test rate limit checking."""
        # Mock rate limit response
        mock_rate_limit = Mock()
        mock_rate_limit.core.remaining = 50
        mock_rate_limit.core.reset.timestamp.return_value = 1234567890

        mock_github = Mock()
        mock_github.get_rate_limit.return_value = mock_rate_limit
        mock_github_class.return_value = mock_github

        client = GitHubClient(token="test_token")

        # Should not raise any exceptions
        client._check_rate_limit()
        mock_github.get_rate_limit.assert_called()

    @patch("gh_analysis.github_client.client.Github")
    def test_get_repository_success(self, mock_github_class: Mock) -> None:
        """Test successful repository retrieval."""
        mock_repo = Mock()
        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        client = GitHubClient(token="test_token")
        result = client.get_repository("testorg", "testrepo")

        assert result == mock_repo
        mock_github.get_repo.assert_called_once_with("testorg/testrepo")

    @patch("gh_analysis.github_client.client.Github")
    def test_get_repository_not_found(self, mock_github_class: Mock) -> None:
        """Test repository not found error."""
        mock_github = Mock()
        mock_github.get_repo.side_effect = UnknownObjectException(
            404, "Not Found", None
        )
        mock_github_class.return_value = mock_github

        client = GitHubClient(token="test_token")

        with pytest.raises(ValueError, match="Repository testorg/testrepo not found"):
            client.get_repository("testorg", "testrepo")

    @patch("gh_analysis.github_client.client.Github")
    def test_convert_user(self, mock_github_class: Mock) -> None:
        """Test user conversion."""
        mock_github_class.return_value = Mock()
        client = GitHubClient(token="test_token")

        # Mock GitHub user
        mock_github_user = Mock()
        mock_github_user.login = "testuser"
        mock_github_user.id = 12345

        result = client._convert_user(mock_github_user)

        assert result.login == "testuser"
        assert result.id == 12345

    @patch("gh_analysis.github_client.client.Github")
    def test_convert_label(self, mock_github_class: Mock) -> None:
        """Test label conversion."""
        mock_github_class.return_value = Mock()
        client = GitHubClient(token="test_token")

        # Mock GitHub label
        mock_github_label = Mock()
        mock_github_label.name = "bug"
        mock_github_label.color = "ff0000"
        mock_github_label.description = "Bug reports"

        result = client._convert_label(mock_github_label)

        assert result.name == "bug"
        assert result.color == "ff0000"
        assert result.description == "Bug reports"

    @patch("gh_analysis.github_client.client.Github")
    def test_convert_comment(self, mock_github_class: Mock) -> None:
        """Test comment conversion."""
        mock_github_class.return_value = Mock()
        client = GitHubClient(token="test_token")

        # Mock GitHub comment
        mock_user = Mock()
        mock_user.login = "commenter"
        mock_user.id = 54321

        mock_comment = Mock()
        mock_comment.id = 98765
        mock_comment.user = mock_user
        mock_comment.body = "Test comment"
        mock_comment.created_at = datetime(2024, 1, 1)
        mock_comment.updated_at = datetime(2024, 1, 2)

        result = client._convert_comment(mock_comment)

        assert result.id == 98765
        assert result.user.login == "commenter"
        assert result.user.id == 54321
        assert result.body == "Test comment"
        assert result.created_at == datetime(2024, 1, 1)
        assert result.updated_at == datetime(2024, 1, 2)

    @patch("gh_analysis.github_client.client.Github")
    def test_get_issue(self, mock_github_class: Mock) -> None:
        """Test getting a single issue."""
        # Setup mocks
        mock_user = Mock()
        mock_user.login = "issueuser"
        mock_user.id = 11111

        mock_label = Mock()
        mock_label.name = "bug"
        mock_label.color = "ff0000"
        mock_label.description = "Bug reports"

        mock_comment = Mock()
        mock_comment.id = 33333
        mock_comment.user = mock_user
        mock_comment.body = "Test comment"
        mock_comment.created_at = datetime(2024, 1, 1)
        mock_comment.updated_at = datetime(2024, 1, 1)

        mock_repository = Mock()
        mock_repository.name = "testrepo"

        mock_issue = Mock()
        mock_issue.number = 42
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test body"
        mock_issue.state = "open"
        mock_issue.labels = [mock_label]
        mock_issue.user = mock_user
        mock_issue.created_at = datetime(2024, 1, 1)
        mock_issue.updated_at = datetime(2024, 1, 1)
        mock_issue.get_comments.return_value = [mock_comment]
        mock_issue.repository = mock_repository

        mock_repo = Mock()
        mock_repo.get_issue.return_value = mock_issue

        mock_github = Mock()
        mock_github.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github

        client = GitHubClient(token="test_token")

        with patch.object(client, "_check_rate_limit"):
            result = client.get_issue("testorg", "testrepo", 42)

        assert isinstance(result, GitHubIssue)
        assert result.number == 42
        assert result.title == "Test Issue"
        assert len(result.labels) == 1
        assert len(result.comments) == 1

    @patch("gh_analysis.github_client.client.Github")
    def test_search_issues(self, mock_github_class: Mock) -> None:
        """Test searching for issues."""
        # Setup mock issue
        mock_user = Mock()
        mock_user.login = "issueuser"
        mock_user.id = 11111

        mock_repository = Mock()
        mock_repository.name = "testrepo"

        mock_issue = Mock()
        mock_issue.number = 42
        mock_issue.title = "Test Issue"
        mock_issue.body = "Test body"
        mock_issue.state = "open"
        mock_issue.labels = []
        mock_issue.user = mock_user
        mock_issue.created_at = datetime(2024, 1, 1)
        mock_issue.updated_at = datetime(2024, 1, 1)
        mock_issue.get_comments.return_value = []
        mock_issue.repository = mock_repository

        mock_github = Mock()
        mock_github.search_issues.return_value = [mock_issue]
        mock_github_class.return_value = mock_github

        client = GitHubClient(token="test_token")

        with patch.object(client, "_check_rate_limit"):
            results = client.search_issues(
                org="testorg", repo="testrepo", labels=["bug"], state="open", limit=1
            )

        assert len(results) == 1
        assert results[0].number == 42
        assert results[0].title == "Test Issue"

        # Verify search query was built correctly
        expected_query = "repo:testorg/testrepo is:issue state:open label:bug"
        mock_github.search_issues.assert_called_once_with(expected_query)
