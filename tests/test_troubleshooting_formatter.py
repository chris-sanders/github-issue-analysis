"""Tests for the dynamic troubleshooting formatter."""

from typing import Any
from gh_analysis.slack.troubleshooting_formatter import TroubleshootingFormatter


class TestTroubleshootingFormatter:
    """Test the dynamic troubleshooting formatter."""

    def setup_method(self):
        """Set up test instance."""
        self.formatter = TroubleshootingFormatter()

    def test_resolved_analysis_all_fields_formatted(self):
        """Test that all ResolvedAnalysis fields are formatted correctly."""
        results = {
            "status": "resolved",
            "root_cause": "Database connection timeout",
            "evidence": [
                "Connection logs show timeout",
                "Network trace confirms delay",
            ],
            "solution": "Increase connection timeout to 30s",
            "validation": "Timeout errors correlate with network latency spikes",
        }

        topics = self.formatter.format_analysis_topics(results)

        # Should have 4 topics (root_cause, evidence, validation, solution)
        assert len(topics) == 4

        # Verify order and content
        all_text = ""
        for topic in topics:
            for block in topic:
                all_text += block.get("text", {}).get("text", "") + " "

        # Check fields appear in correct order
        root_cause_pos = all_text.find("Root Cause")
        evidence_pos = all_text.find("Key Evidence")
        validation_pos = all_text.find("Analysis Validation")
        solution_pos = all_text.find("Recommended Solution")

        assert root_cause_pos < evidence_pos < validation_pos < solution_pos

        # Verify content is present
        assert "Database connection timeout" in all_text
        assert "Connection logs show timeout" in all_text
        assert "Increase connection timeout" in all_text
        assert "network latency spikes" in all_text

    def test_needs_data_analysis_all_fields_formatted(self):
        """Test that all NeedsDataAnalysis fields are formatted correctly."""
        results = {
            "status": "needs_data",
            "current_hypothesis": "Likely memory leak in connection pool",
            "missing_evidence": ["Heap dump", "GC logs"],
            "next_steps": ["Enable heap dumps", "Add GC logging"],
            "eliminated": ["Network issues - no errors in logs"],
        }

        topics = self.formatter.format_analysis_topics(results)

        # Should have 4 topics
        assert len(topics) == 4

        # Verify all content
        all_text = ""
        for topic in topics:
            for block in topic:
                all_text += block.get("text", {}).get("text", "") + " "

        # Check fields appear in correct order
        hypothesis_pos = all_text.find("Current Assessment")
        missing_pos = all_text.find("Data Needed")
        next_steps_pos = all_text.find("Next Steps")
        eliminated_pos = all_text.find("Ruled Out")

        assert hypothesis_pos < missing_pos < next_steps_pos < eliminated_pos

        # Verify content
        assert "memory leak in connection pool" in all_text
        assert "Heap dump" in all_text
        assert "Enable heap dumps" in all_text
        assert "Network issues" in all_text

    def test_long_text_field_splits_correctly(self):
        """Test that long text fields are split into multiple blocks."""
        long_text = "A" * 3500  # Exceeds 2900 char limit

        results: dict[str, Any] = {
            "status": "resolved",
            "root_cause": long_text,
            "evidence": [],
            "solution": "Short solution",
            "validation": "",
        }

        topics = self.formatter.format_analysis_topics(results)

        # Find root cause topic (should be first)
        root_cause_topic = topics[0]

        # Should have multiple blocks due to length
        assert len(root_cause_topic) > 1

        # First block should have "Root Cause"
        assert "Root Cause:" in root_cause_topic[0]["text"]["text"]

        # Second block should have "Root Cause (continued)"
        assert "Root Cause (continued):" in root_cause_topic[1]["text"]["text"]

    def test_empty_fields_not_included(self):
        """Test that empty fields are not included in output."""
        results: dict[str, Any] = {
            "status": "resolved",
            "root_cause": "Simple cause",
            "evidence": [],  # Empty list
            "solution": "",  # Empty string
            "validation": None,  # None value
        }

        topics = self.formatter.format_analysis_topics(results)

        # Should only have root_cause topic
        assert len(topics) == 1

        # Verify only root cause is present
        all_text = topics[0][0]["text"]["text"]
        assert "Root Cause" in all_text
        assert "Simple cause" in all_text

    def test_should_use_dynamic_formatting_detection(self):
        """Test detection of troubleshooting results."""
        # Test with resolved status
        assert self.formatter.should_use_dynamic_formatting({"status": "resolved"})

        # Test with needs_data status
        assert self.formatter.should_use_dynamic_formatting({"status": "needs_data"})

        # Test with troubleshooting fields
        assert self.formatter.should_use_dynamic_formatting({"root_cause": "test"})
        assert self.formatter.should_use_dynamic_formatting(
            {"current_hypothesis": "test"}
        )

        # Test with non-troubleshooting data
        assert not self.formatter.should_use_dynamic_formatting({"status": "open"})
        assert not self.formatter.should_use_dynamic_formatting(
            {"recommended_labels": []}
        )

    def test_list_field_formatting(self):
        """Test that list fields are formatted as bullet points."""
        results = {
            "status": "needs_data",
            "current_hypothesis": "",
            "missing_evidence": [],
            "next_steps": ["Step 1", "Step 2", "Step 3"],
            "eliminated": [],
        }

        topics = self.formatter.format_analysis_topics(results)

        # Should have next_steps topic
        assert len(topics) == 1

        text = topics[0][0]["text"]["text"]

        # Verify bullet formatting
        assert "• Step 1" in text
        assert "• Step 2" in text
        assert "• Step 3" in text

    def test_field_order_configuration(self):
        """Test that fields appear in configured order."""
        # Verify configuration is correct
        resolved_config = self.formatter.FIELD_CONFIG["resolved"]

        # Check order values
        assert resolved_config["root_cause"]["order"] == 1
        assert resolved_config["evidence"]["order"] == 2
        assert resolved_config["validation"]["order"] == 3
        assert resolved_config["solution"]["order"] == 4

        needs_data_config = self.formatter.FIELD_CONFIG["needs_data"]

        assert needs_data_config["current_hypothesis"]["order"] == 1
        assert needs_data_config["missing_evidence"]["order"] == 2
        assert needs_data_config["next_steps"]["order"] == 3
        assert needs_data_config["eliminated"]["order"] == 4
