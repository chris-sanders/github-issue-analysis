#!/bin/bash
set -e  # Exit on error

# Validate required environment variables
if [ -z "$ISSUE_URL" ]; then
    echo "ERROR: ISSUE_URL environment variable is required" >&2
    echo "Example: export ISSUE_URL=\"https://github.com/microsoft/vscode/issues/12345\"" >&2
    exit 2
fi

# Activate virtual environment
export PATH="/app/.venv/bin:$PATH"

# Build command with required --url flag
CMD="gh-analysis process troubleshoot --url \"$ISSUE_URL\""

# Add optional CLI arguments if provided
if [ -n "$CLI_ARGS" ]; then
    CMD="$CMD $CLI_ARGS"
fi

# Execute the command
eval exec $CMD