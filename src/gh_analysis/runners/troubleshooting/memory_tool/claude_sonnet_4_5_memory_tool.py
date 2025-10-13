"""Claude Sonnet 4.5 Memory Tool troubleshooting runner with search capabilities."""

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel

from ....ai.models import TechnicalAnalysis
from ....ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS
from ...adapters.mcp_adapter import create_troubleshoot_mcp_server
from ...utils.history import create_history_trimmer
from ...utils.memory_runner import MemoryAwareGitHubRunner
from ...utils.tools import search_evidence


class ClaudeSonnet45MemoryToolRunner(MemoryAwareGitHubRunner):
    """Claude Sonnet 4.5 Memory Tool troubleshooting analysis with search capabilities.

    This runner combines memory injection and evidence search tool capabilities:
    - Retrieves top 2 similar cases using vector search (memory)
    - Injects memory at beginning of context for highest attention
    - Provides search_evidence tool for additional case lookup during analysis
    - Uses both TROUBLESHOOTING_PROMPT and TOOL_INSTRUCTIONS

    Model: claude-sonnet-4-5-20250929
    Context: 200K tokens with history trimming at 80% (160K) and 90% (180K)
    """

    def __init__(self) -> None:
        # Create history trimmer for Claude Sonnet 4.5's 200K context limit
        history_trimmer = create_history_trimmer(
            max_tokens=200_000, critical_ratio=0.9, high_ratio=0.8
        )

        # Combine prompts for tool-enhanced runner
        combined_instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS

        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model=AnthropicModel("claude-sonnet-4-5-20250929"),
            output_type=TechnicalAnalysis,
            instructions=combined_instructions,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            tools=[search_evidence],
            instrument=True,
            retries=10,  # Increase retries for API stability
            model_settings={
                "timeout": 60.0,  # 60 second timeout for individual API calls
                "max_thinking_tokens": 20000,
                "max_tokens": 8192,
                "parallel_tool_calls": False,
            },
        )
        super().__init__("sonnet-4.5-mt", agent, enable_memory=True)
