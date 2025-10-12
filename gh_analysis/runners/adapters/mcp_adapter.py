"""MCP adapter - now using temporal framework directly.

This module provides convenience wrappers around the temporal framework's
create_mcp_toolset() function for gh-analysis-specific usage patterns.

Per the principle: "If the framework is hard to use, fix THE FRAMEWORK, not gh-analysis."
We use the framework directly and only add convenience functions if we find repeated boilerplate.
"""

import logging

from pydantic_ai.mcp import MCPServerStdio
from temporal_framework import create_mcp_toolset

logger = logging.getLogger(__name__)


def create_troubleshoot_mcp_server(log_handler: object | None = None) -> MCPServerStdio:
    """Create troubleshoot-mcp-server using temporal framework.

    This is a thin convenience wrapper around the framework's create_mcp_toolset()
    that sets gh-analysis's standard configuration for troubleshooting.

    The framework automatically:
    - Handles `uv run` if command not in PATH
    - Creates isolated temp directories
    - Manages environment variables

    Args:
        log_handler: Optional log handler (currently unused, kept for compatibility)

    Returns:
        MCPServerStdio instance configured for troubleshooting

    Raises:
        ValueError: If SBCTL_TOKEN environment variable is not set
    """
    # Use framework directly - it handles everything we need
    return create_mcp_toolset(
        server_command="troubleshoot-mcp-server",
        token_env="SBCTL_TOKEN",  # Framework will check environment
        env={
            # Framework already creates TMPDIR, but we can add gh-analysis-specific vars
            "PYTHONWARNINGS": "ignore",
        },
        timeout=120.0,  # Longer timeout for GPT-5 compatibility
        toolset_id="troubleshoot-mcp",  # Temporal activity identification
    )
