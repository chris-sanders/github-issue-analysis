"""Claude Sonnet 4 Memory Tool troubleshooting runner with search capabilities."""

from pydantic_ai import Agent

from ....ai.models import TechnicalAnalysis
from ....ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS
from ...adapters.mcp_adapter import create_troubleshoot_mcp_server
from ...utils.history import create_history_trimmer
from ...utils.memory_runner import MemoryAwareGitHubRunner
from ...utils.tools import search_evidence


class ClaudeSonnetMemoryToolRunner(MemoryAwareGitHubRunner):
    """Claude Sonnet 4 Memory Tool troubleshooting analysis with search capabilities."""

    def __init__(self) -> None:
        # Create history trimmer with specified max tokens
        history_trimmer = create_history_trimmer(max_tokens=300_000)

        # Combine prompts for tool-enhanced runner
        combined_instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS

        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model="claude-sonnet-4",
            output_type=TechnicalAnalysis,
            instructions=combined_instructions,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            tools=[search_evidence],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1200.0,
                "stream": False,
                "parallel_tool_calls": True,
            },
        )
        super().__init__("claude-sonnet-mt", agent, enable_memory=True)
