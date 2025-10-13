"""
Type aliases for GitHub issue data structures.

This module provides clear type definitions for working with GitHub issue data
from the upstream github-issue-analysis package.
"""

from typing import Any

# Type alias for issue references: (org, repo, issue_number)
IssueRef = tuple[str, str, int]

# Type alias for StoredIssue.model_dump() - the format returned by IssueLoader
# Structure: {"org": str, "repo": str, "issue": GitHubIssue, "metadata": dict}
StoredIssueDict = dict[str, Any]

# Type alias for the collection of loaded issues
LoadedIssues = list[StoredIssueDict]
