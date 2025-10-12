"""Agent analysis activities."""

import logging
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def run_agent_analysis(issue_data: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Run AI agent analysis as Temporal activity.

    This activity executes a TemporalAgent, where each tool call
    becomes its own Temporal activity for full durability.

    Args:
        issue_data: GitHub issue data
        agent_name: Agent to use (gpt5_medium, gpt5_high, etc.)

    Returns:
        Analysis result dictionary

    Raises:
        ValueError: If agent_name is unknown
    """
    activity.logger.info(f"Running {agent_name} analysis")

    # Import agent registry
    from gh_analysis.agents import get_agent

    # Get the TemporalAgent
    agent = get_agent(agent_name)

    try:
        # Run agent (tool calls become Temporal activities automatically)
        result = await agent.run(issue_data)

        activity.logger.info(f"Analysis complete: {agent_name}")
        return {"output": result.output.model_dump()}

    except Exception as e:
        activity.logger.error(f"Analysis failed: {e}")
        raise
