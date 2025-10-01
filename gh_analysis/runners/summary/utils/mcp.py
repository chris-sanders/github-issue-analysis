"""MCP server utilities for easy integration."""

import os
from typing import Optional, Callable
from pydantic_ai.mcp import MCPServerStdio


def create_troubleshoot_mcp_server(
    log_handler: Optional[Callable] = None,
) -> MCPServerStdio:
    """Create the troubleshoot MCP server with configuration.

    This provides a simple way to add troubleshoot MCP server support
    to any experiment without needing to configure containers, tokens, etc.
    Each container gets its own isolated filesystem automatically.

    Args:
        log_handler: Optional log handler for MCP server output

    Returns:
        Configured MCPServerStdio instance

    Raises:
        ValueError: If SBCTL_TOKEN or GITHUB_TOKEN environment variables are not set
    """
    sbctl_token = os.getenv("SBCTL_TOKEN")
    if not sbctl_token:
        raise ValueError("SBCTL_TOKEN environment variable is required")

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable is required")

    return MCPServerStdio(
        "sh",
        args=[
            "-c",
            f"podman run --pull=always --rm -i -e SBCTL_TOKEN={sbctl_token} -e GITHUB_TOKEN={github_token} ghcr.io/chris-sanders/troubleshoot-mcp-server/troubleshoot-mcp-server:latest 2>/dev/null",
        ],
        timeout=30.0,  # 30 seconds for server initialization
        max_retries=3,  # Increase retries for tool call formatting issues
    )
