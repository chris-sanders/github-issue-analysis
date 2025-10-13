"""GitHub search functionality and query building."""

from typing import TYPE_CHECKING

from .models import GitHubIssue

if TYPE_CHECKING:
    from .client import GitHubClient


def build_exclusion_list(
    exclude_repo: list[str] | None, exclude_repos: str | None
) -> list[str]:
    """Build combined list of repositories to exclude.

    Args:
        exclude_repo: List of individual repository names to exclude
        exclude_repos: Comma-separated string of repository names to exclude

    Returns:
        List of unique repository names to exclude, with empty strings filtered out

    Example:
        >>> build_exclusion_list(["repo1", "repo2"], "repo3,repo4")
        ["repo1", "repo2", "repo3", "repo4"]
    """
    exclusions = []

    # Add individual exclusions
    if exclude_repo:
        exclusions.extend(exclude_repo)

    # Add comma-separated exclusions
    if exclude_repos:
        exclusions.extend([repo.strip() for repo in exclude_repos.split(",")])

    # Remove duplicates and empty strings
    return list(set(filter(None, exclusions)))


def build_organization_query(
    org: str,
    labels: list[str] | None = None,
    state: str = "open",
    excluded_repos: list[str] | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
) -> str:
    """Build GitHub search query for organization with exclusions and date filtering.

    Args:
        org: Organization name
        labels: List of label names to filter by
        state: Issue state (open, closed, all)
        excluded_repos: List of repository names to exclude
        created_after: ISO date string to filter issues created after this date
        created_before: ISO date string to filter issues created before this date
        updated_after: ISO date string to filter issues updated after this date
        updated_before: ISO date string to filter issues updated before this date

    Returns:
        GitHub search query string with exclusions and date filtering

    Example:
        >>> build_organization_query(
        ...     "myorg", ["bug"], "closed", ["private-repo"], "2024-01-01"
        ... )
        "org:myorg is:issue state:closed label:bug -repo:myorg/private-repo " \\
        "created:>2024-01-01"
    """
    query_parts = [f"org:{org}", "is:issue"]

    if state != "all":
        query_parts.append(f"state:{state}")

    if labels:
        for label in labels:
            query_parts.append(f"label:{label}")

    # Add repository exclusions
    if excluded_repos:
        for repo in excluded_repos:
            query_parts.append(f"-repo:{org}/{repo}")

    # Date filtering
    if created_after:
        query_parts.append(f"created:>{created_after}")
    if created_before:
        query_parts.append(f"created:<{created_before}")
    if updated_after:
        query_parts.append(f"updated:>{updated_after}")
    if updated_before:
        query_parts.append(f"updated:<{updated_before}")

    return " ".join(query_parts)


class GitHubSearcher:
    """High-level interface for searching GitHub issues."""

    def __init__(self, client: "GitHubClient"):
        """Initialize searcher with GitHub client.

        Args:
            client: Authenticated GitHubClient instance
        """
        self.client = client

    def search_repository_issues(
        self,
        org: str,
        repo: str,
        labels: list[str] | None = None,
        state: str = "open",
        limit: int = 10,
        created_after: str | None = None,
        created_before: str | None = None,
        updated_after: str | None = None,
        updated_before: str | None = None,
    ) -> list[GitHubIssue]:
        """Search for issues in a specific repository.

        Args:
            org: Organization name
            repo: Repository name
            labels: List of label names to filter by
            state: Issue state (open, closed, all)
            limit: Maximum number of issues to return
            created_after: ISO date string to filter issues created after this date
            created_before: ISO date string to filter issues created before this date
            updated_after: ISO date string to filter issues updated after this date
            updated_before: ISO date string to filter issues updated before this date

        Returns:
            List of GitHubIssue objects with full details including comments
        """
        return self.client.search_issues(
            org=org,
            repo=repo,
            labels=labels,
            state=state,
            limit=limit,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
        )

    def get_single_issue(self, org: str, repo: str, issue_number: int) -> GitHubIssue:
        """Get a single issue with all details.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number

        Returns:
            GitHubIssue object with full details including comments
        """
        return self.client.get_issue(org, repo, issue_number)

    def search_organization_issues(
        self,
        org: str,
        labels: list[str] | None = None,
        state: str = "open",
        limit: int = 10,
        created_after: str | None = None,
        created_before: str | None = None,
        updated_after: str | None = None,
        updated_before: str | None = None,
        excluded_repos: list[str] | None = None,
    ) -> list[GitHubIssue]:
        """Search for issues across all repositories in an organization.

        Args:
            org: Organization name
            labels: List of label names to filter by
            state: Issue state (open, closed, all)
            limit: Maximum number of issues to return
            created_after: ISO date string to filter issues created after this date
            created_before: ISO date string to filter issues created before this date
            updated_after: ISO date string to filter issues updated after this date
            updated_before: ISO date string to filter issues updated before this date
            excluded_repos: List of repository names to exclude

        Returns:
            List of GitHubIssue objects with full details including comments
        """
        return self.client.search_organization_issues(
            org=org,
            labels=labels,
            state=state,
            limit=limit,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            excluded_repos=excluded_repos,
        )


def build_github_query(
    org: str,
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
) -> str:
    """Build a GitHub search query string.

    Args:
        org: Organization name
        repo: Repository name
        labels: List of label names to filter by
        state: Issue state (open, closed, all)
        created_after: ISO date string to filter issues created after this date
        created_before: ISO date string to filter issues created before this date
        updated_after: ISO date string to filter issues updated after this date
        updated_before: ISO date string to filter issues updated before this date

    Returns:
        GitHub search query string

    Example:
        >>> build_github_query(
        ...     "test-org", "test-repo", ["bug"], "open", "2024-01-01", "2024-12-31"
        ... )
        "repo:test-org/test-repo is:issue state:open label:bug " \\
        "created:>2024-01-01 created:<2024-12-31"
    """
    query_parts = [f"repo:{org}/{repo}", "is:issue"]

    if state != "all":
        query_parts.append(f"state:{state}")

    if labels:
        for label in labels:
            query_parts.append(f"label:{label}")

    # Date filtering
    if created_after:
        query_parts.append(f"created:>{created_after}")
    if created_before:
        query_parts.append(f"created:<{created_before}")
    if updated_after:
        query_parts.append(f"updated:>{updated_after}")
    if updated_before:
        query_parts.append(f"updated:<{updated_before}")

    return " ".join(query_parts)


def build_github_organization_query(
    org: str,
    labels: list[str] | None = None,
    state: str = "open",
    created_after: str | None = None,
    created_before: str | None = None,
    updated_after: str | None = None,
    updated_before: str | None = None,
) -> str:
    """Build a GitHub search query string for organization-wide search.

    Args:
        org: Organization name
        labels: List of label names to filter by
        state: Issue state (open, closed, all)
        created_after: ISO date string to filter issues created after this date
        created_before: ISO date string to filter issues created before this date
        updated_after: ISO date string to filter issues updated after this date
        updated_before: ISO date string to filter issues updated before this date

    Returns:
        GitHub search query string

    Example:
        >>> build_github_organization_query("test-org", ["bug"], "open", "2024-01-01")
        "org:test-org is:issue state:open label:bug created:>2024-01-01"
    """
    query_parts = [f"org:{org}", "is:issue"]

    if state != "all":
        query_parts.append(f"state:{state}")

    if labels:
        for label in labels:
            query_parts.append(f"label:{label}")

    # Date filtering
    if created_after:
        query_parts.append(f"created:>{created_after}")
    if created_before:
        query_parts.append(f"created:<{created_before}")
    if updated_after:
        query_parts.append(f"updated:>{updated_after}")
    if updated_before:
        query_parts.append(f"updated:<{updated_before}")

    return " ".join(query_parts)
