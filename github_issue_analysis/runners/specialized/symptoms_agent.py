"""Symptoms agent for extracting symptom terms from GitHub issues for memory retrieval."""

from typing import Any, List
from pydantic import BaseModel
from pydantic_ai import Agent

from ..utils.github_runner import GitHubIssueRunner


class SymptomsResult(BaseModel):
    """Result containing symptom terms extracted from an issue."""

    symptoms: List[str] = []


class SymptomsAgentRunner(GitHubIssueRunner):
    """Specialized agent for extracting symptom-related terms from GitHub issues.

    This is used by the memory system to identify relevant symptoms and problems
    for similarity search in the case database.
    """

    def __init__(
        self,
        experiment_name: str = "symptoms-extraction",
        model_name: str = "openai:o4-mini",
        model_settings: dict[str, Any] | None = None,
    ) -> None:
        """Initialize symptoms extraction agent.

        Args:
            experiment_name: Name of the experiment (for logging)
            model_name: Model to use for extraction
            model_settings: Additional model settings
        """
        # Simple agent that extracts symptom terms
        agent = Agent(
            model=model_name,
            output_type=SymptomsResult,
            instructions="""
            Extract symptom and problem-related terms from the GitHub issue.
            
            Look for:
            - Error types (crash, timeout, failure, exception, etc.)
            - Problem behaviors (slow, hanging, not responding, etc.)
            - Error messages or codes
            - Failure modes (startup failure, connection issues, etc.)
            - Performance issues (memory leak, CPU spike, etc.)
            - User impact (unable to access, data loss, etc.)
            
            Return a list of relevant symptom terms that describe the problem
            being experienced. Focus on technical symptoms rather than solutions.
            """,
            retries=1,
            instrument=True,
            model_settings=model_settings,  # type: ignore[arg-type]
        )
        super().__init__(experiment_name, agent)  # type: ignore[arg-type]
