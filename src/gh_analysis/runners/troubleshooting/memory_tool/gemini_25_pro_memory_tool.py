"""Gemini 2.5 Pro Memory Tool troubleshooting runner."""

from pydantic_ai import Agent

from ....ai.models import TechnicalAnalysis
from ....ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS
from ...adapters.mcp_adapter import create_troubleshoot_mcp_server
from ...utils.history import create_history_trimmer
from ...utils.memory_runner import MemoryAwareGitHubRunner
from ...utils.tools import search_evidence


class Gemini25ProMemoryToolRunner(MemoryAwareGitHubRunner):
    """Gemini 2.5 Pro troubleshooting analysis with memory and search evidence tool."""

    def __init__(self) -> None:
        # Create history trimmer with max tokens for Gemini 2.5 Pro
        history_trimmer = create_history_trimmer(max_tokens=800_000)

        # Combine troubleshooting prompt with tool instructions
        instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS

        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model="gemini-2.5-pro-exp",
            output_type=TechnicalAnalysis,
            instructions=instructions,
            history_processors=[history_trimmer],
            tools=[search_evidence],
            toolsets=[create_troubleshoot_mcp_server()],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1200.0,
            },
        )
        super().__init__("gemini-25-pro-mt", agent, enable_memory=True)
