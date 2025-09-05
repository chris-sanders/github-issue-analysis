"""Utils package for github issue experiments."""

from . import checks
from .history import create_history_trimmer
from .types import LoadedIssues, StoredIssueDict

# Conditional imports for optional features
try:
    from .io import IssueLoader, IssueRef, SnowflakeIssueLoader
except ImportError:
    # Snowflake dependencies not available
    IssueLoader = None  # type: ignore
    IssueRef = None  # type: ignore
    SnowflakeIssueLoader = None  # type: ignore

try:
    from .mcp import create_troubleshoot_mcp_server
except ImportError:
    # MCP dependencies not available
    create_troubleshoot_mcp_server = None  # type: ignore

__all__ = [
    "IssueLoader",
    "SnowflakeIssueLoader",
    "IssueRef",
    "StoredIssueDict",
    "LoadedIssues",
    "checks",
    "create_troubleshoot_mcp_server",
    "create_history_trimmer",
]
