"""MCP adapter to bridge between utils and github-issue-analysis."""

import logging
import os
import tempfile
from typing import Any

from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)


def create_troubleshoot_mcp_server(log_handler: Any | None = None) -> MCPServerStdio:
    """Create MCP server using github-issue-analysis's local approach.

    This adapter provides the same interface as utils.mcp but uses
    our local uv run approach instead of podman.
    """
    sbctl_token = os.getenv("SBCTL_TOKEN")
    if not sbctl_token:
        raise ValueError("SBCTL_TOKEN environment variable is required")

    github_token = os.getenv("GITHUB_TOKEN")  # Optional in our case

    # Create isolated temp directory (matching utils pattern)
    isolated_temp = tempfile.mkdtemp(prefix="mcp-troubleshoot-")
    logger.info(f"Created MCP workspace: {isolated_temp}")

    # Prepare environment (matching current implementation)
    env = os.environ.copy()
    env["SBCTL_TOKEN"] = sbctl_token
    env["TMPDIR"] = isolated_temp
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    env["PYTHONWARNINGS"] = "ignore"

    if github_token:
        env["GITHUB_TOKEN"] = github_token
        logger.debug("GitHub token provided to MCP server")

    # Use our local uv run approach (preserving current behavior)
    log_file = f"{isolated_temp}/mcp-server.log"
    return MCPServerStdio(
        "sh",
        args=["-c", f"uv run troubleshoot-mcp-server 2>{log_file}"],
        env=env,
        timeout=120.0,  # Longer timeout for GPT-5 compatibility
        max_retries=3,  # Match our current retry logic
    )
