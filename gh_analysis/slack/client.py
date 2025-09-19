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
        """Send notification with topic-based splitting to avoid truncation.

        This method handles the full workflow with content preservation:
        1. Generate topic-based blocks using new formatting methods
        2. Decide between single message vs multi-message based on total block count
        3. Handle both new messages and thread replies with intelligent splitting

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

            # Step 2: Generate all topic blocks
            from .troubleshooting_formatter import TroubleshootingFormatter

            formatter = TroubleshootingFormatter()

            # Check if we should use dynamic formatting for troubleshooting results
            if formatter.should_use_dynamic_formatting(analysis_results):
                # Use dynamic formatting for troubleshooting
                all_topics = []

                # Add status topic first
                all_topics.append(
                    self._format_status_topic(analysis_results, agent_name)
                )

                # Add dynamically formatted troubleshooting fields
                dynamic_topics = formatter.format_analysis_topics(analysis_results)
                all_topics.extend(dynamic_topics)

                # Add footer last
                all_topics.append(self._format_footer_topic())
            else:
                # Fall back to legacy formatting for non-troubleshooting results
                all_topics = [
                    self._format_status_topic(analysis_results, agent_name),
                    self._format_root_cause_topic(
                        analysis_results
                    ),  # Moved before evidence
                    self._format_evidence_topic(
                        analysis_results
                    ),  # Moved after root cause
                    self._format_solution_topic(analysis_results),
                    self._format_next_steps_topic(analysis_results),
                    self._format_footer_topic(),
                ]

            # Filter out empty topics
            non_empty_topics = [topic for topic in all_topics if topic]
            total_blocks = sum(len(topic) for topic in non_empty_topics)

            logger.info(
                f"Generated {len(non_empty_topics)} topics with {total_blocks} total blocks"
            )

            # Step 3: Decide posting strategy - use multi-message if content topics were split
            # Skip status topic (index 0) since it naturally has 2 blocks
            content_topics = non_empty_topics[1:] if non_empty_topics else []
            has_split_content = any(len(topic) > 1 for topic in content_topics)

            if (
                has_split_content or total_blocks > 15
            ):  # Use multi-message for split content
                # Send each topic as separate message in thread
                logger.info(
                    f"Using multi-message posting due to split topics or {total_blocks} blocks"
                )
                if thread_ts:
                    # Post topics as replies to existing thread
                    return self._post_topic_replies_to_thread(
                        non_empty_topics, thread_ts
                    )
                else:
                    # Post topics as new thread
                    return self._post_topic_sequence(
                        non_empty_topics, issue_url, issue_title
                    )
            else:
                # Send as single message for simple content
                logger.info("Using single message posting for simple content")
                all_blocks = [block for topic in non_empty_topics for block in topic]

                if thread_ts:
                    # Reply to existing thread with blocks directly
                    try:
                        response = self.bot_client.chat_postMessage(
                            channel=self.config.channel,
                            thread_ts=thread_ts,
                            blocks=all_blocks,
                            text="Analysis results available",
                        )
                        return bool(response["ok"])
                    except Exception as e:
                        logger.error(f"Error posting to thread: {e}")
                        return False
                else:
                    # New message with issue header
                    blocks_with_header = self._add_issue_header(
                        all_blocks, issue_url, issue_title
                    )
                    return self._post_single_message(blocks_with_header, issue_title)

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
        # Handle both field names for backward compatibility
        solution = results.get("recommended_solution") or results.get("solution")
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

    def _create_section_block(self, title: str, content: str) -> Dict[str, Any]:
        """Helper to create section block with consistent formatting.

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

    def _format_status_topic(
        self, results: Dict[str, Any], agent_name: str
    ) -> List[Dict[str, Any]]:
        """Format status and agent info (always single block).

        Args:
            results: Analysis results
            agent_name: Name of the AI agent used

        Returns:
            List of status blocks
        """
        status = results.get("status", "unknown")
        status_emoji = (
            "✅" if status == "resolved" else "📋" if status == "needs_data" else "❓"
        )

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *Analysis Complete* - Agent: `{agent_name}`",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:* {status.replace('_', ' ').title()}",
                    }
                ],
            },
        ]

    def _format_evidence_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format evidence points (may split if very long).

        Args:
            results: Analysis results

        Returns:
            List of evidence blocks
        """
        evidence = results.get("evidence", [])
        if not evidence:
            return []

        # Limit to 5 points initially
        limited_evidence = evidence[:5]
        evidence_text = "\n".join([f"• {point}" for point in limited_evidence])

        if len(evidence) > 5:
            evidence_text += f"\n• ... and {len(evidence) - 5} more points"

        # Check if text fits in single block
        if len(evidence_text) <= 2900:
            return [self._create_section_block("Key Evidence", evidence_text)]

        # Split evidence into multiple blocks if too long
        from .text_utils import split_text_at_boundaries, create_continuation_header

        parts = split_text_at_boundaries(evidence_text, 2900)
        blocks = []
        for i, part in enumerate(parts):
            title = create_continuation_header("Key Evidence", i > 0)
            blocks.append(self._create_section_block(title, part))
        return blocks

    def _format_root_cause_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format root cause analysis (splits if >2900 chars).

        Args:
            results: Analysis results

        Returns:
            List of root cause blocks
        """
        root_cause = results.get("root_cause")
        status = results.get("status", "unknown")

        if not root_cause or status != "resolved":
            return []

        # Account for formatting overhead ("*Root Cause:*\n" is ~15 chars)
        formatted_length = len(root_cause) + 20  # Buffer for formatting
        if formatted_length <= 2900:
            return [self._create_section_block("Root Cause", root_cause)]

        # Split into multiple blocks with adjusted max length
        from .text_utils import split_text_at_boundaries, create_continuation_header

        # Leave room for title formatting in each part
        max_content_length = 2900 - 30  # Buffer for "*Root Cause (continued):*\n"
        parts = split_text_at_boundaries(root_cause, max_content_length)
        blocks = []
        for i, part in enumerate(parts):
            title = create_continuation_header("Root Cause", i > 0)
            blocks.append(self._create_section_block(title, part))
        return blocks

    def _format_solution_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format recommended solution (splits if >2900 chars).

        Args:
            results: Analysis results

        Returns:
            List of solution blocks
        """
        # Handle both field names for backward compatibility
        solution = results.get("recommended_solution") or results.get("solution")
        status = results.get("status", "unknown")

        if not solution or status != "resolved":
            return []

        # Account for formatting overhead ("*Recommended Solution:*\n" is ~25 chars)
        formatted_length = len(solution) + 30  # Buffer for formatting
        if formatted_length <= 2900:
            return [self._create_section_block("Recommended Solution", solution)]

        # Split into multiple blocks with adjusted max length
        from .text_utils import split_text_at_boundaries, create_continuation_header

        # Leave room for title formatting in each part
        max_content_length = (
            2900 - 40
        )  # Buffer for "*Recommended Solution (continued):*\n"
        parts = split_text_at_boundaries(solution, max_content_length)
        blocks = []
        for i, part in enumerate(parts):
            title = create_continuation_header("Recommended Solution", i > 0)
            blocks.append(self._create_section_block(title, part))
        return blocks

    def _format_next_steps_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format next steps (splits if many steps).

        Args:
            results: Analysis results

        Returns:
            List of next steps blocks
        """
        next_steps = results.get("next_steps", [])
        status = results.get("status", "unknown")

        if not next_steps or status != "needs_data":
            return []

        # Limit to 3 steps initially
        limited_steps = next_steps[:3]
        steps_text = "\n".join([f"• {step}" for step in limited_steps])

        if len(next_steps) > 3:
            steps_text += f"\n• ... and {len(next_steps) - 3} more steps"

        if len(steps_text) <= 2900:
            return [self._create_section_block("Next Steps", steps_text)]

        # Split steps if too long
        from .text_utils import split_text_at_boundaries, create_continuation_header

        parts = split_text_at_boundaries(steps_text, 2900)
        blocks = []
        for i, part in enumerate(parts):
            title = create_continuation_header("Next Steps", i > 0)
            blocks.append(self._create_section_block(title, part))
        return blocks

    def _format_footer_topic(self) -> List[Dict[str, Any]]:
        """Format footer with timestamp (always single block).

        Returns:
            List containing footer block
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

        return [
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Analysis completed at {timestamp}"}
                ],
            }
        ]

    def _add_issue_header(
        self, blocks: List[Dict[str, Any]], issue_url: str, issue_title: str
    ) -> List[Dict[str, Any]]:
        """Add issue header to first message.

        Args:
            blocks: Existing blocks to add header to
            issue_url: GitHub issue URL
            issue_title: Issue title

        Returns:
            Blocks with issue header prepended
        """
        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*GitHub Issue Analysis Complete*\n<{issue_url}|{issue_title}>",
            },
        }
        return [header_block] + blocks

    def _post_single_message(
        self, blocks: List[Dict[str, Any]], issue_title: str
    ) -> bool:
        """Post all content as single message (backward compatibility).

        Args:
            blocks: Slack Block Kit blocks to post
            issue_title: Issue title for fallback text

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.bot_client.chat_postMessage(
                channel=self.config.channel,
                blocks=blocks,
                text=f"GitHub Issue Analysis: {issue_title}",
            )
            return bool(response["ok"])
        except Exception as e:
            logger.error(f"Error posting single message: {e}")
            return False

    def _post_topic_sequence(
        self, topics: List[List[Dict[str, Any]]], issue_url: str, issue_title: str
    ) -> bool:
        """Post topics as separate messages in thread.

        Args:
            topics: List of topic blocks, each containing multiple blocks
            issue_url: GitHub issue URL
            issue_title: Issue title

        Returns:
            True if all messages posted successfully, False otherwise
        """
        thread_ts = None
        success_count = 0
        total_topics = len(topics)

        logger.info(f"Posting {total_topics} topic messages for analysis")

        for i, topic_blocks in enumerate(topics):
            try:
                if i == 0:
                    # First message includes issue header
                    blocks_with_header = self._add_issue_header(
                        topic_blocks, issue_url, issue_title
                    )
                    response = self.bot_client.chat_postMessage(
                        channel=self.config.channel,
                        blocks=blocks_with_header,
                        text=f"GitHub Issue Analysis: {issue_title}",
                    )
                    thread_ts = response["ts"]
                else:
                    # Subsequent messages as thread replies
                    response = self.bot_client.chat_postMessage(
                        channel=self.config.channel,
                        thread_ts=thread_ts,
                        blocks=topic_blocks,
                        text="Analysis continuation",
                    )

                if response["ok"]:
                    success_count += 1
                    logger.info(f"Posted topic {i + 1}/{total_topics} successfully")
                else:
                    logger.error(
                        f"Failed to post topic {i + 1}/{total_topics}: {response}"
                    )

            except Exception as e:
                logger.error(f"Error posting topic {i + 1}/{total_topics}: {e}")

        success = success_count == total_topics
        if success:
            logger.info(f"All {total_topics} topic messages posted successfully")
        else:
            logger.warning(
                f"Only {success_count}/{total_topics} topic messages posted successfully"
            )

        return success

    def _post_topic_replies_to_thread(
        self, topics: List[List[Dict[str, Any]]], thread_ts: str
    ) -> bool:
        """Post topic messages as replies to existing thread.

        Args:
            topics: List of topic blocks, each containing multiple blocks
            thread_ts: Thread timestamp to reply to

        Returns:
            True if all messages posted successfully, False otherwise
        """
        success_count = 0
        total_topics = len(topics)

        for i, topic_blocks in enumerate(topics):
            try:
                response = self.bot_client.chat_postMessage(
                    channel=self.config.channel,
                    thread_ts=thread_ts,
                    blocks=topic_blocks,
                    text="Analysis results",
                )

                if response["ok"]:
                    success_count += 1
                    logger.info(
                        f"Posted topic reply {i + 1}/{total_topics} successfully"
                    )
                else:
                    logger.error(
                        f"Failed to post topic reply {i + 1}/{total_topics}: {response}"
                    )

            except Exception as e:
                logger.error(f"Error posting topic reply {i + 1}/{total_topics}: {e}")

        return success_count == total_topics
