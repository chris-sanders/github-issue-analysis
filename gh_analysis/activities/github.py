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

    # Use existing GitHubClient
    client = GitHubClient()

    try:
        # Fetch issue with comments
        issue = await client.get_issue(org, repo, issue_number)

        activity.logger.info(f"Fetched issue with {len(issue.get('comments', []))} comments")
        return issue

    except Exception as e:
        activity.logger.error(f"Failed to fetch issue: {e}")
        raise
