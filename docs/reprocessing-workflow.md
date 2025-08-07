# Reprocessing Workflow

When you update your AI prompts or labeling logic and need to reprocess issues that were previously marked as `NO_CHANGE_NEEDED`, follow this workflow:

## Option 1: Reprocess Everything (Recommended)

This approach reprocesses all issues regardless of their current status:

```bash
# 1. Reprocess all issues with the --reprocess flag
uv run gh-analysis process product-labeling --org myorg --repo myrepo --reprocess

# 2. Re-discover recommendations to update statuses
uv run gh-analysis recommendations discover --force-refresh

# 3. Review the updated recommendations
uv run gh-analysis recommendations list
```

## Option 2: Batch Reprocessing (Cost-Effective)

For large repositories, use batch processing:

```bash
# 1. Submit batch job with reprocess flag
uv run gh-analysis batch submit product-labeling --org myorg --repo myrepo --reprocess

# 2. Check batch status
uv run gh-analysis batch status <job-id>

# 3. Collect results when complete
uv run gh-analysis batch collect <job-id>

# 4. Re-discover recommendations
uv run gh-analysis recommendations discover --force-refresh
```

## Option 3: Selective Reprocessing

To reprocess only specific issues:

```bash
# 1. List all recommendations including NO_CHANGE_NEEDED
uv run gh-analysis recommendations list --include-no-change

# 2. Reprocess specific issues
uv run gh-analysis process product-labeling --org myorg --repo myrepo --issue-number 123 --reprocess

# 3. Re-discover for that issue
uv run gh-analysis recommendations discover --force-refresh
```

## Understanding Status Transitions

- `NO_CHANGE_NEEDED` → `PENDING`: When reprocessed AI now recommends different labels
- `NO_CHANGE_NEEDED` → `NO_CHANGE_NEEDED`: When labels still match after reprocessing
- `PENDING/APPROVED/REJECTED` → `PENDING`: When reprocessed with different recommendations
- `PENDING/APPROVED/REJECTED` → `NO_CHANGE_NEEDED`: When reprocessed recommendations now match current labels

## Best Practices

1. **Always use `--reprocess`** when you've updated your AI prompts
2. **Always run `discover --force-refresh`** after reprocessing to update statuses
3. **Use batch processing** for cost efficiency when reprocessing many issues
4. **Monitor the summary** to see how many items changed from NO_CHANGE_NEEDED to PENDING

## Example: After Prompt Update

```bash
# See current state
uv run gh-analysis recommendations summary

# Reprocess everything
uv run gh-analysis batch submit product-labeling --org myorg --reprocess

# Wait for completion...
uv run gh-analysis batch collect <job-id>

# Update all statuses
uv run gh-analysis recommendations discover --force-refresh

# See what changed
uv run gh-analysis recommendations summary
uv run gh-analysis recommendations list  # Shows only items needing changes
```