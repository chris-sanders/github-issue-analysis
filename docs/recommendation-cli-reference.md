# Recommendation CLI Reference

This document provides detailed information about all recommendation management CLI commands, flags, and options.

## Commands Overview

```bash
uv run gh-analysis recommendations <command> [options]
```

Available commands:
- `discover` - Scan for new AI recommendations and initialize tracking
- `list` - List recommendations with filtering options
- `summary` - Show recommendation dashboard with statistics
- `review-session` - Start interactive review session

## Command: `discover`

Scans the results directory for AI analysis files and creates/updates recommendation metadata.

```bash
uv run gh-analysis recommendations discover [OPTIONS]
```

### Options:

- `--force-refresh` - Force refresh of existing recommendations
  - Re-evaluates all recommendations even if they already exist
  - Updates status based on current vs recommended labels
  - Resets review information (reviewed_at, review_notes)
  
- `--data-dir PATH` - Data directory path (default: "data")

### Examples:

```bash
# Discover new recommendations
uv run gh-analysis recommendations discover

# Force refresh all recommendations (e.g., after reprocessing)
uv run gh-analysis recommendations discover --force-refresh
```

## Command: `list`

Lists recommendations with various filtering options.

```bash
uv run gh-analysis recommendations list [OPTIONS]
```

### Options:

- `--org TEXT` - Filter by organization
- `--repo TEXT` - Filter by repository
- `--status TEXT` - Filter by status (can be specified multiple times)
  - Valid values: `pending`, `no_change_needed`, `approved`, `rejected`, `needs_modification`, `applied`, `failed`, `archived`
- `--product TEXT` - Filter by product (can be specified multiple times)
  - Examples: `kots`, `vendor`, `troubleshoot`, `embedded-cluster`
- `--min-confidence FLOAT` - Minimum confidence threshold (0.0-1.0)
- `--confidence-tier TEXT` - Filter by confidence tier (can be specified multiple times)
  - Valid values: `high` (≥0.9), `medium` (≥0.7), `low` (<0.7)
- `--limit INT` - Maximum number of results (default: 20)
- `--format TEXT` - Output format: `table`, `json`, `summary` (default: "table")
- `--include-no-change` - Include recommendations where no label change is needed
  - By default, `NO_CHANGE_NEEDED` recommendations are hidden
- `--data-dir PATH` - Data directory path (default: "data")

### Examples:

```bash
# List all pending recommendations (excluding NO_CHANGE_NEEDED)
uv run gh-analysis recommendations list

# List high-confidence pending recommendations for KOTS
uv run gh-analysis recommendations list --status pending --product kots --min-confidence 0.9

# Show all recommendations including those needing no changes
uv run gh-analysis recommendations list --include-no-change

# Export recommendations as JSON
uv run gh-analysis recommendations list --format json > recommendations.json

# List recommendations for a specific repository
uv run gh-analysis recommendations list --org myorg --repo myrepo
```

## Command: `summary`

Shows a dashboard with recommendation statistics.

```bash
uv run gh-analysis recommendations summary [OPTIONS]
```

### Options:

- `--data-dir PATH` - Data directory path (default: "data")

### Output includes:
- Total recommendation count
- Pending high confidence count
- No change needed count
- Breakdown by status
- Breakdown by product (top 10)
- Recently applied count (Phase 2)

## Command: `review-session`

Starts an interactive review session for recommendations.

```bash
uv run gh-analysis recommendations review-session [OPTIONS]
```

### Options:

- `--org TEXT` - Limit to specific organization
- `--repo TEXT` - Limit to specific repository
- `--status TEXT` - Filter by status (can be specified multiple times)
  - Default: `["pending"]`
  - Note: `NO_CHANGE_NEEDED` items are always excluded from review
- `--min-confidence FLOAT` - Minimum confidence threshold
- `--product TEXT` - Filter by product (can be specified multiple times)
- `--data-dir PATH` - Data directory path (default: "data")

### Review Actions:
1. **Approve** - Mark recommendation as approved
2. **Reject** - Mark recommendation as rejected  
3. **Modify** - Adjust confidence score
4. **Request changes** - Mark as needs_modification
5. **Skip** - Move to next recommendation
6. **Quit** - Exit review session

### Examples:

```bash
# Review all pending recommendations
uv run gh-analysis recommendations review-session

# Review only high-confidence KOTS recommendations
uv run gh-analysis recommendations review-session --product kots --min-confidence 0.9

# Review pending and needs_modification items for specific repo
uv run gh-analysis recommendations review-session --org myorg --repo myrepo --status pending --status needs_modification
```

## Status Lifecycle

1. **PENDING** - AI generated recommendation requiring review
2. **NO_CHANGE_NEEDED** - Current labels match recommendation (auto-set by discover)
3. **APPROVED** - Human approved, ready for application
4. **REJECTED** - Human rejected, will not be applied
5. **NEEDS_MODIFICATION** - Requires changes before approval
6. **APPLIED** - Successfully applied to GitHub (Phase 2)
7. **FAILED** - Application to GitHub failed (Phase 2)
8. **ARCHIVED** - Moved to historical archive (Phase 2)

## Integration with Reprocessing

When using the `--reprocess` flag with AI processing:

```bash
# Reprocess all issues (including NO_CHANGE_NEEDED)
uv run gh-analysis process product-labeling --org myorg --repo myrepo --reprocess

# Then re-discover to update statuses
uv run gh-analysis recommendations discover --force-refresh
```

This workflow ensures that:
- Previously `NO_CHANGE_NEEDED` items are re-evaluated
- Status changes to `PENDING` if new recommendations differ from current labels
- All metadata is updated with latest AI analysis

## Best Practices

1. **Regular Discovery**: Run `discover` after each AI processing batch
2. **Use Filters**: Leverage filtering to focus reviews on specific products or confidence levels
3. **Batch Reviews**: Use `review-session` to efficiently process multiple recommendations
4. **Force Refresh**: Use `--force-refresh` after reprocessing to ensure status accuracy
5. **Monitor NO_CHANGE**: Use `--include-no-change` periodically to audit AI accuracy