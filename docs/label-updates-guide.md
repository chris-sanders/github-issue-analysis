# GitHub Issue Label Updates Guide

This guide explains how to use the automated label update functionality to apply AI recommendations to your GitHub issues.

## Overview

The label update system analyzes AI recommendations from the product-labeling processor and intelligently applies label changes to GitHub issues. It only updates issues that need changes and provides comprehensive safety features.

## Prerequisites

1. **GitHub Token**: You need a GitHub personal access token with write access to the repository
2. **Collected Issues**: Issues must be collected using the `collect` command
3. **AI Analysis**: Issues must be processed with the `process product-labeling` command

## Setup

### 1. Set GitHub Token

```bash
export GITHUB_TOKEN=ghp_your_personal_access_token_here
```

The token needs the following permissions:
- `repo` scope for private repositories
- `public_repo` scope for public repositories  
- `issues:write` permission

### 2. Verify Data Structure

Ensure you have the required data structure:
```
data/
├── issues/
│   └── org-name/
│       └── repo-name/
│           ├── issue-123.json
│           └── issue-456.json
└── results/
    └── org-name/
        └── repo-name/
            ├── issue-123-product-labeling.json
            └── issue-456-product-labeling.json
```

## Basic Workflow

### Step 1: Collect Issues
```bash
uv run gh-analysis collect --org myorg --repo myrepo --limit 10
```

### Step 2: Run AI Analysis  
```bash
uv run gh-analysis process product-labeling --org myorg --repo myrepo
```

### Step 3: Preview Changes (Recommended)
```bash
uv run gh-analysis update-labels --org myorg --repo myrepo --dry-run
```

The dry run shows you exactly what changes will be made, including:
- Which labels will be added/removed with confidence scores and reasoning
- The exact GitHub comment that will be posted to each issue  
- Overall confidence assessment for each issue

### Step 4: Apply Changes
```bash
uv run gh-analysis update-labels --org myorg --repo myrepo
```

## Usage Examples

### Single Issue Update
```bash
# Preview changes for one issue
uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123 --dry-run

# Apply changes to one issue
uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123
```

### Batch Processing with Safety
```bash
# High confidence only (90%+)
uv run gh-analysis update-labels --org myorg --repo myrepo --min-confidence 0.9

# Limit to 5 issues with delay between API calls
uv run gh-analysis update-labels --org myorg --repo myrepo --max-issues 5 --delay 2.0

# Skip posting explanatory comments
uv run gh-analysis update-labels --org myorg --repo myrepo --skip-comments
```

### Advanced Options
```bash
# Force apply all changes (use with extreme caution)
uv run gh-analysis update-labels --org myorg --repo myrepo --force

# Custom data directory
uv run gh-analysis update-labels --org myorg --repo myrepo --data-dir /path/to/data
```

## Understanding the Output

### Dry Run Output
```
🔍 Analyzing label changes with confidence threshold: 0.8

📁 Found 3 file pair(s) to process

📋 Planned Changes:

Found 2 issue(s) that need label updates:

**Issue #123 (myorg/myrepo)**
Overall confidence: 0.92
  Add:
    + product::vendor (confidence: 0.95) - Issue concerns vendor portal functionality
  Remove:
    - product::kots (confidence: 0.88) - Analysis indicates this is not KOTS-related

**GitHub Comment Preview:**
---
🤖 **AI Label Update**

The following label changes have been applied based on AI analysis:

**Added Labels:**
- `product::vendor` (confidence: 0.95) - Issue concerns vendor portal functionality

**Removed Labels:**
- `product::kots` (confidence: 0.88) - Analysis indicates this is not KOTS-related

**Reasoning:** Adding 1 label(s) and Removing 1 label(s) based on analysis: Issue about vendor portal...

---
*This update was automated based on AI analysis of issue content.*
---

**Issue #456 (myorg/myrepo)** 
Overall confidence: 0.85
  Add:
    + product::troubleshoot (confidence: 0.90) - Contains troubleshooting request

**GitHub Comment Preview:**
---
🤖 **AI Label Update**

The following label changes have been applied based on AI analysis:

**Added Labels:**
- `product::troubleshoot` (confidence: 0.90) - Contains troubleshooting request

**Reasoning:** Adding 1 label(s) based on analysis: Issue contains troubleshooting...

---
*This update was automated based on AI analysis of issue content.*
---
```

### Execution Output
```
🏷️ Processing issue #123 (1/2)
  ✅ Updated 2 label(s)

🏷️ Processing issue #456 (2/2)  
  ✅ Updated 1 label(s)

📊 Execution Summary:
✅ Successfully updated 2 issue(s):
  - Issue #123: 2 change(s)
  - Issue #456: 1 change(s)
```

## Safety Features

### Confidence Thresholds
- Default minimum confidence: 80%
- Only applies changes above the threshold
- Use `--min-confidence` to adjust (0.0 to 1.0)

### Smart Detection  
- Only updates issues that actually need changes
- Compares current labels vs AI recommendations
- Skips issues that are already correctly labeled

### User Confirmation
- Prompts for confirmation before batch operations
- Shows preview of all planned changes
- Can be bypassed with single issue updates

### Error Handling
- Continues processing if individual issues fail
- Reports failures with clear error messages
- Respects GitHub API rate limits

### Rate Limiting
- Built-in rate limit checking and waiting
- Optional delay between API calls with `--delay`
- Automatic retry on rate limit exceeded

## Generated Comments

When labels are updated, explanatory comments are posted to the issue:

```
🤖 AI Label Update

The following label changes have been applied based on AI analysis:

Added Labels:
- `product::vendor` (confidence: 0.92) - Issue concerns vendor portal CLI authentication

Removed Labels:  
- `product::kots` (confidence: 0.15) - Analysis indicates this is not KOTS-related

Reasoning: Issue about vendor portal authentication with CLI integration

---
*This update was automated based on AI analysis of issue content.*
```

## Troubleshooting

### Common Issues

**"No matching issue/result files found"**
- Ensure you've run `collect` and `process product-labeling` first
- Check that the org/repo names match exactly
- Verify data directory structure

**"GitHub token required"**  
- Set the `GITHUB_TOKEN` environment variable
- Ensure token has write permissions to the repository

**"No label changes needed"**
- AI analysis may indicate current labels are already correct
- Try lowering confidence threshold with `--min-confidence`
- Use `--dry-run` to see what would be processed

**Rate limit errors**
- Wait for rate limit to reset (usually 1 hour)
- Use `--delay` option to slow down API calls
- Process fewer issues at once with `--max-issues`

### Best Practices

1. **Always dry-run first**: Use `--dry-run` to preview changes
2. **Start with high confidence**: Begin with `--min-confidence 0.9` 
3. **Process incrementally**: Use `--max-issues` for large batches
4. **Monitor rate limits**: Add delays if hitting rate limits frequently
5. **Review AI reasoning**: Check the posted comments for accuracy

## Integration with CI/CD

### Automated Label Updates
```yaml
# .github/workflows/label-update.yml
name: Update Issue Labels
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  update-labels:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install uv
        run: pip install uv
      - name: Install dependencies  
        run: uv sync --all-extras
      - name: Update labels
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          uv run gh-analysis update-labels \
            --org ${{ github.repository_owner }} \
            --repo ${{ github.event.repository.name }} \
            --min-confidence 0.9 \
            --max-issues 10
```

This provides comprehensive documentation for users to understand and effectively use the label update functionality!