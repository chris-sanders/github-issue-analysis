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
        # Format issue data properly for agent (needs actual issue content, not schema)
        # The issue_data is a GitHubIssue model dict with: number, title, body, comments, etc.
        formatted_context = f"""**GitHub Issue Analysis**

**Issue**: #{issue_data['number']}
**Title**: {issue_data.get('title', 'N/A')}
**State**: {issue_data.get('state', 'N/A')}

**Description**:
{issue_data.get('body', 'No description provided')}

**Comments** ({len(issue_data.get('comments', []))} total):
"""
        for i, comment in enumerate(issue_data.get('comments', [])[:10], 1):
            formatted_context += f"\n--- Comment {i} ---\n{comment.get('body', '')}\n"

        # Run agent with formatted context
        result = await agent.run(formatted_context)

        activity.logger.info(f"Analysis complete: {agent_name}")

        # Return the model dict directly (workflow will pass it through)
        return result.output.model_dump()

    except Exception as e:
        activity.logger.error(f"Analysis failed: {e}")
        raise
