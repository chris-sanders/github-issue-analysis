"""Main Temporal worker for gh-analysis.

Registers workflows, activities, and TemporalAgents.
Used by TemporalManager for CLI-managed execution.
"""

import logging

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin

# Import workflows
from gh_analysis.workflows import TroubleshootWorkflow

# Import activities  
from gh_analysis.activities import fetch_github_issue, run_agent_analysis

# Import agents (for TemporalAgent registration)
from gh_analysis.agents import AVAILABLE_AGENTS

logger = logging.getLogger(__name__)


def create_worker(
    client: Client, task_queue: str = "gh-analysis-queue"
) -> Worker:
    """Create gh-analysis worker with all workflows and activities registered.

    Args:
        client: Temporal client
        task_queue: Task queue name

    Returns:
        Configured Worker instance
    """
    logger.info("Creating gh-analysis worker...")

    # Register all agents
    agent_list = list(AVAILABLE_AGENTS.values())

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[TroubleshootWorkflow],
        activities=[fetch_github_issue, run_agent_analysis],
        # TemporalAgent activities registered automatically via PydanticAIPlugin
    )

    logger.info(f"Worker created with {len(agent_list)} agents registered")
    return worker
