"""MCP server utilities for summary runners - now using temporal framework.

This module re-exports the framework's create_mcp_toolset for backward compatibility.
New code should import directly from temporal_framework.
"""

from temporal_framework import create_mcp_toolset

# Re-export for backward compatibility
__all__ = ["create_mcp_toolset", "create_troubleshoot_mcp_server"]


def create_troubleshoot_mcp_server() -> object:
    """Create troubleshoot-mcp-server using temporal framework.

    This is a legacy compatibility function. New code should use:
        from temporal_framework import create_mcp_toolset
        mcp_tools = create_mcp_toolset("troubleshoot-mcp-server", token_env="SBCTL_TOKEN")

    Returns:
        MCPServerStdio instance configured for troubleshooting
    """
    return create_mcp_toolset(
        server_command="troubleshoot-mcp-server",
        token_env="SBCTL_TOKEN",
        env={"PYTHONWARNINGS": "ignore"},
        timeout=120.0,
        toolset_id="troubleshoot-mcp",
    )
