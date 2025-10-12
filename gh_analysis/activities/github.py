"""GitHub data fetching activities."""

import logging
from typing import Any

from temporalio import activity

from gh_analysis.github_client.client import GitHubClient

logger = logging.getLogger(__name__)


@activity.defn
async def fetch_github_issue(org: str, repo: str, issue_number: int) -> dict[str, Any]:
    """Fetch GitHub issue data as Temporal activity.

    Args:
        org: GitHub organization
        repo: GitHub repository
        issue_number: Issue number

    Returns:
        Issue data dictionary

    Raises:
        ValueError: If issue not found
    """
    activity.logger.info(f"Fetching issue: {org}/{repo}#{issue_number}")

    # Use existing GitHub search (synchronous)
    from gh_analysis.github_client.search import GitHubSearcher

    client = GitHubClient()
    searcher = GitHubSearcher(client)

    try:
        # Fetch issue with comments (synchronous call)
        issue = searcher.get_single_issue(org, repo, issue_number)

        comments_count = len(issue.comments) if hasattr(issue, "comments") else 0
        activity.logger.info(f"Fetched issue with {comments_count} comments")

        # Convert to dict
        return issue.model_dump()

    except Exception as e:
        activity.logger.error(f"Failed to fetch issue: {e}")
        raise
