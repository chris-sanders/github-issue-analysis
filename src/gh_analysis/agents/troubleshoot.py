"""
Troubleshooting agents for Temporal workflow execution.

These agents use TemporalAgent with per-workflow bundle storage.
Bundles persist across activity executions using PRESERVE_BUNDLES=true.
"""

import logging
import os
from datetime import timedelta
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import TemporalAgent
from pydantic_ai.models.openai import OpenAIResponsesModel

from framework.temporal import create_mcp_toolset
from gh_analysis.ai.models import TechnicalAnalysis
from gh_analysis.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Base bundle storage directory
BASE_BUNDLE_STORAGE = Path("/tmp/mcp-bundles")
BASE_BUNDLE_STORAGE.mkdir(parents=True, exist_ok=True)

# Environment variables
sbctl_token = os.getenv("SBCTL_TOKEN")
github_token = os.getenv("GITHUB_TOKEN")

if not sbctl_token:
    raise ValueError("SBCTL_TOKEN environment variable is required")
if not github_token:
    raise ValueError("GITHUB_TOKEN environment variable is required")


# Create MCP toolset using UV to run troubleshoot-mcp-server directly
# Single bundle mode: Bundle presence on disk = active bundle (stateless operation)
# - MCP_SINGLE_BUNDLE_MODE=true: Auto-activates bundle from disk on server startup
# - PRESERVE_BUNDLES=true: Don't delete bundles on shutdown
# - MCP_BUNDLE_STORAGE: Persistent directory for bundle storage
#
# How it works:
# 1. Activity 1 (initialize_bundle): Downloads bundle → stored in BASE_BUNDLE_STORAGE
# 2. Activity 2 (list_files): New MCP server → auto-discovers bundle from disk → uses it
# 3. Activity N: Each activity auto-discovers the bundle (no re-initialization needed)

mcp_tools = create_mcp_toolset(
    "troubleshoot-mcp-server",
    env={
        "SBCTL_TOKEN": sbctl_token,
        "GITHUB_TOKEN": github_token,
        "MCP_BUNDLE_STORAGE": str(BASE_BUNDLE_STORAGE),
        "MCP_SINGLE_BUNDLE_MODE": "true",  # Enable stateless bundle mode
        "PRESERVE_BUNDLES": "true",
    },
    toolset_id="troubleshoot-mcp",
)

# Module-level TemporalAgent (required for activity registration)
# Uses shared bundle storage - MCP server manages isolation
gpt5_mini_medium_agent = TemporalAgent(
    Agent(
        name="g5m-med",
        model=OpenAIResponsesModel("gpt-5-mini"),
        output_type=TechnicalAnalysis,
        instructions=SYSTEM_PROMPT,
        toolsets=[mcp_tools],
        retries=3,
        model_settings={
            "timeout": 1800.0,  # OpenAI API timeout (30 minutes)
            "openai_reasoning_effort": "medium",
            "parallel_tool_calls": True,
        },
    ),
    model_activity_config={
        "start_to_close_timeout": timedelta(
            minutes=2
        )  # Temporal activity timeout for LLM calls
    },
)


def create_gpt5_mini_high_agent() -> TemporalAgent[None, TechnicalAnalysis]:
    """
    Create GPT-5 Mini agent with high reasoning effort for troubleshooting.

    Returns:
        TemporalAgent configured for technical analysis with MCP tools
    """
    return TemporalAgent(
        Agent(
            name="g5m-high",
            model=OpenAIResponsesModel("gpt-5-mini"),
            output_type=TechnicalAnalysis,
            instructions=SYSTEM_PROMPT,
            toolsets=[mcp_tools],
            retries=3,
            model_settings={
                "timeout": 1800.0,  # OpenAI API timeout (30 minutes)
                "openai_reasoning_effort": "high",
                "parallel_tool_calls": True,
            },
        ),
        model_activity_config={
            "start_to_close_timeout": timedelta(
                minutes=2
            )  # Temporal activity timeout for LLM calls
        },
    )


def create_gpt5_medium_agent() -> TemporalAgent[None, TechnicalAnalysis]:
    """
    Create GPT-5 agent with medium reasoning effort for troubleshooting.

    Returns:
        TemporalAgent configured for technical analysis with MCP tools
    """
    return TemporalAgent(
        Agent(
            name="g5-med",
            model=OpenAIResponsesModel("gpt-5"),
            output_type=TechnicalAnalysis,
            instructions=SYSTEM_PROMPT,
            toolsets=[mcp_tools],
            retries=3,
            model_settings={
                "timeout": 1800.0,  # OpenAI API timeout (30 minutes)
                "openai_reasoning_effort": "medium",
                "parallel_tool_calls": True,
            },
        ),
        model_activity_config={
            "start_to_close_timeout": timedelta(
                minutes=2
            )  # Temporal activity timeout for LLM calls
        },
    )


def create_gpt5_high_agent() -> TemporalAgent[None, TechnicalAnalysis]:
    """
    Create GPT-5 agent with high reasoning effort for troubleshooting.

    Returns:
        TemporalAgent configured for technical analysis with MCP tools
    """
    return TemporalAgent(
        Agent(
            name="g5-high",
            model=OpenAIResponsesModel("gpt-5"),
            output_type=TechnicalAnalysis,
            instructions=SYSTEM_PROMPT,
            toolsets=[mcp_tools],
            retries=3,
            model_settings={
                "timeout": 1800.0,  # OpenAI API timeout (30 minutes)
                "openai_reasoning_effort": "high",
                "parallel_tool_calls": True,
            },
        ),
        model_activity_config={
            "start_to_close_timeout": timedelta(
                minutes=2
            )  # Temporal activity timeout for LLM calls
        },
    )
