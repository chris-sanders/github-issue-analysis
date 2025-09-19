"""Integration tests for Slack notifications with troubleshooting analysis results."""

from unittest.mock import patch

from gh_analysis.ai.models import ResolvedAnalysis, NeedsDataAnalysis
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig


class TestTroubleshootingSlackIntegration:
    """Test Slack notifications with actual troubleshooting result structures."""

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_resolved_analysis_displays_correctly(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that ResolvedAnalysis results display correctly in Slack."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Use ACTUAL ResolvedAnalysis dataclass
        resolved_analysis = ResolvedAnalysis(
            root_cause="The service fails to start because the database connection string is malformed",
            evidence=[
                "Error log shows: 'Invalid connection string format'",
                "Service crashes immediately after attempting database connection",
                "Connection string contains unescaped special characters",
            ],
            solution="Escape special characters in the database password using URL encoding",
            validation="The error message directly indicates connection string parsing failure",
        )

        # This is what the CLI actually does - passes model_dump() output
        resolved_results = resolved_analysis.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Service startup failure",
            resolved_results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Verify all content is present
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        blocks = call_args["blocks"]

        all_text = self._extract_all_text(blocks)

        # Verify critical content is displayed
        assert "database connection string is malformed" in all_text, (
            "Root cause not found"
        )
        assert "Invalid connection string format" in all_text, "Evidence not found"
        assert "Escape special characters" in all_text, "Solution not found"
        assert "directly indicates connection string parsing failure" in all_text, (
            "Validation not found"
        )

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_needs_data_analysis_displays_correctly(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that NeedsDataAnalysis results display correctly in Slack."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Use ACTUAL NeedsDataAnalysis dataclass
        needs_data_analysis = NeedsDataAnalysis(
            current_hypothesis="Likely a memory leak but need heap dumps to confirm",
            missing_evidence=[
                "Heap dump from when memory usage is high",
                "GC logs showing collection frequency",
                "Thread dump to check for thread leaks",
            ],
            next_steps=[
                "Enable heap dump on OutOfMemoryError with -XX:+HeapDumpOnOutOfMemoryError",
                "Enable GC logging with -Xlog:gc*",
                "Take thread dump when memory is high using jstack",
            ],
            eliminated=["Network issues - no connection errors in logs"],
        )

        # This is what the CLI actually does - passes model_dump() output
        needs_data_results = needs_data_analysis.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/2",
            "Memory leak investigation",
            needs_data_results,
            "gpt5_mini_medium_mt",
        )

        assert success

        call_args = mock_bot_client.chat_postMessage.call_args[1]
        blocks = call_args["blocks"]

        all_text = self._extract_all_text(blocks)

        # Verify all needs_data fields are displayed
        assert "Likely a memory leak" in all_text, "Current hypothesis not found"
        assert "Heap dump from when memory usage is high" in all_text, (
            "Missing evidence not found"
        )
        assert "Enable heap dump" in all_text, "Next steps not found"
        assert "HeapDumpOnOutOfMemoryError" in all_text, "Next steps details not found"
        assert "Network issues" in all_text, "Eliminated items not found"
        # Solution should NOT appear for needs_data
        assert "Recommended Solution" not in all_text, (
            "Solution shown for needs_data status"
        )

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_topic_ordering_with_troubleshooting_data(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that topics appear in correct order for troubleshooting results."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Use ACTUAL ResolvedAnalysis dataclass
        resolved = ResolvedAnalysis(
            root_cause="Configuration file missing",
            evidence=["Error: config.yaml not found"],
            solution="Create config.yaml with required settings",
            validation="Error directly indicates missing file",
        )
        results = resolved.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/3",
            "Config issue",
            results,
            "gpt5_mini_medium_mt",
        )

        assert success

        call_args = mock_bot_client.chat_postMessage.call_args[1]
        blocks = call_args["blocks"]

        # Find the order of sections
        root_cause_index = -1
        evidence_index = -1
        solution_index = -1

        for i, block in enumerate(blocks):
            if block.get("type") == "section" and "text" in block:
                text = block["text"]["text"]
                if "*Root Cause:*" in text:
                    root_cause_index = i
                elif "*Key Evidence:*" in text:
                    evidence_index = i
                elif "*Recommended Solution:*" in text:
                    solution_index = i

        # Critical assertions that would have caught the bug
        assert root_cause_index != -1, "Root Cause section missing"
        assert evidence_index != -1, "Evidence section missing"
        assert solution_index != -1, "Solution section missing"

        # Root Cause MUST come before Evidence
        assert root_cause_index < evidence_index, (
            f"Root Cause (index {root_cause_index}) must appear before "
            f"Evidence (index {evidence_index})"
        )

        # Evidence should come before Solution
        assert evidence_index < solution_index, (
            f"Evidence (index {evidence_index}) must appear before "
            f"Solution (index {solution_index})"
        )

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_very_long_troubleshooting_content_splits_correctly(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that very long troubleshooting content triggers multi-message flow."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Create very long content that should trigger splitting
        long_root_cause = (
            """The issue is caused by a complex interaction between multiple system components.
        """
            + "A" * 3000
        )  # Make it very long

        long_solution = (
            """To resolve this issue, follow these detailed steps:
        """
            + "B" * 3000
        )  # Make it very long

        # Use ACTUAL ResolvedAnalysis dataclass
        resolved = ResolvedAnalysis(
            root_cause=long_root_cause,
            evidence=[f"Evidence point {i}" for i in range(20)],
            solution=long_solution,
            validation="Multiple validation points confirm this analysis",
        )
        results = resolved.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/4",
            "Complex system issue",
            results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Should have multiple messages for very long content
        assert mock_bot_client.chat_postMessage.call_count > 1, (
            "Long content should trigger multi-message posting"
        )

        # Verify thread organization
        calls = mock_bot_client.chat_postMessage.call_args_list
        first_call = calls[0][1]
        assert "thread_ts" not in first_call, "First message should create thread"

        for call in calls[1:]:
            assert "thread_ts" in call[1], (
                "Subsequent messages should be thread replies"
            )

    def _extract_all_text(self, blocks):
        """Helper to extract all text from Slack blocks."""
        all_text = ""
        for block in blocks:
            if block.get("type") == "section" and "text" in block:
                all_text += block["text"]["text"] + " "
            elif block.get("type") == "context":
                for element in block.get("elements", []):
                    if element.get("type") == "mrkdwn":
                        all_text += element.get("text", "") + " "
        return all_text


class TestFieldCompatibility:
    """Test that Slack handles exact troubleshooting datatypes."""

    def test_troubleshooting_datatypes_handled(self):
        """Verify Slack handles the exact datatypes from troubleshooting agents."""
        client = SlackClient(SlackConfig())

        # Test ACTUAL ResolvedAnalysis dataclass
        resolved = ResolvedAnalysis(
            root_cause="Database connection timeout",
            evidence=["Timeout in logs", "Connection pool exhausted"],
            solution="Increase connection timeout to 30s",
            validation="Logs confirm timeout at connection phase",
        )
        resolved_analysis = resolved.model_dump()

        # Test ACTUAL NeedsDataAnalysis dataclass
        needs_data = NeedsDataAnalysis(
            current_hypothesis="Memory leak suspected",
            missing_evidence=["Heap dump", "GC logs"],
            next_steps=["Enable heap dumps", "Monitor memory"],
            eliminated=["Network issues - no errors"],
        )
        needs_data_analysis = needs_data.model_dump()

        # Test that ResolvedAnalysis solution field works
        blocks = client._format_solution_topic(resolved_analysis)
        assert len(blocks) > 0, "ResolvedAnalysis solution not formatted"
        assert "Increase connection timeout" in blocks[0]["text"]["text"]

        # Test that NeedsDataAnalysis has no solution
        blocks = client._format_solution_topic(needs_data_analysis)
        assert blocks == [], "NeedsDataAnalysis should have no solution"

    def test_missing_field_graceful_handling(self):
        """Test that missing fields are handled gracefully."""
        client = SlackClient(SlackConfig())

        # Neither field present
        results = {"status": "resolved"}  # No solution field
        blocks = client._format_solution_topic(results)
        assert blocks == [], "Should return empty list when solution missing"

        # Wrong status
        results = {"status": "needs_data", "solution": "This shouldn't show"}
        blocks = client._format_solution_topic(results)
        assert blocks == [], "Should not show solution for needs_data status"
