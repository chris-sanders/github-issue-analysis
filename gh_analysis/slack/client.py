"""Slack client for GitHub issue analysis notifications."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import SlackConfig

logger = logging.getLogger(__name__)


class SlackClient:
    """Client for sending Slack notifications about GitHub issue analysis."""

    def __init__(self, config: Optional[SlackConfig] = None) -> None:
        """Initialize Slack client with configuration."""
        self.config = config or SlackConfig()
        self._bot_client: Optional[WebClient] = None
        self._user_client: Optional[WebClient] = None

    @property
    def bot_client(self) -> WebClient:
        """Get or create Slack WebClient instance for bot token (posting messages)."""
        if self._bot_client is None:
            self.config.validate()
            self._bot_client = WebClient(token=self.config.bot_token)
        return self._bot_client

    @property
    def user_client(self) -> WebClient:
        """Get or create Slack WebClient instance for user token (searching messages)."""
        if self._user_client is None:
            self.config.validate()
            self._user_client = WebClient(token=self.config.user_token)
        return self._user_client

    def search_for_issue(self, issue_url: str) -> Optional[str]:
        """
        Search for a GitHub issue in the configured Slack channel.

        Args:
            issue_url: The GitHub issue URL to search for

        Returns:
            The thread timestamp (ts) if found, None otherwise
        """
        try:
            # Extract issue number and repo from URL for better searching
            parsed = urlparse(issue_url)
            path_parts = parsed.path.strip("/").split("/")
            if len(path_parts) >= 4 and path_parts[2] == "issues":
                issue_number = path_parts[3]
                repo_name = f"{path_parts[0]}/{path_parts[1]}"

                # Search for messages containing the issue URL or issue reference
                search_query = f"in:{self.config.channel.lstrip('#')} {issue_url}"

                result = self.user_client.search_messages(query=search_query)

                if result["ok"] and result["messages"]["total"] > 0:
                    # Return the timestamp of the first matching message
                    first_match = result["messages"]["matches"][0]
                    return str(first_match["ts"])

                # If direct URL search fails, try searching by issue reference
                search_query = f"in:{self.config.channel.lstrip('#')} #{issue_number}"
                result = self.user_client.search_messages(query=search_query)

                if result["ok"] and result["messages"]["total"] > 0:
                    for match in result["messages"]["matches"]:
                        # Check if the message contains the repo name
                        if repo_name.lower() in match["text"].lower():
                            return str(match["ts"])

        except SlackApiError as e:
            logger.error(f"Error searching for issue in Slack: {e}")
        except Exception as e:
            logger.error(f"Unexpected error searching for issue: {e}")

        return None

    def post_to_thread(
        self,
        thread_ts: str,
        analysis_results: Dict[str, Any],
        issue_url: str,
        agent_name: str,
    ) -> bool:
        """
        Post analysis results to an existing Slack thread.

        Args:
            thread_ts: The thread timestamp to reply to
            analysis_results: The analysis results from the AI agent
            issue_url: The GitHub issue URL
            agent_name: The name of the AI agent used

        Returns:
            True if successful, False otherwise
        """
        try:
            blocks = self._format_analysis_results(
                analysis_results, issue_url, agent_name
            )

            response = self.bot_client.chat_postMessage(
                channel=self.config.channel,
                thread_ts=thread_ts,
                blocks=blocks,
                text="Analysis results available",
            )

            return bool(response["ok"])

        except SlackApiError as e:
            logger.error(f"Error posting to thread in Slack: {e}")
        except Exception as e:
            logger.error(f"Unexpected error posting to thread: {e}")

        return False

    def notify_analysis_complete(
        self,
        issue_url: str,
        issue_title: str,
        analysis_results: Dict[str, Any],
        agent_name: str,
    ) -> bool:
        """
        Send notification about completed analysis.

        This method handles the full workflow:
        1. Search for existing issue thread
        2. If found: Reply to the existing thread with analysis results
        3. If not found: Post new comprehensive message with issue info and results

        Args:
            issue_url: The GitHub issue URL
            issue_title: The title of the GitHub issue
            analysis_results: The analysis results from the AI agent
            agent_name: The name of the AI agent used

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.config.is_configured():
            logger.warning("Slack is not configured, skipping notification")
            return False

        try:
            # Step 1: Search for existing thread
            thread_ts = self.search_for_issue(issue_url)

            if thread_ts:
                # Step 2a: Reply to existing thread with analysis results
                return self.post_to_thread(
                    thread_ts, analysis_results, issue_url, agent_name
                )
            else:
                # Step 2b: Post new comprehensive message
                return self.post_new_message(
                    issue_url, issue_title, analysis_results, agent_name
                )

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    def post_new_message(
        self,
        issue_url: str,
        issue_title: str,
        analysis_results: Dict[str, Any],
        agent_name: str,
    ) -> bool:
        """
        Post a new comprehensive message with issue info and analysis results.

        Args:
            issue_url: The GitHub issue URL
            issue_title: The title of the GitHub issue
            analysis_results: The analysis results from the AI agent
            agent_name: The name of the AI agent used

        Returns:
            True if successful, False otherwise
        """
        try:
            blocks = self._format_comprehensive_message(
                issue_url, issue_title, analysis_results, agent_name
            )

            response = self.bot_client.chat_postMessage(
                channel=self.config.channel,
                blocks=blocks,
                text=f"GitHub Issue Analysis: {issue_title}",
            )

            return bool(response["ok"])

        except SlackApiError as e:
            logger.error(f"Error posting new message to Slack: {e}")
        except Exception as e:
            logger.error(f"Unexpected error posting new message: {e}")

        return False

    def _format_comprehensive_message(
        self,
        issue_url: str,
        issue_title: str,
        analysis_results: Dict[str, Any],
        agent_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Format a comprehensive message with issue info and analysis results.

        Args:
            issue_url: The GitHub issue URL
            issue_title: The title of the GitHub issue
            analysis_results: The analysis results dictionary
            agent_name: The name of the AI agent used

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        # Issue header section
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*GitHub Issue Analysis Complete*\n<{issue_url}|{issue_title}>",
                },
            }
        )

        # Add analysis results using existing formatter
        analysis_blocks = self._format_analysis_results(
            analysis_results, issue_url, agent_name
        )
        blocks.extend(analysis_blocks)

        return blocks

    def _format_analysis_results(
        self, results: Dict[str, Any], issue_url: str, agent_name: str
    ) -> List[Dict[str, Any]]:
        """
        Format analysis results into Slack Block Kit format.

        Args:
            results: The analysis results dictionary
            issue_url: The GitHub issue URL
            agent_name: The name of the AI agent used

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        # Header section
        status = results.get("status", "unknown")
        status_emoji = (
            "✅" if status == "resolved" else "📋" if status == "needs_data" else "❓"
        )

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *Analysis Complete* - Agent: `{agent_name}`",
                },
            }
        )

        # Status section
        if status:
            status_block: Dict[str, Any] = {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:* {status.replace('_', ' ').title()}",
                    }
                ],
            }
            blocks.append(status_block)

        # Root cause (if high confidence)
        root_cause = results.get("root_cause")
        if root_cause and status == "resolved":
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Root Cause:*\n{root_cause}"},
                }
            )

        # Evidence points
        evidence = results.get("evidence", [])
        if evidence:
            evidence_text = "\n".join(
                [f"• {point}" for point in evidence[:5]]
            )  # Limit to 5 points
            if len(evidence) > 5:
                evidence_text += f"\n• ... and {len(evidence) - 5} more points"

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Key Evidence:*\n{evidence_text}",
                    },
                }
            )

        # Solution (if high confidence)
        solution = results.get("recommended_solution")
        if solution and status == "resolved":
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommended Solution:*\n{solution}",
                    },
                }
            )

        # Next steps (if needs data)
        next_steps = results.get("next_steps", [])
        if next_steps and status == "needs_data":
            steps_text = "\n".join([f"• {step}" for step in next_steps[:3]])
            if len(next_steps) > 3:
                steps_text += f"\n• ... and {len(next_steps) - 3} more steps"

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Next Steps:*\n{steps_text}"},
                }
            )

        # Footer with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        footer_block: Dict[str, Any] = {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Analysis completed at {timestamp}"}
            ],
        }
        blocks.append(footer_block)

        return blocks
