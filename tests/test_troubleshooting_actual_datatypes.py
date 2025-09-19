"""Test that Slack handles the EXACT datatypes returned by troubleshooting agents."""

from unittest.mock import patch

from gh_analysis.ai.models import ResolvedAnalysis, NeedsDataAnalysis
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig


class TestActualTroubleshootingDatatypes:
    """Test with actual dataclass instances to ensure exact compatibility."""

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_resolved_analysis_dataclass(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test with actual ResolvedAnalysis dataclass instance."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Create actual ResolvedAnalysis instance
        resolved = ResolvedAnalysis(
            status="resolved",
            root_cause="The database connection pool is exhausted due to leaked connections",
            evidence=[
                "Connection pool metrics show 100% utilization",
                "Application logs show 'no available connections' errors",
                "Database shows 50+ idle connections from the application",
            ],
            solution="Implement connection timeout and ensure proper connection cleanup in finally blocks",
            validation="The evidence directly shows connection exhaustion and the solution addresses the leak",
        )

        # This is what the CLI does - passes model_dump() to Slack
        analysis_results = resolved.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Database connection failures",
            analysis_results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Verify all fields from ResolvedAnalysis are displayed
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        blocks = call_args["blocks"]
        all_text = self._extract_all_text(blocks)

        # Verify all ResolvedAnalysis fields are present
        assert "database connection pool is exhausted" in all_text, "root_cause missing"
        assert "Connection pool metrics show 100%" in all_text, "evidence missing"
        assert "Implement connection timeout" in all_text, "solution missing"
        assert "evidence directly shows connection exhaustion" in all_text, "validation missing"

        # Verify field is labeled as "Recommended Solution" in UI
        assert "*Recommended Solution:*" in all_text, "Solution not properly labeled"

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_needs_data_analysis_dataclass(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test with actual NeedsDataAnalysis dataclass instance."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Create actual NeedsDataAnalysis instance
        needs_data = NeedsDataAnalysis(
            status="needs_data",
            current_hypothesis="Memory leak suspected based on gradual memory increase over 24 hours",
            missing_evidence=[
                "Heap dump from when memory usage is high",
                "GC logs showing collection frequency and duration",
                "Thread dump to check for thread leaks",
            ],
            next_steps=[
                "Enable heap dumps with -XX:+HeapDumpOnOutOfMemoryError",
                "Add GC logging with -Xlog:gc*:file=gc.log",
                "Schedule heap dump capture at 80% memory usage",
            ],
            eliminated=[
                "Database connection leak - connection pool metrics are stable",
                "External service issues - all downstream services are healthy",
            ],
        )

        # This is what the CLI does - passes model_dump() to Slack
        analysis_results = needs_data.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/2",
            "Application memory constantly increasing",
            analysis_results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Verify all fields from NeedsDataAnalysis are displayed
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        blocks = call_args["blocks"]
        all_text = self._extract_all_text(blocks)

        # Verify all NeedsDataAnalysis fields are present
        assert "Memory leak suspected" in all_text, "current_hypothesis missing"
        assert "Heap dump from when memory" in all_text, "missing_evidence missing"
        assert "Enable heap dumps" in all_text, "next_steps missing"
        assert "Database connection leak" in all_text, "eliminated missing"

        # Verify NO solution is shown (NeedsDataAnalysis has no solution field)
        assert "*Recommended Solution:*" not in all_text, "Solution shown for needs_data"

    def test_dataclass_field_names(self):
        """Verify the exact field names in the dataclasses."""
        # ResolvedAnalysis fields
        resolved = ResolvedAnalysis(
            root_cause="test",
            evidence=["test"],
            solution="test",  # NOT recommended_solution!
            validation="test",
        )

        resolved_dict = resolved.model_dump()
        assert "solution" in resolved_dict, "ResolvedAnalysis should have 'solution' field"
        assert "recommended_solution" not in resolved_dict, "ResolvedAnalysis should NOT have 'recommended_solution'"

        # NeedsDataAnalysis fields
        needs_data = NeedsDataAnalysis(
            current_hypothesis="test",
            missing_evidence=["test"],
            next_steps=["test"],
            eliminated=["test"],
        )

        needs_data_dict = needs_data.model_dump()
        assert "solution" not in needs_data_dict, "NeedsDataAnalysis should NOT have 'solution'"
        assert "recommended_solution" not in needs_data_dict, "NeedsDataAnalysis should NOT have 'recommended_solution'"

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