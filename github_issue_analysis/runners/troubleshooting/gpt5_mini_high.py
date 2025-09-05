"""GPT-5 Mini High reasoning troubleshooting runner."""

from pydantic_ai import Agent

from ...ai.models import TechnicalAnalysis
from ...ai.prompts import TROUBLESHOOTING_PROMPT
from ..adapters.mcp_adapter import create_troubleshoot_mcp_server
from ..utils.github_runner import GitHubIssueRunner
from ..utils.history import create_history_trimmer


class GPT5MiniHighTroubleshootRunner(GitHubIssueRunner):
    """GPT-5 Mini High reasoning troubleshooting analysis."""

    def __init__(self) -> None:
        # Match current agent configuration exactly
        history_trimmer = create_history_trimmer(
            max_tokens=400_000, critical_ratio=0.9, high_ratio=0.8
        )

        agent = Agent[None, TechnicalAnalysis](  # type: ignore[call-overload]
            model="gpt-5-mini",
            output_type=TechnicalAnalysis,
            instructions=TROUBLESHOOTING_PROMPT,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1800.0,
                "openai_reasoning_effort": "high",
                "stream": False,
                "parallel_tool_calls": True,
            },
        )
        super().__init__("gpt5-mini-high", agent)
