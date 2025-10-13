"""GPT-5 Medium reasoning troubleshooting runner with memory and search tools."""

from pydantic_ai import Agent

from ....ai.models import TechnicalAnalysis
from ....ai.prompts import TROUBLESHOOTING_PROMPT, TOOL_INSTRUCTIONS
from ...adapters.mcp_adapter import create_troubleshoot_mcp_server
from ...utils.history import create_history_trimmer
from ...utils.memory_runner import MemoryAwareGitHubRunner
from ...utils.tools import search_evidence


class GPT5MediumMemoryToolRunner(MemoryAwareGitHubRunner):
    """GPT-5 Medium reasoning troubleshooting analysis with memory and search tools."""

    def __init__(self) -> None:
        # Create history trimmer with specified max tokens
        history_trimmer = create_history_trimmer(max_tokens=400_000)

        # Combine prompts as specified
        combined_instructions = TROUBLESHOOTING_PROMPT + "\n\n" + TOOL_INSTRUCTIONS

        # Create agent with GPT-5 model and specified configuration
        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model="gpt-5",
            output_type=TechnicalAnalysis,
            instructions=combined_instructions,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            tools=[search_evidence],  # Include search_evidence tool
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1200.0,
                "openai_reasoning_effort": "medium",
                "stream": False,
                "parallel_tool_calls": True,
            },
        )

        # Call parent constructor with specified parameters
        super().__init__(
            name="gpt5-medium-mt",
            agent=agent,
            enable_memory=True,
        )
