"""TemporalAgent definitions for gh-analysis.

Provides agent registry and factory function for creating agents.
All agents use framework utilities (MCP, history, etc.).
"""

from .troubleshoot import get_agent, AVAILABLE_AGENTS

__all__ = ["get_agent", "AVAILABLE_AGENTS"]
