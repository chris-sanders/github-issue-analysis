"""Memory-aware GitHub runner that injects relevant past cases into context."""

from typing import TypeVar, Dict, Any, Optional

from pydantic import BaseModel
from pydantic_ai import Agent

from .github_runner import GitHubIssueRunner
from .summary_retrieval import SummaryRetrievalClient

T = TypeVar("T", bound=BaseModel)


class MemoryAwareGitHubRunner(GitHubIssueRunner):
    """Base class for memory-aware GitHub issue runners.

    This class extends GitHubIssueRunner to add memory retrieval capabilities.
    It injects relevant past cases at the beginning of the context to provide
    historical context for better analysis.

    Key features:
    - Retrieves similar cases using vector search
    - Formats memory as structured XML context
    - Tracks retrieval metrics for observability
    """

    def __init__(
        self,
        name: str,
        agent: Agent,
        enable_memory: bool = True,
        shared_memory: Optional[Dict[int, Dict[str, Any]]] = None,
    ):
        """Initialize memory-aware runner.

        Args:
            name: Name of the runner
            agent: PydanticAI agent to use for analysis
            enable_memory: Whether to enable memory retrieval (for A/B testing)
            shared_memory: Pre-computed memory context to share across runners (optional)
        """
        super().__init__(name, agent)
        self.enable_memory = enable_memory
        self.summary_client = SummaryRetrievalClient() if enable_memory else None
        self.memory_stats: Dict[str, Any] = {}  # Track retrieval metrics per issue
        self.shared_memory_cache: Dict[
            int, Dict[str, Any]
        ] = {}  # Cache for shared memory contexts per issue

        # Set shared memory if provided
        if shared_memory:
            self.set_shared_memory(shared_memory)

    def set_shared_memory(self, memory_cache: Dict[int, Dict[str, Any]]) -> None:
        """Set pre-computed memory contexts for sharing across runners.

        Args:
            memory_cache: Dictionary mapping issue numbers to memory data
        """
        self.shared_memory_cache = memory_cache
        print(f"🧠 {self.name}: Loaded shared memory for {len(memory_cache)} issues")

    def get_shared_memory(self, issue_number: int) -> Optional[Dict[str, Any]]:
        """Get shared memory data for a specific issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            Memory data dictionary or None if not found
        """
        return self.shared_memory_cache.get(issue_number)

    async def _retrieve_memory_context(self, issue: Dict[str, Any]) -> str:
        """Retrieve similar cases and format as context.

        Args:
            issue: StoredIssueDict containing org, repo, issue, and metadata

        Returns:
            Formatted XML string containing relevant past cases
        """
        if not self.enable_memory:
            return ""

        # Handle both structures: StoredIssueDict and raw GitHub issue
        if "issue" in issue and isinstance(issue["issue"], dict):
            # This is a StoredIssueDict from our CLI
            github_issue = issue["issue"]
            issue_number = github_issue.get("number")
        else:
            # This is a raw GitHub issue (from experiments)
            github_issue = issue
            issue_number = issue.get("number")

        if not issue_number:
            raise ValueError(
                f"Invalid issue structure: missing issue number ({issue_number}). "
                f"Available keys: {list(issue.keys())}"
            )

        issue_key = f"issue-{issue_number}"

        # PRIORITY 1: Check for shared memory first (most efficient)
        shared_memory = self.get_shared_memory(issue_number)
        if shared_memory:
            print(f"🧠 Using shared memory context for {issue_key}")
            # Copy stats for observability
            self.memory_stats = shared_memory.get("stats", {})
            return str(shared_memory.get("memory_context", ""))

        # PRIORITY 2: Fall back to independent memory generation if no shared memory
        if not self.summary_client:
            return ""

        print(f"🧠 Generating independent memory context for {issue_key}...")

        # Step 1: Generate symptoms using specialized agent
        from gh_analysis.runners.specialized.symptoms_agent import (
            SymptomsAgentRunner,
        )

        # Create specialized agent for memory context extraction
        symptoms_agent = SymptomsAgentRunner(f"memory-{issue_key}")

        # Extract symptoms for memory search
        print("   🤖 Running symptoms agent for memory context...")
        symptoms_result: Any = await symptoms_agent.analyze(github_issue)

        # Step 2: Extract symptom fields
        symptoms = (
            symptoms_result.symptoms if hasattr(symptoms_result, "symptoms") else []
        )

        print(f"   🚨 Symptom terms: {len(symptoms)}")

        # Step 3: Search for similar cases using symptoms only
        symptoms_text = " ".join(symptoms) if symptoms else ""
        similar_cases = self.summary_client.search_by_symptoms(
            symptoms_text=symptoms_text,
            limit=2,
            threshold=0.7,
        )

        # Step 4: Track metrics
        self.memory_stats = {
            "cases_retrieved": len(similar_cases),
            "avg_similarity": (
                sum(c.get("SYMPTOM_SIMILARITY", 0) for c in similar_cases)
                / len(similar_cases)
                if similar_cases
                else 0
            ),
            "symptom_terms": len(symptoms),
        }

        # Step 5: Format and return
        memory_context = self.summary_client.format_memory_context(similar_cases)

        if memory_context:
            print(f"   ✅ Retrieved {len(similar_cases)} relevant cases")
        else:
            print("   ⚠️ No relevant cases found")

        return memory_context

    def _build_context(self, issue: Dict[str, Any]) -> str:
        """Build context with memory injection.

        Args:
            issue: GitHub issue data

        Returns:
            Context string with memory prepended if available
        """
        # Get base context from parent class
        base_context = super()._build_context(issue)

        if not self.enable_memory:
            return base_context

        # This is called from sync context, so we need to handle async carefully
        # In practice, this will be called from analyze() which is already async
        # For now, return base context and rely on async analyze override
        return base_context

    async def analyze(self, issue: Dict[str, Any]) -> T:
        """Analyze issue with memory context injection.

        This method overrides the base analyze to inject memory context
        and add observability tracking for memory retrieval.

        Args:
            issue: GitHub issue data

        Returns:
            Analysis result from the configured agent
        """
        memory_context = ""

        # Step 1: Retrieve memory context if enabled
        if self.enable_memory:
            # Always add observability tracking (Phoenix is assumed to be available)
            from opentelemetry import trace

            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span("memory_retrieval") as span:
                memory_context = await self._retrieve_memory_context(issue)

                # Set span attributes
                stats = self.memory_stats
                span.set_attribute(
                    "memory.cases_retrieved", stats.get("cases_retrieved", 0)
                )
                span.set_attribute(
                    "memory.avg_similarity", stats.get("avg_similarity", 0)
                )
                span.set_attribute("memory.context_length", len(memory_context))
                span.set_attribute(
                    "memory.symptom_terms", stats.get("symptom_terms", 0)
                )
                span.set_attribute(
                    "memory.retrieval_status",
                    stats.get("retrieval_status", "unknown"),
                )

        # Step 2: Temporarily store memory context for _build_user_message
        self._current_memory_context = memory_context

        # Step 3: Continue with standard analysis
        # Extract GitHub issue for parent class (same logic as memory retrieval)
        if "issue" in issue and isinstance(issue["issue"], dict):
            # This is a StoredIssueDict from our CLI
            github_issue_for_analysis = issue["issue"]
        else:
            # This is a raw GitHub issue (from experiments)
            github_issue_for_analysis = issue

        try:
            result: T = await super().analyze(github_issue_for_analysis)
            return result
        finally:
            # Clean up temporary context
            self._current_memory_context = ""

    def _build_user_message(self, context: str) -> str:
        """Build user message with memory context prepended.

        Args:
            context: Base context from GitHub issue

        Returns:
            User message with memory context at the beginning
        """
        memory_context = getattr(self, "_current_memory_context", "")

        if memory_context:
            # Inject memory at the beginning for highest attention
            full_context = f"{memory_context}\n\n{context}"
        else:
            full_context = context

        return f"**Problem Description:**\n{full_context}"

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory retrieval statistics for the last analysis.

        Returns:
            Dictionary containing retrieval metrics
        """
        return self.memory_stats.copy()
