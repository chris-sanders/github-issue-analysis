"""
Temporal activities for GitHub issue analysis.

Activities are the units of work in Temporal that can be retried independently.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from temporalio import activity

from loaders import GitHubIssueLoader

from .agents.troubleshoot import (
    BASE_BUNDLE_STORAGE,
    create_gpt5_high_agent,
    create_gpt5_medium_agent,
    create_gpt5_mini_high_agent,
)
from .models import TechnicalAnalysis

logger = logging.getLogger(__name__)


@activity.defn
async def cleanup_mcp_bundles() -> None:
    """
    Clean MCP bundle storage before workflow execution.

    Prevents stale bundles from previous workflow runs being reused.
    Must run as first activity in workflow before any MCP operations.
    """
    logger.info(f"Cleaning MCP bundle storage: {BASE_BUNDLE_STORAGE}")

    try:
        if BASE_BUNDLE_STORAGE.exists():
            # Remove all contents
            shutil.rmtree(BASE_BUNDLE_STORAGE)
            logger.info("Removed old bundle storage")

        # Recreate empty directory
        BASE_BUNDLE_STORAGE.mkdir(parents=True, exist_ok=True)
        logger.info("Created fresh bundle storage")
    except Exception as e:
        logger.error(f"Error cleaning bundle storage: {e}")
        # Don't fail - proceed even if cleanup fails


@activity.defn
async def fetch_github_issue(
    repo_owner: str,
    repo_name: str,
    issue_number: int,
    comment_limit: Optional[int] = None,
) -> dict:
    """
    Fetch GitHub issue data with comments.

    Uses SnowflakeIssueLoader from context-experiments utils.

    Args:
        repo_owner: Repository owner
        repo_name: Repository name
        issue_number: Issue number
        comment_limit: Optional limit on number of comments to fetch

    Returns:
        Dictionary with issue data including title, body, comments
    """
    logger.info(f"Fetching issue {repo_owner}/{repo_name}#{issue_number}")
    activity.heartbeat(f"Fetching {repo_owner}/{repo_name}#{issue_number}")

    # Use GitHubIssueLoader (from context-experiments loaders/)
    # Enable insecure_mode to bypass SSL cert validation (for debugging cert issues)
    insecure = os.getenv("SNOWFLAKE_INSECURE_MODE", "").lower() in ("1", "true", "yes")

    if comment_limit:
        loader = GitHubIssueLoader(
            number_of_comments=comment_limit, insecure_mode=insecure
        )
    else:
        loader = GitHubIssueLoader(insecure_mode=insecure)

    issues = await loader.load_issues([(repo_owner, repo_name, issue_number)])

    if not issues:
        raise ValueError(f"Issue {repo_owner}/{repo_name}#{issue_number} not found")

    issue = issues[0]
    logger.info(
        f"Fetched issue with {len(issue.get('issue', {}).get('comments', []))} comments"
    )

    return issue


@activity.defn
async def run_agent_analysis(issue_data: dict, agent_type: str) -> TechnicalAnalysis:
    """
    Run agent analysis on GitHub issue.

    This activity creates the agent and runs it. In the current implementation,
    all MCP tool calls happen within this single activity.

    Future improvement: Use TemporalAgent to make each tool call a separate activity.

    Args:
        issue_data: Issue data from fetch_github_issue
        agent_type: Type of agent to use

    Returns:
        TechnicalAnalysis result from agent
    """
    logger.info(f"Running {agent_type} analysis")
    activity.heartbeat(f"Starting {agent_type} analysis")

    # Create agent based on type
    # Note: gpt5_mini_medium uses TemporalAgent (v2), not this activity
    agent_creators = {
        "gpt5_mini_high": create_gpt5_mini_high_agent,
        "gpt5_medium": create_gpt5_medium_agent,
        "gpt5_high": create_gpt5_high_agent,
    }

    if agent_type not in agent_creators:
        raise ValueError(f"Unknown agent type: {agent_type}")

    agent = agent_creators[agent_type]()

    # Format issue context
    issue = issue_data.get("issue", {})
    context = f"**Problem Description:**\n"
    context += f"Title: {issue.get('title', 'N/A')}\n"
    context += f"Body: {issue.get('body', 'N/A')}\n\n"

    if issue.get("comments"):
        context += "**Comments:**\n"
        for i, comment in enumerate(issue["comments"], 1):
            context += f"\nComment {i}:\n{comment.get('body', '')}\n"

    logger.info(f"Running agent with context length: {len(context)}")

    # Run agent with MCP server context
    async with agent:
        activity.heartbeat("Agent running with MCP tools")
        result = await agent.run(context)
        activity.heartbeat("Agent completed")

    logger.info(
        f"Analysis complete: {result.output.status if hasattr(result.output, 'status') else 'unknown'}"
    )

    return result.output
