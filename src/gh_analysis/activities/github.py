"""GitHub and agent activities for Temporal workflows."""

import logging
from typing import Any

from temporalio import activity

from gh_analysis.ai.models import TechnicalAnalysis
from gh_analysis.github_client import GitHubClient

logger = logging.getLogger(__name__)


@activity.defn
async def fetch_github_issue(
    org: str, repo: str, issue_number: int, comment_limit: int | None = None
) -> dict[str, Any]:
    """Fetch GitHub issue with comments.

    Args:
        org: GitHub organization
        repo: Repository name
        issue_number: Issue number
        comment_limit: Limit on comments (None = all)

    Returns:
        Dict with issue data
    """
    logger.info(f"Fetching {org}/{repo}#{issue_number}")

    client = GitHubClient()
    issue = client.get_issue(org, repo, issue_number)
    issue_dict = issue.model_dump()

    if comment_limit and issue_dict.get("comments"):
        issue_dict["comments"] = issue_dict["comments"][:comment_limit]

    return {"issue": issue_dict, "org": org, "repo": repo}


@activity.defn
async def run_agent_analysis(
    issue_data: dict[str, Any], agent_type: str
) -> TechnicalAnalysis:
    """Run agent analysis on issue (fallback for non-TemporalAgent agents).

    Args:
        issue_data: Issue data from fetch_github_issue
        agent_type: Agent type identifier

    Returns:
        TechnicalAnalysis result
    """
    logger.info(f"Running {agent_type} analysis")
    # This is a placeholder - exp05 uses TemporalAgent directly in workflow
    # keeping for backwards compatibility
    raise NotImplementedError("Use TemporalAgent directly in workflow")
