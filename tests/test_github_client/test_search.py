"""Tests for GitHub search functionality."""

from unittest.mock import Mock

from gh_analysis.github_client.client import GitHubClient
from gh_analysis.github_client.models import GitHubIssue
from gh_analysis.github_client.search import (
    GitHubSearcher,
    build_exclusion_list,
    build_github_query,
    build_organization_query,
)


class TestGitHubSearcher:
    """Test GitHubSearcher class."""

    def test_init(self) -> None:
        """Test searcher initialization."""
        mock_client = Mock(spec=GitHubClient)
        searcher = GitHubSearcher(mock_client)
        assert searcher.client == mock_client

    def test_search_repository_issues(self) -> None:
        """Test searching repository issues."""
        mock_client = Mock(spec=GitHubClient)
        mock_issues = [Mock(spec=GitHubIssue)]
        mock_client.search_issues.return_value = mock_issues

        searcher = GitHubSearcher(mock_client)

        results = searcher.search_repository_issues(
            org="testorg",
            repo="testrepo",
            labels=["bug", "enhancement"],
            state="open",
            limit=5,
        )

        assert results == mock_issues
        mock_client.search_issues.assert_called_once_with(
            org="testorg",
            repo="testrepo",
            labels=["bug", "enhancement"],
            state="open",
            limit=5,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
        )

    def test_search_repository_issues_defaults(self) -> None:
        """Test searching with default parameters."""
        mock_client = Mock(spec=GitHubClient)
        mock_issues = [Mock(spec=GitHubIssue)]
        mock_client.search_issues.return_value = mock_issues

        searcher = GitHubSearcher(mock_client)

        results = searcher.search_repository_issues(org="testorg", repo="testrepo")

        assert results == mock_issues
        mock_client.search_issues.assert_called_once_with(
            org="testorg",
            repo="testrepo",
            labels=None,
            state="open",
            limit=10,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
        )

    def test_get_single_issue(self) -> None:
        """Test getting a single issue."""
        mock_client = Mock(spec=GitHubClient)
        mock_issue = Mock(spec=GitHubIssue)
        mock_client.get_issue.return_value = mock_issue

        searcher = GitHubSearcher(mock_client)

        result = searcher.get_single_issue("testorg", "testrepo", 42)

        assert result == mock_issue
        mock_client.get_issue.assert_called_once_with("testorg", "testrepo", 42)


class TestBuildGitHubQuery:
    """Test build_github_query function."""

    def test_basic_query(self) -> None:
        """Test building basic query."""
        query = build_github_query("test-org", "test-repo")
        expected = "repo:test-org/test-repo is:issue state:open"
        assert query == expected

    def test_query_with_labels(self) -> None:
        """Test query with labels."""
        query = build_github_query(
            "test-org", "test-repo", labels=["bug", "enhancement"]
        )
        expected = (
            "repo:test-org/test-repo is:issue state:open label:bug label:enhancement"
        )
        assert query == expected

    def test_query_with_state_all(self) -> None:
        """Test query with state 'all'."""
        query = build_github_query("test-org", "test-repo", state="all")
        expected = "repo:test-org/test-repo is:issue"
        assert query == expected

    def test_query_with_closed_state(self) -> None:
        """Test query with closed state."""
        query = build_github_query("test-org", "test-repo", state="closed")
        expected = "repo:test-org/test-repo is:issue state:closed"
        assert query == expected

    def test_query_with_created_after(self) -> None:
        """Test query with created_after filter."""
        query = build_github_query("test-org", "test-repo", created_after="2024-01-01")
        expected = "repo:test-org/test-repo is:issue state:open created:>2024-01-01"
        assert query == expected

    def test_complex_query(self) -> None:
        """Test complex query with all parameters."""
        query = build_github_query(
            org="test-org",
            repo="test-repo",
            labels=["bug", "priority:high"],
            state="closed",
            created_after="2024-01-01",
        )
        expected = (
            "repo:test-org/test-repo is:issue state:closed label:bug "
            "label:priority:high created:>2024-01-01"
        )
        assert query == expected

    def test_query_with_empty_labels(self) -> None:
        """Test query with empty labels list."""
        query = build_github_query("test-org", "test-repo", labels=[])
        expected = "repo:test-org/test-repo is:issue state:open"
        assert query == expected

    def test_query_with_single_label(self) -> None:
        """Test query with single label."""
        query = build_github_query("test-org", "test-repo", labels=["bug"])
        expected = "repo:test-org/test-repo is:issue state:open label:bug"
        assert query == expected

    def test_search_organization_issues_with_exclusions(self) -> None:
        """Test searching organization issues with exclusions."""
        mock_client = Mock(spec=GitHubClient)
        mock_issues = [Mock(spec=GitHubIssue)]
        mock_client.search_organization_issues.return_value = mock_issues

        searcher = GitHubSearcher(mock_client)

        results = searcher.search_organization_issues(
            org="testorg",
            labels=["bug"],
            state="closed",
            limit=5,
            excluded_repos=["private-repo", "test-repo"],
        )

        assert results == mock_issues
        mock_client.search_organization_issues.assert_called_once_with(
            org="testorg",
            labels=["bug"],
            state="closed",
            limit=5,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
            excluded_repos=["private-repo", "test-repo"],
        )

    def test_search_organization_issues_no_exclusions(self) -> None:
        """Test searching organization issues without exclusions."""
        mock_client = Mock(spec=GitHubClient)
        mock_issues = [Mock(spec=GitHubIssue)]
        mock_client.search_organization_issues.return_value = mock_issues

        searcher = GitHubSearcher(mock_client)

        results = searcher.search_organization_issues(
            org="testorg",
            labels=["bug"],
            state="open",
            limit=10,
        )

        assert results == mock_issues
        mock_client.search_organization_issues.assert_called_once_with(
            org="testorg",
            labels=["bug"],
            state="open",
            limit=10,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
            excluded_repos=None,
        )


class TestBuildExclusionList:
    """Test build_exclusion_list function."""

    def test_no_exclusions(self) -> None:
        """Test with no exclusions provided."""
        result = build_exclusion_list(None, None)
        assert result == []

    def test_exclude_repo_only(self) -> None:
        """Test with only exclude_repo parameter."""
        result = build_exclusion_list(["repo1", "repo2"], None)
        assert sorted(result) == ["repo1", "repo2"]

    def test_exclude_repos_only(self) -> None:
        """Test with only exclude_repos parameter."""
        result = build_exclusion_list(None, "repo1,repo2,repo3")
        assert sorted(result) == ["repo1", "repo2", "repo3"]

    def test_both_parameters(self) -> None:
        """Test with both exclude_repo and exclude_repos."""
        result = build_exclusion_list(["repo1", "repo2"], "repo3,repo4")
        assert sorted(result) == ["repo1", "repo2", "repo3", "repo4"]

    def test_duplicates_removed(self) -> None:
        """Test that duplicate repositories are removed."""
        result = build_exclusion_list(["repo1", "repo2"], "repo2,repo3")
        assert sorted(result) == ["repo1", "repo2", "repo3"]

    def test_empty_strings_filtered(self) -> None:
        """Test that empty strings are filtered out."""
        result = build_exclusion_list(["repo1", ""], "repo2,,repo3")
        assert sorted(result) == ["repo1", "repo2", "repo3"]

    def test_whitespace_trimmed(self) -> None:
        """Test that whitespace is trimmed from comma-separated list."""
        result = build_exclusion_list(None, " repo1 , repo2 , repo3 ")
        assert sorted(result) == ["repo1", "repo2", "repo3"]

    def test_empty_lists(self) -> None:
        """Test with empty lists."""
        result = build_exclusion_list([], "")
        assert result == []


class TestBuildOrganizationQuery:
    """Test build_organization_query function."""

    def test_basic_query(self) -> None:
        """Test building basic organization query."""
        query = build_organization_query("testorg")
        expected = "org:testorg is:issue state:open"
        assert query == expected

    def test_query_with_labels(self) -> None:
        """Test query with labels."""
        query = build_organization_query("testorg", labels=["bug", "enhancement"])
        expected = "org:testorg is:issue state:open label:bug label:enhancement"
        assert query == expected

    def test_query_with_state_all(self) -> None:
        """Test query with state 'all'."""
        query = build_organization_query("testorg", state="all")
        expected = "org:testorg is:issue"
        assert query == expected

    def test_query_with_closed_state(self) -> None:
        """Test query with closed state."""
        query = build_organization_query("testorg", state="closed")
        expected = "org:testorg is:issue state:closed"
        assert query == expected

    def test_query_with_single_exclusion(self) -> None:
        """Test query with single repository exclusion."""
        query = build_organization_query("testorg", excluded_repos=["private-repo"])
        expected = "org:testorg is:issue state:open -repo:testorg/private-repo"
        assert query == expected

    def test_query_with_multiple_exclusions(self) -> None:
        """Test query with multiple repository exclusions."""
        query = build_organization_query(
            "testorg", excluded_repos=["private-repo", "test-repo", "archived-repo"]
        )
        expected = (
            "org:testorg is:issue state:open -repo:testorg/private-repo "
            "-repo:testorg/test-repo -repo:testorg/archived-repo"
        )
        assert query == expected

    def test_complex_query_with_exclusions(self) -> None:
        """Test complex query with all parameters including exclusions."""
        query = build_organization_query(
            org="testorg",
            labels=["bug", "priority:high"],
            state="closed",
            excluded_repos=["private-repo", "test-repo"],
        )
        expected = (
            "org:testorg is:issue state:closed label:bug label:priority:high "
            "-repo:testorg/private-repo -repo:testorg/test-repo"
        )
        assert query == expected

    def test_query_with_empty_exclusions(self) -> None:
        """Test query with empty exclusions list."""
        query = build_organization_query("testorg", excluded_repos=[])
        expected = "org:testorg is:issue state:open"
        assert query == expected

    def test_query_with_empty_labels(self) -> None:
        """Test query with empty labels list."""
        query = build_organization_query("testorg", labels=[])
        expected = "org:testorg is:issue state:open"
        assert query == expected
