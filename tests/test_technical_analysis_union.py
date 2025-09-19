"""Test that Slack handles the TechnicalAnalysis union type correctly."""

from typing import Any, Dict, List
from unittest.mock import patch

from gh_analysis.ai.models import ResolvedAnalysis, NeedsDataAnalysis, TechnicalAnalysis
from gh_analysis.slack.client import SlackClient
from gh_analysis.slack.config import SlackConfig


class TestTechnicalAnalysisUnion:
    """Test handling of the TechnicalAnalysis discriminated union."""

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_technical_analysis_union_resolved(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that TechnicalAnalysis union with ResolvedAnalysis works."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Create TechnicalAnalysis as ResolvedAnalysis
        analysis: TechnicalAnalysis = ResolvedAnalysis(
            root_cause="Service timeout due to resource exhaustion",
            evidence=["CPU at 100%", "Memory at 95%", "Thread pool exhausted"],
            solution="Scale service horizontally and increase resource limits",
            validation="Metrics clearly show resource exhaustion pattern",
        )

        # This simulates what the troubleshooting runner returns
        # The CLI calls model_dump() on it
        results = analysis.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/1",
            "Service performance degradation",
            results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Verify the correct fields are displayed
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        all_text = self._extract_all_text(call_args["blocks"])

        assert "resource exhaustion" in all_text
        assert "CPU at 100%" in all_text
        assert "Scale service horizontally" in all_text
        assert "*Recommended Solution:*" in all_text

    @patch("gh_analysis.slack.client.SlackClient.bot_client")
    @patch("gh_analysis.slack.client.SlackClient.search_for_issue")
    @patch("gh_analysis.slack.config.SlackConfig.is_configured", return_value=True)
    def test_technical_analysis_union_needs_data(
        self, mock_configured, mock_search, mock_bot_client
    ):
        """Test that TechnicalAnalysis union with NeedsDataAnalysis works."""
        mock_search.return_value = None
        mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

        # Create TechnicalAnalysis as NeedsDataAnalysis
        analysis: TechnicalAnalysis = NeedsDataAnalysis(
            current_hypothesis="Intermittent network issues suspected (70% confidence)",
            missing_evidence=[
                "Network packet capture during failure",
                "DNS resolution logs",
                "Firewall logs from the time of failure",
            ],
            next_steps=[
                "Enable tcpdump on affected hosts",
                "Check DNS server logs for failures",
                "Review firewall rules and logs",
            ],
            eliminated=[
                "Application bug - code hasn't changed in 30 days",
                "Database issues - DB metrics are normal",
            ],
        )

        # This simulates what the troubleshooting runner returns
        results = analysis.model_dump()

        client = SlackClient(SlackConfig())
        success = client.notify_analysis_complete(
            "https://github.com/test/test/issues/2",
            "Intermittent connection failures",
            results,
            "gpt5_mini_medium_mt",
        )

        assert success

        # Verify the correct fields are displayed
        call_args = mock_bot_client.chat_postMessage.call_args[1]
        all_text = self._extract_all_text(call_args["blocks"])

        assert "Intermittent network issues suspected" in all_text
        assert "Network packet capture" in all_text
        assert "Enable tcpdump" in all_text
        assert "Application bug - code hasn't changed" in all_text
        assert "*Recommended Solution:*" not in all_text  # No solution for needs_data

    def test_technical_analysis_type_compatibility(self):
        """Test that TechnicalAnalysis union works with both types."""
        # This tests the actual type system

        # Both of these should be valid TechnicalAnalysis instances
        resolved: TechnicalAnalysis = ResolvedAnalysis(
            root_cause="Test",
            evidence=["Test"],
            solution="Test",
            validation="Test",
        )

        needs_data: TechnicalAnalysis = NeedsDataAnalysis(
            current_hypothesis="Test",
            missing_evidence=["Test"],
            next_steps=["Test"],
            eliminated=["Test"],
        )

        # Both should produce valid model_dump() output
        resolved_dict = resolved.model_dump()
        needs_data_dict = needs_data.model_dump()

        # Verify discriminator field
        assert resolved_dict["status"] == "resolved"
        assert needs_data_dict["status"] == "needs_data"

        # Verify correct fields exist
        assert "solution" in resolved_dict
        assert "solution" not in needs_data_dict
        assert "current_hypothesis" not in resolved_dict
        assert "current_hypothesis" in needs_data_dict

    def _extract_all_text(self, blocks: List[Dict[str, Any]]) -> str:
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
