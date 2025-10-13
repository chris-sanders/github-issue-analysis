"""Root cause analysis agent runner."""

import uuid
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel

from ..utils.github_runner import GitHubIssueRunner
from ..utils.mcp import create_troubleshoot_mcp_server
from ..utils.history import create_history_trimmer
from ..summary_models import CauseResult
from ..summary_prompts import CAUSE_FULL_PROMPT


class CauseAgentRunner(GitHubIssueRunner):
    """Runner to identify root causes in support cases."""

    def __init__(self):
        # Create history trimmer for GPT-5's context limit
        history_trimmer = create_history_trimmer(
            max_tokens=400_000, critical_ratio=0.9, high_ratio=0.8
        )

        # Create agent with GPT-5 medium specific settings and unique name
        unique_id = str(uuid.uuid4())[:8]
        agent = Agent(
            name=f"cause-agent-{unique_id}",
            model=OpenAIResponsesModel("gpt-5-mini"),
            output_type=CauseResult,
            instructions=CAUSE_FULL_PROMPT,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            instrument=True,
            model_settings={
                "timeout": 1800.0,  # 30 minutes (increased from 16.6 minutes)
                "openai_reasoning_effort": "medium",
                "parallel_tool_calls": True,
            },
        )

        super().__init__("cause-agent", agent)
