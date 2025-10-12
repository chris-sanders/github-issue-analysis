"""Troubleshooting workflow using Temporal orchestration."""

import logging
from datetime import timedelta
from typing import Any

from temporalio import workflow

# Import activities at module level (required for Temporal sandbox)
with workflow.unsafe.imports_passed_through():
    from gh_analysis.activities.analysis import run_agent_analysis
    from gh_analysis.activities.github import fetch_github_issue

logger = logging.getLogger(__name__)


@workflow.defn
class TroubleshootWorkflow:
    """Workflow for troubleshooting GitHub issues with AI agents."""

    @workflow.run
    async def run(
        self, org: str, repo: str, issue_number: int, agent_name: str = "gpt5_medium"
    ) -> dict[str, Any]:
        """Execute troubleshooting workflow.

        Args:
            org: GitHub organization
            repo: GitHub repository
            issue_number: Issue number
            agent_name: Name of agent to use (gpt5_medium, gpt5_high, etc.)

        Returns:
            Analysis result dictionary
        """
        workflow.logger.info(
            f"Starting troubleshoot workflow: {org}/{repo}#{issue_number} with {agent_name}"
        )

        # Activity 1: Fetch GitHub issue
        issue_data = await workflow.execute_activity(
            fetch_github_issue,
            args=(org, repo, issue_number),
            start_to_close_timeout=timedelta(minutes=5),
        )

        # Activity 2: Run agent analysis (TemporalAgent - tool calls become activities)
        result = await workflow.execute_activity(
            run_agent_analysis,
            args=(issue_data, agent_name),
            start_to_close_timeout=timedelta(minutes=30),
        )

        workflow.logger.info("Troubleshoot workflow completed")
        return result
