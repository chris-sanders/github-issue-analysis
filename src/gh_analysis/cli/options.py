"""Standardized CLI option definitions for consistent shorthand mappings.

This module provides centralized option definitions to ensure consistent
shorthand options across all commands and prevent future drift.
"""

import typer

# Core options - used across most commands
ORG_OPTION = typer.Option(..., "--org", "-o", help="GitHub organization name")
ORG_OPTION_OPTIONAL = typer.Option(None, "--org", "-o", help="GitHub organization name")

REPO_OPTION = typer.Option(None, "--repo", "-r", help="GitHub repository name")

ISSUE_NUMBER_OPTION = typer.Option(
    None, "--issue-number", "-i", help="Specific issue number"
)

# Filter options - used for filtering operations
LABELS_OPTION = typer.Option(
    None, "--labels", "-l", help="Filter by labels (can be used multiple times)"
)

STATE_OPTION = typer.Option(
    "closed", "--state", "-s", help="Issue state: open, closed, or all"
)

LIMIT_OPTION = typer.Option(10, "--limit", help="Maximum number of issues to collect")

# Behavior options - control command behavior
DRY_RUN_OPTION = typer.Option(
    False, "--dry-run", "-d", help="Preview changes without applying them"
)

FORCE_OPTION = typer.Option(
    False, "--force", "-f", help="Apply changes without confirmation"
)

SKIP_COMMENTS_OPTION = typer.Option(
    False, "--skip-comments", help="Skip posting explanatory comments"
)

# Data options - AI processing configuration
MODEL_OPTION = typer.Option(
    "openai:gpt-4o",
    "--model",
    "-m",
    help="AI model to use (e.g., 'openai:gpt-4o-mini')",
)

THINKING_EFFORT_OPTION = typer.Option(
    None, "--thinking-effort", help="Reasoning effort level (low, medium, high)"
)

THINKING_BUDGET_OPTION = typer.Option(
    None, "--thinking-budget", help="Thinking token budget for models"
)

TEMPERATURE_OPTION = typer.Option(
    0.0, "--temperature", help="Model temperature (0.0-2.0)"
)

RETRY_COUNT_OPTION = typer.Option(
    2, "--retry-count", help="Number of retries on failure"
)

INCLUDE_IMAGES_OPTION = typer.Option(
    True, "--include-images/--no-include-images", help="Include image analysis"
)

# Repository exclusion options
EXCLUDE_REPO_OPTION = typer.Option(
    None,
    "--exclude-repo",
    "-x",
    help="Repository to exclude from organization-wide search",
)

EXCLUDE_REPOS_OPTION = typer.Option(
    None,
    "--exclude-repos",
    help="Comma-separated list of repositories to exclude",
)

# Authentication options
TOKEN_OPTION = typer.Option(
    None, "--token", "-t", help="GitHub API token (defaults to GITHUB_TOKEN env var)"
)

# Processing options
REPROCESS_OPTION = typer.Option(
    False, "--reprocess", help="Force reprocessing of items already processed"
)

MAX_ISSUES_OPTION = typer.Option(
    None, "--max-issues", help="Maximum number of issues to process"
)

DELAY_OPTION = typer.Option(0.0, "--delay", help="Delay between API calls in seconds")

# Configuration options
DATA_DIR_OPTION = typer.Option(
    None, "--data-dir", help="Data directory path (defaults to ./data)"
)

MIN_CONFIDENCE_OPTION = typer.Option(
    0.8, "--min-confidence", help="Minimum confidence threshold"
)

IGNORE_STATUS_OPTION = typer.Option(
    False,
    "--ignore-status",
    help="Process all recommendations regardless of approval status",
)

# Attachment options
DOWNLOAD_ATTACHMENTS_OPTION = typer.Option(
    True,
    "--download-attachments/--no-download-attachments",
    help="Download issue and comment attachments",
)

MAX_ATTACHMENT_SIZE_OPTION = typer.Option(
    10, "--max-attachment-size", help="Maximum attachment size in MB"
)

# Date filtering options - absolute dates
CREATED_AFTER_OPTION = typer.Option(
    None, "--created-after", help="Filter issues created after date (YYYY-MM-DD)"
)

CREATED_BEFORE_OPTION = typer.Option(
    None, "--created-before", help="Filter issues created before date (YYYY-MM-DD)"
)

UPDATED_AFTER_OPTION = typer.Option(
    None, "--updated-after", help="Filter issues updated after date (YYYY-MM-DD)"
)

UPDATED_BEFORE_OPTION = typer.Option(
    None, "--updated-before", help="Filter issues updated before date (YYYY-MM-DD)"
)

# Date filtering options - relative dates
LAST_DAYS_OPTION = typer.Option(
    None, "--last-days", help="Filter issues from last N days"
)

LAST_WEEKS_OPTION = typer.Option(
    None, "--last-weeks", help="Filter issues from last N weeks"
)

LAST_MONTHS_OPTION = typer.Option(
    None, "--last-months", help="Filter issues from last N months"
)
