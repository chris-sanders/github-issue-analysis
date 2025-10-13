"""
GitHub issue analysis workflow using Temporal and PydanticAI agents.

This workflow orchestrates the fetching and analysis of GitHub issues using
troubleshooting agents with MCP tool access.
"""

import logging
from datetime import timedelta
from typing import Optional

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

from ..models import TechnicalAnalysis

logger = logging.getLogger(__name__)


class AnalysisRequest(BaseModel):
    """Request for GitHub issue analysis."""

    repo_owner: str
    repo_name: str
    issue_number: int
    agent_type: str = "gpt5_mini_medium"  # Agent to use
    comment_limit: Optional[int] = None  # Limit number of comments


class AnalysisResult(BaseModel):
    """Result from GitHub issue analysis."""

    issue_number: int
    agent_used: str
    analysis: TechnicalAnalysis
    execution_time_seconds: float


@workflow.defn
class GitHubAnalysisWorkflow:
    """
    Workflow for analyzing GitHub issues with AI agents.

    This workflow:
    1. Fetches GitHub issue data with comments
    2. Runs agent analysis with MCP tools
    3. Returns structured analysis result
    """

    def __init__(self):
        self._execution_start_time: Optional[float] = None
        self._fetch_duration: Optional[float] = None
        self._analysis_duration: Optional[float] = None
        self._tool_call_count: int = 0

    @workflow.run
    async def run(self, request: AnalysisRequest) -> AnalysisResult:
        """Execute GitHub issue analysis workflow."""
        from ..activities import (
            cleanup_mcp_bundles,
            fetch_github_issue,
            run_agent_analysis,
        )
        from ..agents.troubleshoot import gpt5_mini_medium_agent

        self._execution_start_time = workflow.now().timestamp()

        workflow.logger.info(
            f"Starting analysis: {request.repo_owner}/{request.repo_name}#{request.issue_number} "
            f"with {request.agent_type}"
        )

        # Clean MCP bundle storage first (prevents cross-workflow contamination)
        await workflow.execute_activity(
            cleanup_mcp_bundles,
            start_to_close_timeout=timedelta(seconds=30),
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

        # Check if using TemporalAgent (v2) or activity-based (v1)
        if request.agent_type == "gpt5_mini_medium":
            # V2 Pattern: Use TemporalAgent with persistent bundle storage
            from exp.exp05_temporal.agents.troubleshoot import gpt5_mini_medium_agent

            workflow.logger.info(
                "Using TemporalAgent (v2) with persistent bundle storage"
            )

            # Format issue context
            issue = issue_data.get("issue", {})
            context = f"**Problem Description:**\n"
            context += f"Title: {issue.get('title', 'N/A')}\n"
            context += f"Body: {issue.get('body', 'N/A')}\n\n"

            if issue.get("comments"):
                context += "**Comments:**\n"
                for i, comment in enumerate(issue["comments"], 1):
                    context += f"\nComment {i}:\n{comment.get('body', '')}\n"

            analysis_start = workflow.now().timestamp()
            result = await gpt5_mini_medium_agent.run(context)
            self._analysis_duration = workflow.now().timestamp() - analysis_start
            analysis = result.output
        else:
            # V1 Pattern: Run agent in activity (fallback for other agents)
            workflow.logger.info("Using activity-based agent (v1)")
            analysis_start = workflow.now().timestamp()
            analysis = await workflow.execute_activity(
                run_agent_analysis,
                args=[issue_data, request.agent_type],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=2,
                    backoff_coefficient=1.5,
                    initial_interval=timedelta(seconds=10),
                ),
            )
            self._analysis_duration = workflow.now().timestamp() - analysis_start

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

        status = {
            "status": "running",
            "elapsed_seconds": elapsed,
            "fetch_completed": self._fetch_duration is not None,
            "analysis_completed": self._analysis_duration is not None,
            "tool_call_count": self._tool_call_count,
        }

        if self._fetch_duration:
            status["fetch_duration_seconds"] = self._fetch_duration
        if self._analysis_duration:
            status["analysis_duration_seconds"] = self._analysis_duration

        return status
