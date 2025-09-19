"""Unit tests for Slack message splitting functionality."""

from unittest.mock import patch
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig
from gh_analysis.slack.text_utils import (
    split_text_at_boundaries,
    create_continuation_header,
)


class TestTextSplitting:
    """Test text splitting utilities."""

    def test_short_text_no_splitting(self):
        """Test that short text is returned as-is."""
        text = "Short content"
        result = split_text_at_boundaries(text, 2900)
        assert result == [text]
        assert len(result[0]) <= 2900

    def test_long_text_paragraph_splitting(self):
        """Test splitting long text at paragraph boundaries."""
        # Create text that exceeds 2900 chars to trigger splitting
        paragraph1 = "A" * 1500 + "."
        paragraph2 = "B" * 1500 + "."
        text = paragraph1 + "\n\n" + paragraph2

        result = split_text_at_boundaries(text, 2900)
        assert len(result) == 2
        assert len(result[0]) <= 2900
        assert len(result[1]) <= 2900
        assert paragraph1 in result[0]
        assert paragraph2 in result[1]

    def test_very_long_text_sentence_splitting(self):
        """Test splitting very long paragraph by sentences."""
        # Create very long paragraph that needs sentence splitting
        sentences = [
            f"This is a much longer sentence {i} with more words to make it exceed the limit."
            for i in range(100)
        ]
        text = " ".join(sentences)

        result = split_text_at_boundaries(text, 2900)
        assert len(result) > 1
        for part in result:
            assert len(part) <= 2900

        # Verify all content preserved
        rejoined = " ".join(result).replace("  ", " ")
        assert rejoined.strip() == text.strip()

    def test_continuation_headers(self):
        """Test continuation header generation."""
        assert create_continuation_header("Root Cause", False) == "Root Cause"
        assert (
            create_continuation_header("Root Cause", True) == "Root Cause (continued)"
        )

    def test_empty_text_handling(self):
        """Test handling of empty or whitespace-only text."""
        assert split_text_at_boundaries("", 2900) == [""]
        assert split_text_at_boundaries("   ", 2900) == ["   "]

    def test_exact_boundary_text(self):
        """Test text that exactly matches the boundary."""
        text = "A" * 2900
        result = split_text_at_boundaries(text, 2900)
        assert result == [text]
        assert len(result[0]) == 2900


class TestTopicFormatting:
    """Test topic-based formatting methods."""

    def setup_method(self):
        """Set up test instance."""
        self.client = SlackClient(SlackConfig())

    def test_status_topic_always_fits(self):
        """Test that status topic always fits in expected blocks."""
        results = {"status": "resolved"}
        blocks = self.client._format_status_topic(results, "test_agent")

        assert len(blocks) == 2  # Status message + status field
        assert "✅" in blocks[0]["text"]["text"]
        assert "test_agent" in blocks[0]["text"]["text"]

    def test_root_cause_topic_short_content(self):
        """Test root cause formatting with short content."""
        results = {"root_cause": "Simple root cause", "status": "resolved"}
        blocks = self.client._format_root_cause_topic(results)

        assert len(blocks) == 1
        assert "Simple root cause" in blocks[0]["text"]["text"]
        assert "*Root Cause:*" in blocks[0]["text"]["text"]

    def test_root_cause_topic_long_content_splitting(self):
        """Test root cause formatting with content that requires splitting."""
        # Create root cause longer than 2900 chars
        long_cause = "A" * 3000
        results = {"root_cause": long_cause, "status": "resolved"}
        blocks = self.client._format_root_cause_topic(results)

        assert len(blocks) > 1
        assert "*Root Cause:*" in blocks[0]["text"]["text"]
        assert "*Root Cause (continued):*" in blocks[1]["text"]["text"]

        # Verify all content preserved (extract content after formatting headers)
        combined_content = ""
        for block in blocks:
            text = block["text"]["text"]
            # Remove formatting header to get just the content
            if text.startswith("*Root Cause:*\n"):
                combined_content += text[14:]  # Remove "*Root Cause:*\n"
            elif text.startswith("*Root Cause (continued):*\n"):
                combined_content += text[26:]  # Remove "*Root Cause (continued):*\n"

        assert combined_content == long_cause

    def test_evidence_topic_with_many_points(self):
        """Test evidence formatting with many evidence points."""
        evidence = [f"Evidence point {i}" for i in range(10)]
        results = {"evidence": evidence}
        blocks = self.client._format_evidence_topic(results)

        assert len(blocks) >= 1
        text_content = blocks[0]["text"]["text"]
        assert "Evidence point 0" in text_content
        assert "Evidence point 4" in text_content  # First 5 items
        assert "and 5 more points" in text_content  # Overflow indicator

    def test_empty_topics_filtered(self):
        """Test that empty topics are correctly filtered out."""
        results = {"status": "needs_data"}  # No root_cause or solution

        root_cause_blocks = self.client._format_root_cause_topic(results)
        solution_blocks = self.client._format_solution_topic(results)

        assert root_cause_blocks == []
        assert solution_blocks == []

    def test_solution_topic_formatting(self):
        """Test solution topic formatting."""
        results = {"recommended_solution": "Simple solution", "status": "resolved"}
        blocks = self.client._format_solution_topic(results)

        assert len(blocks) == 1
        assert "Simple solution" in blocks[0]["text"]["text"]
        assert "*Recommended Solution:*" in blocks[0]["text"]["text"]

    def test_next_steps_topic_formatting(self):
        """Test next steps topic formatting."""
        next_steps = ["Step 1", "Step 2", "Step 3"]
        results = {"next_steps": next_steps, "status": "needs_data"}
        blocks = self.client._format_next_steps_topic(results)

        assert len(blocks) == 1
        text_content = blocks[0]["text"]["text"]
        assert "Step 1" in text_content
        assert "Step 2" in text_content
        assert "Step 3" in text_content

    def test_footer_topic_format(self):
        """Test footer topic formatting."""
        blocks = self.client._format_footer_topic()

        assert len(blocks) == 1
        assert blocks[0]["type"] == "context"
        assert "Analysis completed at" in blocks[0]["elements"][0]["text"]


class TestMessageStrategy:
    """Test message posting strategy decisions."""

    def setup_method(self):
        """Set up test instance."""
        self.client = SlackClient(SlackConfig())

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_single_message_for_small_content(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test single message strategy for small content."""

        mock_search.return_value = None  # No existing thread
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Small analysis results that should fit in single message
        results = {
            "status": "resolved",
            "root_cause": "Simple cause",
            "recommended_solution": "Simple solution",
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1", "Test Issue", results, "test_agent"
        )

        assert success
        assert mock_bot_client.chat_postMessage.call_count == 1  # Single message

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_multi_message_for_large_content(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test multi-message strategy for large content."""

        mock_search.return_value = None  # No existing thread
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Large analysis results that require splitting
        results = {
            "status": "resolved",
            "root_cause": "A" * 5000,  # Very long content
            "recommended_solution": "B" * 5000,  # Very long content
            "evidence": [f"Evidence {i}" for i in range(20)],  # Many evidence points
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1", "Test Issue", results, "test_agent"
        )

        assert success
        assert mock_bot_client.chat_postMessage.call_count > 1  # Multiple messages

        # Verify thread organization
        calls = mock_bot_client.chat_postMessage.call_args_list
        first_call = calls[0][1]  # First message
        assert "thread_ts" not in first_call  # First message creates thread

        for call in calls[1:]:  # Subsequent messages
            assert "thread_ts" in call[1]  # Should be thread replies
            assert call[1]["thread_ts"] == "123"  # Same thread

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_thread_reply_for_existing_issue(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test replying to existing thread."""

        mock_search.return_value = "existing_thread_123"  # Existing thread
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "456"}

        results = {
            "status": "resolved",
            "root_cause": "Simple cause",
            "recommended_solution": "Simple solution",
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1", "Test Issue", results, "test_agent"
        )

        assert success

        # Verify it posted to the existing thread
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        assert call_args["thread_ts"] == "existing_thread_123"

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_partial_posting_failure_handling(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test handling of partial posting failures."""

        mock_search.return_value = None

        # Simulate partial failure - first message succeeds, second fails
        # Create enough responses to handle any number of messages
        mock_responses = [
            {"ok": True, "ts": "123.456"},  # First message succeeds
            {"ok": False, "error": "rate_limited"},  # Second message fails
            {"ok": True, "ts": "123.789"},  # Third message succeeds
            {"ok": True, "ts": "123.999"},  # Fourth message succeeds
            {"ok": True, "ts": "124.000"},  # Fifth message (if needed)
            {"ok": True, "ts": "124.001"},  # Sixth message (if needed)
        ]
        mock_bot_client.chat_postMessage.side_effect = mock_responses

        results = {
            "status": "resolved",
            "root_cause": "A" * 4000,  # Forces multi-message
            "solution": "B" * 4000,  # Use 'solution' for troubleshooting
            "evidence": ["Evidence 1", "Evidence 2"],  # Add evidence
            "validation": "Validation text",  # Add validation
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1", "Test Issue", results, "test_agent"
        )

        assert not success  # Should fail due to partial failure
        # With dynamic formatter, we have status + multiple content topics + footer
        # The exact count depends on how content splits
        assert mock_bot_client.chat_postMessage.call_count >= 3  # At least 3 messages


class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.client = SlackClient(SlackConfig())

    def test_slack_config_unchanged(self):
        """Test that SlackConfig interface hasn't changed."""
        config = SlackConfig()

        # These methods should still exist
        assert hasattr(config, "is_configured")
        assert hasattr(config, "validate")

    def test_notify_analysis_complete_signature_unchanged(self):
        """Test that notify_analysis_complete method signature is unchanged."""
        # Method should accept same parameters as before
        method = getattr(self.client, "notify_analysis_complete")
        assert callable(method)

        # Should have the expected parameter names in signature
        import inspect

        sig = inspect.signature(method)
        expected_params = ["issue_url", "issue_title", "analysis_results", "agent_name"]
        actual_params = list(
            sig.parameters.keys()
        )  # Don't skip 'self' for bound method
        assert actual_params == expected_params

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_normal_content_uses_single_message(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that normal-sized content still uses single message (backward compatibility)."""

        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Normal-sized content (should use single message like before)
        results = {
            "status": "resolved",
            "root_cause": "This is a normal-sized root cause analysis.",
            "solution": "This is a normal-sized solution.",  # Use 'solution' for troubleshooting
            "evidence": ["Evidence 1", "Evidence 2", "Evidence 3"],
        }

        success = self.client.notify_analysis_complete(
            "https://github.com/test/test/issues/1", "Test Issue", results, "test_agent"
        )

        assert success
        assert mock_bot_client.chat_postMessage.call_count == 1  # Single message

        # Verify the message contains expected content
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        assert "blocks" in call_args

        # Extract all text from blocks to verify content preservation
        all_text = ""
        for block in call_args["blocks"]:
            if block.get("type") == "section" and "text" in block:
                all_text += block["text"].get("text", "")

        assert "normal-sized root cause" in all_text
        assert "normal-sized solution" in all_text
        assert "Evidence 1" in all_text

    def test_topic_ordering_root_cause_first(self):
        """Test that Root Cause appears before Evidence in topic order."""
        results = {
            "status": "resolved",
            "root_cause": "Test root cause",
            "evidence": ["Evidence 1", "Evidence 2"],
            "solution": "Test solution",
        }

        # Use internal method to verify ordering
        client = SlackClient(SlackConfig())

        # Get all topics in the actual order used by notify_analysis_complete
        all_topics = [
            client._format_status_topic(results, "test_agent"),
            client._format_root_cause_topic(results),
            client._format_evidence_topic(results),
            client._format_solution_topic(results),
            client._format_next_steps_topic(results),
            client._format_footer_topic(),
        ]

        # Filter non-empty topics
        non_empty_topics = [topic for topic in all_topics if topic]

        # Find indices of root cause and evidence topics
        root_cause_index = -1
        evidence_index = -1

        for i, topic in enumerate(non_empty_topics):
            if topic and len(topic) > 0:
                text = topic[0].get("text", {}).get("text", "")
                if "Root Cause" in text:
                    root_cause_index = i
                elif "Evidence" in text:
                    evidence_index = i

        # Root Cause should come before Evidence
        assert root_cause_index < evidence_index, (
            "Root Cause must appear before Evidence"
        )
        assert root_cause_index == 1, "Root Cause should be second topic (after status)"

    def test_solution_field_mapping_backward_compatibility(self):
        """Test that both 'solution' and 'recommended_solution' fields work."""
        client = SlackClient(SlackConfig())

        # Test with 'solution' field (new troubleshooting format)
        results_new = {"status": "resolved", "solution": "Fix using new format"}
        blocks = client._format_solution_topic(results_new)
        assert len(blocks) == 1
        assert "Fix using new format" in blocks[0]["text"]["text"]

        # Test with 'recommended_solution' field (old format)
        results_old = {
            "status": "resolved",
            "recommended_solution": "Fix using old format",
        }
        blocks = client._format_solution_topic(results_old)
        assert len(blocks) == 1
        assert "Fix using old format" in blocks[0]["text"]["text"]
