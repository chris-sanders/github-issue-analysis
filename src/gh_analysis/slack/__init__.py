"""Slack integration module for GitHub issue analysis notifications."""

from .client import SlackClient
from .config import SlackConfig

__all__ = ["SlackClient", "SlackConfig"]
