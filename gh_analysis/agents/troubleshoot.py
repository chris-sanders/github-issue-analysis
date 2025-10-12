"""Troubleshooting TemporalAgents using framework utilities.

All agents use framework's MCP integration and utilities.
No vendored code - everything comes from framework or gh_analysis.ai.
"""

import os
from datetime import timedelta

from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from temporal_framework import create_mcp_toolset
from temporal_framework.history import create_history_trimmer
from temporal_framework.tools import search_evidence

from gh_analysis.ai.models import TechnicalAnalysis
from gh_analysis.ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS

# Create MCP toolset using framework (suppress verbose logging)
mcp_tools = create_mcp_toolset(
    server_command="troubleshoot-mcp-server",
    token_env="SBCTL_TOKEN",
    env={"PYTHONWARNINGS": "ignore"},
    timeout=120.0,
    verbose=False,  # Suppress MCP server logs
    toolset_id="troubleshoot-mcp",
)

# Create history trimmers for different context windows
history_400k = create_history_trimmer(max_tokens=400_000, critical_ratio=0.9, high_ratio=0.8)
history_300k = create_history_trimmer(max_tokens=300_000, critical_ratio=0.9, high_ratio=0.8)
history_200k = create_history_trimmer(max_tokens=200_000, critical_ratio=0.9, high_ratio=0.8)

# Combined instructions for agents with search_evidence tool
combined_instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS


# GPT-5 Mini Medium
gpt5_mini_medium = TemporalAgent(
    Agent(
        name="gpt5_mini_medium",
        model=OpenAIResponsesModel("gpt-5-mini"),
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[mcp_tools],
        history_processors=[history_400k],
        retries=2,
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "medium",
            "parallel_tool_calls": True,
        },
    ),
    model_activity_config={"start_to_close_timeout": timedelta(minutes=2)},
)

# GPT-5 Mini High
gpt5_mini_high = TemporalAgent(
    Agent(
        name="gpt5_mini_high",
        model=OpenAIResponsesModel("gpt-5-mini"),
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[mcp_tools],
        history_processors=[history_400k],
        retries=2,
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "high",
            "parallel_tool_calls": True,
        },
    ),
    model_activity_config={"start_to_close_timeout": timedelta(minutes=2)},
)

# GPT-5 Medium
gpt5_medium = TemporalAgent(
    Agent(
        name="gpt5_medium",
        model=OpenAIResponsesModel("gpt-5"),
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[mcp_tools],
        history_processors=[history_400k],
        retries=2,
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "medium",
            "parallel_tool_calls": True,
        },
    ),
    model_activity_config={"start_to_close_timeout": timedelta(minutes=2)},
)

# GPT-5 High
gpt5_high = TemporalAgent(
    Agent(
        name="gpt5_high",
        model=OpenAIResponsesModel("gpt-5"),
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[mcp_tools],
        history_processors=[history_400k],
        retries=2,
        model_settings={
            "timeout": 1800.0,
            "openai_reasoning_effort": "high",
            "parallel_tool_calls": True,
        },
    ),
    model_activity_config={"start_to_close_timeout": timedelta(minutes=2)},
)

# Sonnet 4.5 (default Claude model)
sonnet_4_5 = TemporalAgent(
    Agent(
        name="sonnet_4_5",
        model=AnthropicModel("claude-sonnet-4-5-20250929"),
        output_type=TechnicalAnalysis,
        instructions=combined_instructions,
        toolsets=[mcp_tools],
        tools=[search_evidence],
        history_processors=[history_200k],
        retries=10,
        model_settings={
            "timeout": 60.0,
            "max_thinking_tokens": 20000,
            "max_tokens": 8192,
            "parallel_tool_calls": False,
        },
    ),
    model_activity_config={"start_to_close_timeout": timedelta(minutes=2)},
)

# Agent registry
AVAILABLE_AGENTS = {
    "gpt5_mini_medium": gpt5_mini_medium,
    "gpt5_mini_high": gpt5_mini_high,
    "gpt5_medium": gpt5_medium,
    "gpt5_high": gpt5_high,
    "sonnet_4_5": sonnet_4_5,  # Default Claude (Sonnet 4.5)
}


def get_agent(name: str) -> TemporalAgent:
    """Get agent by name.

    Args:
        name: Agent name (gpt5_medium, gpt5_high, etc.)

    Returns:
        TemporalAgent instance

    Raises:
        ValueError: If agent name is unknown
    """
    if name not in AVAILABLE_AGENTS:
        available = ", ".join(AVAILABLE_AGENTS.keys())
        raise ValueError(f"Unknown agent: {name}. Available: {available}")

    return AVAILABLE_AGENTS[name]
