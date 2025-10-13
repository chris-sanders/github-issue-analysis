"""GitHub issue analysis workflow using Temporal and PydanticAI agents."""

import logging
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from gh_analysis.temporal.models import AnalysisRequest, AnalysisResult

logger = logging.getLogger(__name__)


@workflow.defn
class GitHubAnalysisWorkflow:
    """Workflow for analyzing GitHub issues with AI agents."""

    def __init__(self):
        self._execution_start_time: Optional[float] = None
        self._fetch_duration: Optional[float] = None
        self._analysis_duration: Optional[float] = None

    @workflow.run
    async def run(self, request: AnalysisRequest) -> AnalysisResult:
        """Execute GitHub issue analysis workflow."""
        from gh_analysis.activities import fetch_github_issue
        from gh_analysis.agents.troubleshoot import gpt5_mini_medium_agent

        self._execution_start_time = workflow.now().timestamp()

        workflow.logger.info(
            f"Starting analysis: {request.repo_owner}/{request.repo_name}#{request.issue_number}"
        )

        # Fetch GitHub issue data
        fetch_start = workflow.now().timestamp()
        issue_data = await workflow.execute_activity(
            fetch_github_issue,
            args=[
                request.repo_owner,
                request.repo_name,
                request.issue_number,
                request.comment_limit,
            ],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=2),
            ),
        )
        self._fetch_duration = workflow.now().timestamp() - fetch_start
        workflow.logger.info(f"Fetched issue data in {self._fetch_duration:.2f}s")

        # Format issue context
        issue = issue_data.get("issue", {})
        context = "**Problem Description:**\n"
        context += f"Title: {issue.get('title', 'N/A')}\n"
        context += f"Body: {issue.get('body', 'N/A')}\n\n"

        if issue.get("comments"):
            context += "**Comments:**\n"
            for i, comment in enumerate(issue["comments"], 1):
                context += f"\nComment {i}:\n{comment.get('body', '')}\n"

        # Run TemporalAgent analysis (each tool call becomes activity)
        analysis_start = workflow.now().timestamp()
        result = await gpt5_mini_medium_agent.run(context)
        self._analysis_duration = workflow.now().timestamp() - analysis_start
        analysis = result.output

        workflow.logger.info(f"Completed analysis in {self._analysis_duration:.2f}s")

        total_time = workflow.now().timestamp() - self._execution_start_time

        return AnalysisResult(
            issue_number=request.issue_number,
            agent_used=request.agent_type,
            analysis=analysis,
            execution_time_seconds=total_time,
        )

    @workflow.query
    def get_status(self) -> dict:
        """Get current workflow execution status."""
        if self._execution_start_time is None:
            return {"status": "not_started"}

        current_time = workflow.now().timestamp()
        elapsed = current_time - self._execution_start_time

        return {
            "status": "running",
            "elapsed_seconds": elapsed,
            "fetch_completed": self._fetch_duration is not None,
            "analysis_completed": self._analysis_duration is not None,
        }
