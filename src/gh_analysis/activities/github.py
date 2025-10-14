"""GitHub and agent activities for Temporal workflows."""

import logging
import shutil
from pathlib import Path
from typing import Any

from temporalio import activity

from gh_analysis.ai.models import TechnicalAnalysis
from gh_analysis.github_client import GitHubClient

logger = logging.getLogger(__name__)

BASE_BUNDLE_STORAGE = Path("/tmp/mcp-bundles")


@activity.defn
async def cleanup_mcp_bundles() -> None:
    """Clean MCP bundle storage before workflow."""
    logger.info(f"Cleaning MCP bundle storage: {BASE_BUNDLE_STORAGE}")
    try:
        if BASE_BUNDLE_STORAGE.exists():
            shutil.rmtree(BASE_BUNDLE_STORAGE)
            BASE_BUNDLE_STORAGE.mkdir(parents=True, exist_ok=True)
            logger.info("✓ Bundle storage cleaned")
    except Exception as e:
        logger.warning(f"Failed to clean bundles: {e}")


@activity.defn
async def fetch_github_issue(
    repo_owner: str, repo_name: str, issue_number: int, comment_limit: int | None = None
) -> dict[str, Any]:
    """Fetch GitHub issue with comments."""
    logger.info(f"Fetching {repo_owner}/{repo_name}#{issue_number}")

    client = GitHubClient()
    issue = client.get_issue(repo_owner, repo_name, issue_number)
    issue_dict = issue.model_dump()

    if comment_limit and issue_dict.get("comments"):
        issue_dict["comments"] = issue_dict["comments"][:comment_limit]

    return {"issue": issue_dict, "org": repo_owner, "repo": repo_name}


@activity.defn
async def run_agent_analysis(
    issue_data: dict[str, Any], agent_type: str
) -> TechnicalAnalysis:
    """Run agent analysis (fallback)."""
    logger.info(f"Running {agent_type} analysis")
    raise NotImplementedError("Use TemporalAgent directly in workflow")
