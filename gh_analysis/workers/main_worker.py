"""Main Temporal worker for gh-analysis.

Registers workflows, activities, and TemporalAgents.
Used by TemporalManager for CLI-managed execution.
"""

import logging

from pydantic_ai.durable_exec.temporal import AgentPlugin
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

# Import workflows
from gh_analysis.workflows import TroubleshootWorkflow

# Import activities
from gh_analysis.activities import fetch_github_issue, run_agent_analysis

# Import agents (TemporalAgents must be registered at module level)
from gh_analysis.agents.troubleshoot import (
    gpt5_high,
    gpt5_medium,
    gpt5_mini_high,
    gpt5_mini_medium,
    sonnet_4_5,
)

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

    # Register each TemporalAgent via AgentPlugin
    # This makes each agent's tool calls become Temporal activities
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[TroubleshootWorkflow],
        activities=[fetch_github_issue, run_agent_analysis],
        plugins=[
            AgentPlugin(gpt5_mini_medium),
            AgentPlugin(gpt5_mini_high),
            AgentPlugin(gpt5_medium),
            AgentPlugin(gpt5_high),
            AgentPlugin(sonnet_4_5),
        ],
    )

    logger.info("Worker created with 5 TemporalAgents registered via AgentPlugin")
    return worker
