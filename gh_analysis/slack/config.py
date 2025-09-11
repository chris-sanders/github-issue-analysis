"""Configuration for Slack integration."""

import os
from typing import Optional


class SlackConfig:
    """Configuration class for Slack API integration."""

    def __init__(self) -> None:
        """Initialize Slack configuration from environment variables."""
        self.bot_token: Optional[str] = os.getenv("SLACK_BOT_TOKEN")
        self.user_token: Optional[str] = os.getenv("SLACK_USER_TOKEN")
        self.channel: str = os.getenv("SLACK_CHANNEL", "#support-chat")

    def is_configured(self) -> bool:
        """Check if Slack is properly configured."""
        return self.bot_token is not None and self.user_token is not None

    def validate(self) -> None:
        """Validate configuration and raise error if invalid."""
        missing_tokens = []
        if not self.bot_token:
            missing_tokens.append("SLACK_BOT_TOKEN")
        if not self.user_token:
            missing_tokens.append("SLACK_USER_TOKEN")

        if missing_tokens:
            raise ValueError(
                f"Environment variables required for Slack notifications: {', '.join(missing_tokens)}"
            )
