"""
Reusable PydanticAI tools for technical support analysis.

This module contains tool functions that can be used across different agents
and experiments to enhance their analytical capabilities.
"""

from typing import List, Dict, Any
from .summary_retrieval import SummaryRetrievalClient


def search_evidence(query: str, limit: int = 2, threshold: float = 0.6) -> str:
    """Search for similar technical evidence in past support cases.

    Use this tool when you encounter specific technical evidence (error messages,
    log entries, diagnostic output) and want to find similar patterns from resolved
    cases. This helps identify precedent solutions and common root causes.

    Best results come from detailed technical descriptions. Include context like
    the failure mode, specific error messages, and what component is affected.

    Args:
        query: Technical evidence to search for - use detailed descriptions with context
        limit: Maximum number of similar cases to return (default: 2, max: 5)
        threshold: Minimum similarity score (default: 0.6, range: 0.0-1.0)

    Returns:
        Formatted string containing similar cases with their evidence, root causes, and fixes.
        Returns "No similar evidence found." if no matches above threshold.

    Examples of effective queries:
        "Pod stuck in ContainerCreating state FailedMount unable to mount volumes"
        "ImagePullBackOff ErrImagePull failed to pull and extract image dial tcp timeout"
        "DNS resolution failed timeout resolving external domain names"
        "PersistentVolumeClaim is pending no persistent volumes available to satisfy"
    """
    try:
        # Validate and constrain parameters
        limit = max(1, min(limit, 5))  # Constrain to 1-5 results
        threshold = max(0.0, min(threshold, 1.0))  # Constrain to 0.0-1.0

        if not query.strip():
            return "Error: Query is empty. Please provide technical evidence to search for."

        # Initialize client and search
        client = SummaryRetrievalClient()
        results = client.search_by_evidence(query, limit=limit, threshold=threshold)

        if not results:
            return "No similar evidence found. Try lowering the threshold or using different technical terms."

        # Format results for agent consumption
        return _format_evidence_search_results(results, query, threshold)

    except Exception as e:
        return f"Error searching evidence: {str(e)}"


def _format_evidence_search_results(
    results: List[Dict[str, Any]], query: str, threshold: float
) -> str:
    """Format evidence search results for agent consumption using XML format.

    Args:
        results: List of matching case dictionaries from database
        query: Original search query
        threshold: Similarity threshold used

    Returns:
        XML formatted string with case details for agent analysis
    """
    if not results:
        return "No similar evidence found."

    def parse_array_field(field_value: Any) -> List[str]:
        """Parse array field that might be returned as string from Snowflake."""
        if isinstance(field_value, str):
            # Try to parse as JSON array if it looks like one
            if field_value.strip().startswith("[") and field_value.strip().endswith(
                "]"
            ):
                import json

                try:
                    parsed = json.loads(field_value)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                    else:
                        return [str(parsed)]
                except json.JSONDecodeError:
                    return [field_value]  # Return as single item if can't parse
            else:
                return [field_value]  # Single string item
        elif isinstance(field_value, list):
            return [str(item) for item in field_value]
        else:
            return []

    context_lines = [
        f'<similar_evidence_cases query="{query}" threshold="{threshold:.2f}" count="{len(results)}">'
    ]

    for i, case in enumerate(results, 1):
        # Basic case info
        issue_key = f"{case.get('ORG_NAME', 'unknown')}/{case.get('REPO_NAME', 'unknown')}#{case.get('ISSUE_NUMBER', 'unknown')}"
        similarity = case.get("evidence_similarity", case.get("EVIDENCE_SIMILARITY", 0))

        context_lines.append(
            f'<case id="{i}" issue="{issue_key}" similarity="{similarity:.3f}">'
        )

        # Evidence items (limit to top 3 for readability)
        evidence_items = parse_array_field(case.get("EVIDENCE", []))
        if evidence_items and any(e for e in evidence_items):
            context_lines.append("<evidence>")
            for evidence in evidence_items[:3]:  # Limit to top 3
                if evidence and str(evidence).strip():
                    context_lines.append(f"<item>{evidence}</item>")
            context_lines.append("</evidence>")

        # Root cause if available
        cause = case.get("CAUSE", "")
        if cause and str(cause).strip():
            context_lines.append(f"<root_cause>{cause}</root_cause>")

        # Fix actions if available
        fix_items = parse_array_field(case.get("FIX", []))
        if fix_items and any(f for f in fix_items):
            context_lines.append("<fix_applied>")
            for fix in fix_items[:2]:  # Limit to top 2 fix items
                if fix and str(fix).strip():
                    context_lines.append(f"<action>{fix}</action>")
            context_lines.append("</fix_applied>")

        context_lines.append("</case>")

    context_lines.append("</similar_evidence_cases>")

    return "\n".join(context_lines)
