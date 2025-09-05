"""Runner registry for github-issue-analysis."""

from typing import Any

from .base.product_labeling import ProductLabelingRunner
from .troubleshooting.gpt5_high import GPT5HighTroubleshootRunner
from .troubleshooting.gpt5_medium import GPT5MediumTroubleshootRunner
from .troubleshooting.gpt5_mini_high import GPT5MiniHighTroubleshootRunner
from .troubleshooting.gpt5_mini_medium import GPT5MiniMediumTroubleshootRunner
from .troubleshooting.memory_tool.claude_sonnet_memory_tool import (
    ClaudeSonnetMemoryToolRunner,
)
from .troubleshooting.memory_tool.gemini_25_pro_memory_tool import (
    Gemini25ProMemoryToolRunner,
)
from .troubleshooting.memory_tool.gpt5_high_memory_tool import GPT5HighMemoryToolRunner
from .troubleshooting.memory_tool.gpt5_medium_memory_tool import (
    GPT5MediumMemoryToolRunner,
)
from .troubleshooting.memory_tool.gpt5_mini_high_memory_tool import (
    GPT5MiniHighMemoryToolRunner,
)
from .troubleshooting.memory_tool.gpt5_mini_medium_memory_tool import (
    GPT5MiniMediumMemoryToolRunner,
)
from .troubleshooting.o3_high import O3HighTroubleshootRunner
from .troubleshooting.o3_medium import O3MediumTroubleshootRunner
from .utils.github_runner import GitHubIssueRunner

RUNNERS: dict[str, type[GitHubIssueRunner]] = {
    "product-labeling": ProductLabelingRunner,
    "gpt5_mini_medium": GPT5MiniMediumTroubleshootRunner,
    "gpt5_mini_high": GPT5MiniHighTroubleshootRunner,
    "gpt5_medium": GPT5MediumTroubleshootRunner,
    "gpt5_high": GPT5HighTroubleshootRunner,
    "o3_medium": O3MediumTroubleshootRunner,
    "o3_high": O3HighTroubleshootRunner,
    "claude_sonnet_mt": ClaudeSonnetMemoryToolRunner,
    "gpt5_mini_medium_mt": GPT5MiniMediumMemoryToolRunner,
    "gpt5_mini_high_mt": GPT5MiniHighMemoryToolRunner,
    "gpt5_medium_mt": GPT5MediumMemoryToolRunner,
    "gpt5_high_mt": GPT5HighMemoryToolRunner,
    "gemini_25_pro_mt": Gemini25ProMemoryToolRunner,
}


def get_runner(name: str, **kwargs: Any) -> GitHubIssueRunner:
    """Get runner instance by name."""
    if name not in RUNNERS:
        available = ", ".join(RUNNERS.keys())
        raise ValueError(f"Unknown runner: {name}. Available: {available}")

    runner_class = RUNNERS[name]
    return runner_class(**kwargs)


def list_runners() -> dict[str, str]:
    """Get list of available runners with descriptions."""
    return {
        "product-labeling": "Product label recommendations using configurable models",
        "gpt5_mini_medium": "GPT-5 Mini with medium reasoning for troubleshooting",
        "gpt5_mini_high": "GPT-5 Mini with high reasoning for troubleshooting",
        "gpt5_medium": "GPT-5 with medium reasoning for troubleshooting",
        "gpt5_high": "GPT-5 with high reasoning for troubleshooting",
        "o3_medium": "OpenAI O3 with medium reasoning for troubleshooting",
        "o3_high": "OpenAI O3 with high reasoning for troubleshooting",
        "claude_sonnet_mt": "Claude Sonnet 4 with memory injection and evidence search tools",
        "gpt5_mini_medium_mt": "GPT-5 Mini (medium reasoning) with memory and evidence search",
        "gpt5_mini_high_mt": "GPT-5 Mini (high reasoning) with memory and evidence search",
        "gpt5_medium_mt": "GPT-5 (medium reasoning) with memory and evidence search",
        "gpt5_high_mt": "GPT-5 (high reasoning) with memory and evidence search",
        "gemini_25_pro_mt": "Gemini 2.5 Pro with memory injection and evidence search tools",
    }
