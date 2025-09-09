"""Tests for GitHub search query building with date filtering."""

from unittest.mock import Mock

from gh_analysis.github_client.search import (
    GitHubSearcher,
    build_github_organization_query,
    build_github_query,
)


class TestBuildGithubQuery:
    """Test repository-specific GitHub query building with date filtering."""

    def test_basic_query(self) -> None:
        """Test building basic repository query."""
        result = build_github_query("test-org", "test-repo")
        expected = "repo:test-org/test-repo is:issue state:open"
        assert result == expected

    def test_query_with_labels(self) -> None:
        """Test building query with labels."""
        result = build_github_query("test-org", "test-repo", labels=["bug", "feature"])
        expected = "repo:test-org/test-repo is:issue state:open label:bug label:feature"
        assert result == expected

    def test_query_with_state(self) -> None:
        """Test building query with different states."""
        result = build_github_query("test-org", "test-repo", state="closed")
        expected = "repo:test-org/test-repo is:issue state:closed"
        assert result == expected

        result = build_github_query("test-org", "test-repo", state="all")
        expected = "repo:test-org/test-repo is:issue"
        assert result == expected

    def test_query_with_created_after(self) -> None:
        """Test building query with created_after date."""
        result = build_github_query("test-org", "test-repo", created_after="2024-01-01")
        expected = "repo:test-org/test-repo is:issue state:open created:>2024-01-01"
        assert result == expected

    def test_query_with_created_before(self) -> None:
        """Test building query with created_before date."""
        result = build_github_query(
            "test-org", "test-repo", created_before="2024-12-31"
        )
        expected = "repo:test-org/test-repo is:issue state:open created:<2024-12-31"
        assert result == expected

    def test_query_with_created_date_range(self) -> None:
        """Test building query with created date range."""
        result = build_github_query(
            "test-org",
            "test-repo",
            created_after="2024-01-01",
            created_before="2024-12-31",
        )
        expected = (
            "repo:test-org/test-repo is:issue state:open "
            "created:>2024-01-01 created:<2024-12-31"
        )
        assert result == expected

    def test_query_with_updated_after(self) -> None:
        """Test building query with updated_after date."""
        result = build_github_query("test-org", "test-repo", updated_after="2024-06-01")
        expected = "repo:test-org/test-repo is:issue state:open updated:>2024-06-01"
        assert result == expected

    def test_query_with_updated_before(self) -> None:
        """Test building query with updated_before date."""
        result = build_github_query(
            "test-org", "test-repo", updated_before="2024-06-30"
        )
        expected = "repo:test-org/test-repo is:issue state:open updated:<2024-06-30"
        assert result == expected

    def test_query_with_updated_date_range(self) -> None:
        """Test building query with updated date range."""
        result = build_github_query(
            "test-org",
            "test-repo",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )
        expected = (
            "repo:test-org/test-repo is:issue state:open "
            "updated:>2024-06-01 updated:<2024-06-30"
        )
        assert result == expected

    def test_query_with_all_date_filters(self) -> None:
        """Test building query with all date filter combinations."""
        result = build_github_query(
            "test-org",
            "test-repo",
            labels=["bug"],
            state="closed",
            created_after="2024-01-01",
            created_before="2024-12-31",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )
        expected = (
            "repo:test-org/test-repo is:issue state:closed label:bug "
            "created:>2024-01-01 created:<2024-12-31 "
            "updated:>2024-06-01 updated:<2024-06-30"
        )
        assert result == expected

    def test_query_with_none_dates(self) -> None:
        """Test building query with None date values."""
        result = build_github_query(
            "test-org",
            "test-repo",
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
        )
        expected = "repo:test-org/test-repo is:issue state:open"
        assert result == expected


class TestBuildGithubOrganizationQuery:
    """Test organization-wide GitHub query building with date filtering."""

    def test_basic_organization_query(self) -> None:
        """Test building basic organization query."""
        result = build_github_organization_query("test-org")
        expected = "org:test-org is:issue state:open"
        assert result == expected

    def test_organization_query_with_labels(self) -> None:
        """Test building organization query with labels."""
        result = build_github_organization_query("test-org", labels=["bug", "feature"])
        expected = "org:test-org is:issue state:open label:bug label:feature"
        assert result == expected

    def test_organization_query_with_state(self) -> None:
        """Test building organization query with different states."""
        result = build_github_organization_query("test-org", state="closed")
        expected = "org:test-org is:issue state:closed"
        assert result == expected

        result = build_github_organization_query("test-org", state="all")
        expected = "org:test-org is:issue"
        assert result == expected

    def test_organization_query_with_created_after(self) -> None:
        """Test building organization query with created_after date."""
        result = build_github_organization_query("test-org", created_after="2024-01-01")
        expected = "org:test-org is:issue state:open created:>2024-01-01"
        assert result == expected

    def test_organization_query_with_all_date_filters(self) -> None:
        """Test building organization query with all date filter combinations."""
        result = build_github_organization_query(
            "test-org",
            labels=["bug"],
            state="closed",
            created_after="2024-01-01",
            created_before="2024-12-31",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )
        expected = (
            "org:test-org is:issue state:closed label:bug "
            "created:>2024-01-01 created:<2024-12-31 "
            "updated:>2024-06-01 updated:<2024-06-30"
        )
        assert result == expected


class TestGitHubSearcher:
    """Test GitHubSearcher class with date filtering integration."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = Mock()
        self.searcher = GitHubSearcher(self.mock_client)

    def test_search_repository_issues_with_dates(self) -> None:
        """Test repository search with date parameters."""
        self.setUp()

        # Mock the client response
        self.mock_client.search_issues.return_value = []

        # Call the method with date parameters
        self.searcher.search_repository_issues(
            org="test-org",
            repo="test-repo",
            labels=["bug"],
            state="open",
            limit=10,
            created_after="2024-01-01",
            created_before="2024-12-31",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )

        # Verify client was called with all parameters
        self.mock_client.search_issues.assert_called_once_with(
            org="test-org",
            repo="test-repo",
            labels=["bug"],
            state="open",
            limit=10,
            created_after="2024-01-01",
            created_before="2024-12-31",
            updated_after="2024-06-01",
            updated_before="2024-06-30",
        )

    def test_search_organization_issues_with_dates(self) -> None:
        """Test organization search with date parameters."""
        self.setUp()

        # Mock the client response
        self.mock_client.search_organization_issues.return_value = []

        # Call the method with date parameters
        self.searcher.search_organization_issues(
            org="test-org",
            labels=["bug"],
            state="closed",
            limit=20,
            created_after="2024-01-01",
            updated_after="2024-06-01",
        )

        # Verify client was called with all parameters
        self.mock_client.search_organization_issues.assert_called_once_with(
            org="test-org",
            labels=["bug"],
            state="closed",
            limit=20,
            created_after="2024-01-01",
            created_before=None,
            updated_after="2024-06-01",
            updated_before=None,
            excluded_repos=None,
        )

    def test_search_repository_issues_no_dates(self) -> None:
        """Test repository search without date parameters (backward compatibility)."""
        self.setUp()

        # Mock the client response
        self.mock_client.search_issues.return_value = []

        # Call the method without date parameters
        self.searcher.search_repository_issues(
            org="test-org", repo="test-repo", labels=["feature"], state="all", limit=5
        )

        # Verify client was called with None for date parameters
        self.mock_client.search_issues.assert_called_once_with(
            org="test-org",
            repo="test-repo",
            labels=["feature"],
            state="all",
            limit=5,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
        )

    def test_search_organization_issues_no_dates(self) -> None:
        """Test organization search without date parameters (backward compatibility)."""
        self.setUp()

        # Mock the client response
        self.mock_client.search_organization_issues.return_value = []

        # Call the method without date parameters
        self.searcher.search_organization_issues(
            org="test-org", labels=None, state="open", limit=15
        )

        # Verify client was called with None for date parameters
        self.mock_client.search_organization_issues.assert_called_once_with(
            org="test-org",
            labels=None,
            state="open",
            limit=15,
            created_after=None,
            created_before=None,
            updated_after=None,
            updated_before=None,
            excluded_repos=None,
        )
