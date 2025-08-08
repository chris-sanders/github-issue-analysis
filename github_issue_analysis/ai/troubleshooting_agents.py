"""Troubleshooting agents with MCP server integration."""

import os

from pydantic_ai import Agent

from .mcp_server import troubleshoot_mcp_server
from .models import TroubleshootingResponse
from .prompts import TROUBLESHOOTING_PROMPT
from .pydantic_ai_patch import apply_pydantic_ai_patch

# Apply the patch for OpenAI 1.99.2+ compatibility
apply_pydantic_ai_patch()


def create_o3_medium_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TroubleshootingResponse]:
    """Create O3 medium reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'o3').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for o3_medium agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="o3",  # Specify the model directly
        output_type=TroubleshootingResponse,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "medium",
            "stream": False,
        },
        retries=2,
    )


def create_o3_high_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TroubleshootingResponse]:
    """Create O3 high reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'o3').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for o3_high agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="o3",  # Specify the model directly
        output_type=TroubleshootingResponse,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 2400.0,
            "openai_reasoning_effort": "high",
            "stream": False,
        },
        retries=2,
    )


def create_opus_41_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TroubleshootingResponse]:
    """Create Anthropic Claude Opus 4.0 agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'claude-opus-4-0').
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable required for opus_41 agent"
        )

    return Agent(
        model="claude-opus-4-0",  # Specify the model directly
        output_type=TroubleshootingResponse,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 1800.0,
            "temperature": 0.7,
        },
        retries=2,
    )


# Factory function for agent creation
def create_troubleshooting_agent(
    agent_name: str,
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TroubleshootingResponse]:
    """Create troubleshooting agent based on agent name.

    Args:
        agent_name: Name of agent configuration (o3_medium, o3_high, opus_41)
        sbctl_token: SBCTL token for MCP server
        github_token: Optional GitHub token for enhanced MCP operations

    Returns:
        Configured PydanticAI agent with MCP tools

    Raises:
        ValueError: If agent_name is invalid or required API keys missing
    """
    if agent_name == "o3_medium":
        return create_o3_medium_agent(sbctl_token, github_token)
    elif agent_name == "o3_high":
        return create_o3_high_agent(sbctl_token, github_token)
    elif agent_name == "opus_41":
        return create_opus_41_agent(sbctl_token, github_token)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
