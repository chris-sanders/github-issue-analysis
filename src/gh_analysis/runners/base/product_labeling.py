"""Product labeling runner using runner pattern."""

from typing import Any

from pydantic_ai import Agent

from ...ai.models import ProductLabelingResponse
from ...ai.prompts import PRODUCT_LABELING_PROMPT
from ..utils.github_runner import GitHubIssueRunner


class ProductLabelingRunner(GitHubIssueRunner):
    """Product labeling analysis using runner pattern."""

    def __init__(
        self,
        model_name: str = "openai:o4-mini",
        model_settings: dict[str, Any] | None = None,
    ) -> None:
        # Create agent with same configuration as current implementation
        agent = Agent(
            model=model_name,
            output_type=ProductLabelingResponse,
            instructions=PRODUCT_LABELING_PROMPT,
            retries=2,
            instrument=True,
            model_settings=model_settings,  # type: ignore[arg-type]
        )
        super().__init__("product-labeling", agent)  # type: ignore[arg-type]
