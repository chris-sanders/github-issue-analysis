"""GPT-5 High reasoning troubleshooting runner with memory and tool access."""

from pydantic_ai import Agent

from ....ai.models import TechnicalAnalysis
from ....ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS
from ...adapters.mcp_adapter import create_troubleshoot_mcp_server
from ...utils.memory_runner import MemoryAwareGitHubRunner
from ...utils.history import create_history_trimmer
from ...utils.tools import search_evidence


class GPT5HighMemoryToolRunner(MemoryAwareGitHubRunner):
    """GPT-5 High reasoning troubleshooting analysis with memory and tool access."""

    def __init__(self) -> None:
        # Create history trimmer with high token limit
        history_trimmer = create_history_trimmer(max_tokens=400_000)

        # Combine prompts for tool-enhanced instructions
        combined_instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS

        # Create agent with tools and MCP server
        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model="gpt-5",
            output_type=TechnicalAnalysis,
            instructions=combined_instructions,
            history_processors=[history_trimmer],
            tools=[search_evidence],
            toolsets=[create_troubleshoot_mcp_server()],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1200.0,
                "openai_reasoning_effort": "high",
                "stream": False,
                "parallel_tool_calls": True,
            },
        )

        # Initialize with memory enabled
        super().__init__(name="gpt5-high-mt", agent=agent, enable_memory=True)
