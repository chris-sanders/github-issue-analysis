"""MCP server integration for troubleshooting capabilities."""

import logging
import os
import tempfile

from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)


def troubleshoot_mcp_server(
    sbctl_token: str, github_token: str | None = None
) -> MCPServerStdio:
    """
    Create MCP server instance for troubleshooting tools.

    Args:
        sbctl_token: SBCTL token for MCP server authentication
        github_token: GitHub API token for GitHub operations (optional)

    Returns:
        MCPServerStdio instance configured for troubleshooting
    """
    # Create isolated temporary directory for this analysis
    isolated_temp = tempfile.mkdtemp(prefix="mcp-troubleshoot-")
    logger.info(f"Created MCP workspace: {isolated_temp}")

    # Prepare environment
    env = os.environ.copy()
    env["SBCTL_TOKEN"] = sbctl_token
    env["TMPDIR"] = isolated_temp
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    env["PYTHONWARNINGS"] = "ignore"

    if github_token:
        env["GITHUB_TOKEN"] = github_token
        logger.debug("GitHub token provided to MCP server")

    # Redirect stderr to a log file for debugging instead of suppressing
    # The external MCP package doesn't respect log level env vars anyway
    log_file = f"{isolated_temp}/mcp-server.log"
    return MCPServerStdio(
        "sh",
        args=["-c", f"uv run troubleshoot-mcp-server 2>{log_file}"],
        env=env,
        timeout=120.0,  # Increased timeout for GPT-5 compatibility
    )
