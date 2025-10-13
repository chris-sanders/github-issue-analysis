"""Product agent for extracting product terms from GitHub issues for memory retrieval."""

from typing import Any, List
from pydantic import BaseModel
from pydantic_ai import Agent

from ..utils.github_runner import GitHubIssueRunner


class ProductResult(BaseModel):
    """Result containing product terms extracted from an issue."""

    product: List[str] = []


class ProductAgentRunner(GitHubIssueRunner):
    """Specialized agent for extracting product-related terms from GitHub issues.

    This is used by the memory system to identify relevant product components
    for similarity search in the case database.
    """

    def __init__(
        self,
        experiment_name: str = "product-extraction",
        model_name: str = "openai:o4-mini",
        model_settings: dict[str, Any] | None = None,
    ) -> None:
        """Initialize product extraction agent.

        Args:
            experiment_name: Name of the experiment (for logging)
            model_name: Model to use for extraction
            model_settings: Additional model settings
        """
        # Simple agent that extracts product terms
        agent = Agent(
            model=model_name,
            output_type=ProductResult,
            instructions="""
            Extract product-related terms from the GitHub issue.
            
            Look for:
            - Product names (KOTS, Troubleshoot, KURL, Embedded Cluster, SDK, etc.)
            - Component names (CLI, API, UI, dashboard, etc.)  
            - Technology terms (Kubernetes, Docker, Helm, etc.)
            - Feature names (snapshots, backups, updates, etc.)
            
            Return a list of relevant product terms that could be used for similarity search.
            Be concise but comprehensive.
            """,
            retries=1,
            instrument=True,
            model_settings=model_settings,  # type: ignore[arg-type]
        )
        super().__init__(experiment_name, agent)  # type: ignore[arg-type]
