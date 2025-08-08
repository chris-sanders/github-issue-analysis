"""Troubleshooting agents with MCP server integration."""

import os

from pydantic_ai import Agent

from .mcp_server import troubleshoot_mcp_server
from .models import TechnicalAnalysis
from .prompts import TROUBLESHOOTING_PROMPT
from .pydantic_ai_patch import apply_pydantic_ai_patch

# Apply the patch for OpenAI 1.99.2+ compatibility
apply_pydantic_ai_patch()


def create_o3_medium_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
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
        output_type=TechnicalAnalysis,
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
) -> Agent[None, TechnicalAnalysis]:
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
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 2400.0,
            "openai_reasoning_effort": "high",
            "stream": False,
        },
        retries=2,
    )


def create_gpt5_medium_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
    """Create GPT-5 with medium reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'gpt-5').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for gpt5_medium agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="gpt-5",  # Specify the model directly
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "medium",
            "stream": False,
            "parallel_tool_calls": True,
        },
        retries=2,
    )


def create_gpt5_high_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
    """Create GPT-5 with high reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'gpt-5').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for gpt5_high agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="gpt-5",  # Specify the model directly
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 2400.0,
            "openai_reasoning_effort": "high",
            "stream": False,
            "parallel_tool_calls": True,
        },
        retries=2,
    )


def create_gpt5_mini_medium_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
    """Create GPT-5-mini with medium reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'gpt-5-mini').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for gpt5_mini_medium agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="gpt-5-mini",  # Specify the model directly
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 1200.0,
            "openai_reasoning_effort": "medium",
            "stream": False,
            "parallel_tool_calls": True,
        },
        retries=2,
    )


def create_gpt5_mini_high_agent(
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
    """Create GPT-5-mini with high reasoning agent for troubleshooting.

    Note: Model should be specified at runtime (e.g., 'gpt-5-mini').
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable required for gpt5_mini_high agent"
        )

    return Agent(  # type: ignore[call-overload,no-any-return]
        model="gpt-5-mini",  # Specify the model directly
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[troubleshoot_mcp_server(sbctl_token, github_token)],
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "high",
            "stream": False,
            "parallel_tool_calls": True,
        },
        retries=2,
    )


# Factory function for agent creation
def create_troubleshooting_agent(
    agent_name: str,
    sbctl_token: str,
    github_token: str | None = None,
) -> Agent[None, TechnicalAnalysis]:
    """Create troubleshooting agent based on agent name.

    Args:
        agent_name: Name of agent configuration (o3_medium, o3_high, gpt5_mini_medium,
            gpt5_mini_high, gpt5_medium, gpt5_high)
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
    elif agent_name == "gpt5_mini_medium":
        return create_gpt5_mini_medium_agent(sbctl_token, github_token)
    elif agent_name == "gpt5_mini_high":
        return create_gpt5_mini_high_agent(sbctl_token, github_token)
    elif agent_name == "gpt5_medium":
        return create_gpt5_medium_agent(sbctl_token, github_token)
    elif agent_name == "gpt5_high":
        return create_gpt5_high_agent(sbctl_token, github_token)
    elif agent_name == "opus_41":
        raise ValueError("opus_41 agent is no longer supported")
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
