"""Dynamic formatter for troubleshooting analysis results in Slack."""

from typing import Dict, Any, List
from .text_utils import split_text_at_boundaries, create_continuation_header


class TroubleshootingFormatter:
    """Formats troubleshooting analysis results for Slack display."""

    # Field display configuration
    FIELD_CONFIG = {
        # ResolvedAnalysis fields
        "resolved": {
            "root_cause": {"title": "Root Cause", "order": 1, "type": "text"},
            "evidence": {"title": "Key Evidence", "order": 2, "type": "list"},
            "validation": {"title": "Analysis Validation", "order": 3, "type": "text"},
            "solution": {"title": "Recommended Solution", "order": 4, "type": "text"},
        },
        # NeedsDataAnalysis fields
        "needs_data": {
            "current_hypothesis": {
                "title": "Current Assessment",
                "order": 1,
                "type": "text",
            },
            "missing_evidence": {"title": "Data Needed", "order": 2, "type": "list"},
            "next_steps": {"title": "Next Steps", "order": 3, "type": "list"},
            "eliminated": {"title": "Ruled Out", "order": 4, "type": "list"},
        },
    }

    def format_analysis_topics(
        self, results: Dict[str, Any]
    ) -> List[List[Dict[str, Any]]]:
        """
        Dynamically format analysis results based on status and available fields.

        Args:
            results: Analysis results dictionary

        Returns:
            List of topic blocks (each topic is a list of blocks)
        """
        status = results.get("status", "unknown")
        topics = []

        # Get field configuration for this status
        field_config = self.FIELD_CONFIG.get(status, {})

        # Sort fields by configured order
        sorted_fields = sorted(field_config.items(), key=lambda x: x[1]["order"])

        # Format each field if present in results
        for field_name, config in sorted_fields:
            value = results.get(field_name)
            if not value:
                continue

            # Format based on field type
            if config["type"] == "text":
                blocks = self._format_text_field(value, config["title"])
            elif config["type"] == "list":
                blocks = self._format_list_field(value, config["title"])
            else:
                continue

            if blocks:
                topics.append(blocks)

        return topics

    def _format_text_field(self, text: str, title: str) -> List[Dict[str, Any]]:
        """
        Format a text field with proper splitting if needed.

        Args:
            text: The text content
            title: The field title

        Returns:
            List of formatted blocks
        """
        if len(text) <= 2900:
            return [self._create_section_block(title, text)]

        # Split long text
        parts = split_text_at_boundaries(text, 2900)
        blocks = []
        for i, part in enumerate(parts):
            block_title = create_continuation_header(title, i > 0)
            blocks.append(self._create_section_block(block_title, part))
        return blocks

    def _format_list_field(self, items: List[str], title: str) -> List[Dict[str, Any]]:
        """
        Format a list field as bullet points with proper splitting if needed.

        Args:
            items: List of items
            title: The field title

        Returns:
            List of formatted blocks
        """
        if not items:
            return []

        # Format as bullet list
        text = "\n".join([f"• {item}" for item in items])

        if len(text) <= 2900:
            return [self._create_section_block(title, text)]

        # Split long lists
        parts = split_text_at_boundaries(text, 2900)
        blocks = []
        for i, part in enumerate(parts):
            block_title = create_continuation_header(title, i > 0)
            blocks.append(self._create_section_block(block_title, part))
        return blocks

    def _create_section_block(self, title: str, content: str) -> Dict[str, Any]:
        """
        Create a Slack section block.

        Args:
            title: Block title
            content: Block content

        Returns:
            Formatted section block
        """
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}:*\n{content}",
            },
        }

    def should_use_dynamic_formatting(self, results: Dict[str, Any]) -> bool:
        """
        Check if results should use dynamic formatting.

        Args:
            results: Analysis results

        Returns:
            True if this is a troubleshooting result that should use dynamic formatting
        """
        status = results.get("status")

        # Use dynamic formatting for troubleshooting statuses
        if status in ["resolved", "needs_data"]:
            return True

        # Check for troubleshooting-specific fields
        troubleshooting_fields = {
            "root_cause",
            "solution",
            "validation",  # ResolvedAnalysis
            "current_hypothesis",
            "missing_evidence",
            "eliminated",  # NeedsDataAnalysis
        }

        return any(field in results for field in troubleshooting_fields)
