"""GitHub API client using PyGitHub."""

import os
import time

from github import Github
from github.GithubException import RateLimitExceededException, UnknownObjectException
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Label import Label
from github.NamedUser import NamedUser
from github.Repository import Repository
from rich.console import Console

from .attachments import AttachmentDownloader
from .models import GitHubComment, GitHubIssue, GitHubLabel, GitHubUser
from .search import build_github_query

console = Console()


class GitHubClient:
    """GitHub API client with rate limiting and authentication."""

    def __init__(self, token: str | None = None):
        """Initialize GitHub client with authentication.

        Args:
            token: GitHub personal access token. If None, reads from
                GITHUB_TOKEN env var.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError(
                "GitHub token is required. Set GITHUB_TOKEN environment variable."
            )

        self.github = Github(self.token)
        self._check_rate_limit()

    def _check_rate_limit(self) -> None:
        """Check rate limit and sleep if necessary."""
        try:
            rate_limit = self.github.get_rate_limit()
            remaining = rate_limit.core.remaining
            console.print(f"GitHub API rate limit: {remaining} requests remaining")

            if remaining < 10:
                reset_time = rate_limit.core.reset.timestamp()
                sleep_time = reset_time - time.time() + 1
                console.print(
                    f"Rate limit low, sleeping for {sleep_time:.1f} seconds..."
                )
                time.sleep(sleep_time)

        except Exception:
            # Silently continue if rate limit check fails - it's not critical
            pass

    def _convert_user(self, github_user: NamedUser) -> GitHubUser:
        """Convert PyGitHub user to our model."""
        return GitHubUser(login=github_user.login, id=github_user.id)

    def _convert_label(self, github_label: Label) -> GitHubLabel:
        """Convert PyGitHub label to our model."""
        return GitHubLabel(
            name=github_label.name,
            color=github_label.color,
            description=github_label.description,
        )

    def _convert_comment(self, github_comment: IssueComment) -> GitHubComment:
        """Convert PyGitHub comment to our model."""
        return GitHubComment(
            id=github_comment.id,
            user=self._convert_user(github_comment.user),
            body=github_comment.body,
            created_at=github_comment.created_at,
            updated_at=github_comment.updated_at,
        )

    def _convert_issue(self, github_issue: Issue) -> GitHubIssue:
        """Convert PyGitHub issue to our model."""
        labels = [self._convert_label(label) for label in github_issue.labels]

        # Extract repository name from the issue's repository
        repository_name = None
        if hasattr(github_issue, "repository") and github_issue.repository:
            repository_name = github_issue.repository.name

        # Fetch comments for the issue
        comments = []
        try:
            for comment in github_issue.get_comments():
                comments.append(self._convert_comment(comment))
        except Exception as e:
            console.print(
                f"Warning: Could not fetch comments for issue "
                f"#{github_issue.number}: {e}"
            )

        return GitHubIssue(
            number=github_issue.number,
            title=github_issue.title,
            body=github_issue.body,
            state=github_issue.state,
            labels=labels,
            user=self._convert_user(github_issue.user),
            comments=comments,
            created_at=github_issue.created_at,
            updated_at=github_issue.updated_at,
            repository_name=repository_name,
        )

    def get_repository(self, org: str, repo: str) -> Repository:
        """Get repository object."""
        try:
            return self.github.get_repo(f"{org}/{repo}")
        except UnknownObjectException:
            raise ValueError(f"Repository {org}/{repo} not found")

    def get_issue(self, org: str, repo: str, issue_number: int) -> GitHubIssue:
        """Get a specific issue with all its details."""
        self._check_rate_limit()

        repository = self.get_repository(org, repo)
        github_issue = repository.get_issue(issue_number)

        return self._convert_issue(github_issue)

    def search_issues(
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
        """Search for issues in a repository.

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
            List of GitHubIssue objects
        """
        self._check_rate_limit()

        # Build search query using the centralized function
        query = build_github_query(
            org=org,
            repo=repo,
            labels=labels,
            state=state,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
        )
        console.print(f"Searching with query: {query}")

        try:
            # Use GitHub search API
            issues = self.github.search_issues(query)

            # Convert to our models, limiting results
            result_issues = []
            for i, github_issue in enumerate(issues):
                if i >= limit:
                    break

                try:
                    result_issues.append(self._convert_issue(github_issue))
                    console.print(
                        f"Processed issue #{github_issue.number}: {github_issue.title}"
                    )
                except Exception as e:
                    console.print(f"Error processing issue #{github_issue.number}: {e}")
                    continue

            return result_issues

        except RateLimitExceededException:
            console.print("Rate limit exceeded, waiting...")
            time.sleep(60)
            return self.search_issues(
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
        except Exception as e:
            console.print(f"Error searching issues: {e}")
            raise

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
            List of GitHubIssue objects
        """
        self._check_rate_limit()

        # Import here to avoid circular import
        from .search import build_organization_query

        # Build search query for organization-wide search with exclusions and dates
        query = build_organization_query(
            org=org,
            labels=labels,
            state=state,
            excluded_repos=excluded_repos,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
        )
        console.print(f"Searching with query: {query}")

        try:
            # Use GitHub search API
            issues = self.github.search_issues(query)

            # Convert to our models, limiting results
            result_issues = []
            for i, github_issue in enumerate(issues):
                if i >= limit:
                    break

                try:
                    result_issues.append(self._convert_issue(github_issue))
                    console.print(
                        f"Processed issue #{github_issue.number}: {github_issue.title}"
                    )
                except Exception as e:
                    console.print(f"Error processing issue #{github_issue.number}: {e}")
                    continue

            return result_issues

        except RateLimitExceededException:
            console.print("Rate limit exceeded, waiting...")
            time.sleep(60)
            return self.search_organization_issues(
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
        except Exception as e:
            console.print(f"Error searching organization issues: {e}")
            raise

    def process_issue_attachments(self, issue: GitHubIssue) -> GitHubIssue:
        """Process and detect all attachments in an issue.

        Args:
            issue: GitHubIssue object to process

        Returns:
            Updated GitHubIssue object with detected attachments
        """
        if not self.token:
            raise ValueError("GitHub token is required for attachment processing")
        downloader = AttachmentDownloader(self.token)
        return downloader.process_issue_attachments(issue)

    def update_issue_labels(
        self, org: str, repo: str, issue_number: int, labels: list[str]
    ) -> bool:
        """Update issue labels by replacing all current labels.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number
            labels: List of label names to set on the issue

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If repository or issue not found
            Exception: For other API errors
        """
        self._check_rate_limit()

        try:
            repository = self.get_repository(org, repo)
            github_issue = repository.get_issue(issue_number)

            # Set new labels (this replaces all existing labels)
            github_issue.set_labels(*labels)

            console.print(f"Updated labels for issue #{issue_number}: {labels}")
            return True

        except UnknownObjectException:
            raise ValueError(f"Issue #{issue_number} not found in {org}/{repo}")
        except RateLimitExceededException:
            console.print("Rate limit exceeded during label update, waiting...")
            time.sleep(60)
            return self.update_issue_labels(org, repo, issue_number, labels)
        except Exception as e:
            console.print(f"Error updating labels for issue #{issue_number}: {e}")
            raise

    def add_issue_comment(
        self, org: str, repo: str, issue_number: int, comment: str
    ) -> bool:
        """Add a comment to an issue.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number
            comment: Comment text to add

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If repository or issue not found
            Exception: For other API errors
        """
        self._check_rate_limit()

        try:
            repository = self.get_repository(org, repo)
            github_issue = repository.get_issue(issue_number)

            # Create the comment
            github_issue.create_comment(comment)

            console.print(f"Added comment to issue #{issue_number}")
            return True

        except UnknownObjectException:
            raise ValueError(f"Issue #{issue_number} not found in {org}/{repo}")
        except RateLimitExceededException:
            console.print("Rate limit exceeded during comment creation, waiting...")
            time.sleep(60)
            return self.add_issue_comment(org, repo, issue_number, comment)
        except Exception as e:
            console.print(f"Error adding comment to issue #{issue_number}: {e}")
            raise

    def get_issue_labels(self, org: str, repo: str, issue_number: int) -> list[str]:
        """Get current labels for an issue.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number

        Returns:
            List of current label names

        Raises:
            ValueError: If repository or issue not found
            Exception: For other API errors
        """
        self._check_rate_limit()

        try:
            repository = self.get_repository(org, repo)
            github_issue = repository.get_issue(issue_number)

            return [label.name for label in github_issue.labels]

        except UnknownObjectException:
            raise ValueError(f"Issue #{issue_number} not found in {org}/{repo}")
        except RateLimitExceededException:
            console.print("Rate limit exceeded during label fetch, waiting...")
            time.sleep(60)
            return self.get_issue_labels(org, repo, issue_number)
        except Exception as e:
            console.print(f"Error fetching labels for issue #{issue_number}: {e}")
            raise
