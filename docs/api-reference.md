# API Reference

## CLI Commands

### collect
Collect GitHub issues and save them locally.

```bash
uv run gh-analysis collect [OPTIONS]
```

**Options:**
- `--org, -o TEXT`: GitHub organization name (required)
- `--repo, -r TEXT`: GitHub repository name (optional for org-wide search)
- `--issue-number INTEGER`: Specific issue number to collect
- `--labels, -l TEXT`: Filter by labels (can be used multiple times)
- `--state TEXT`: Issue state: open, closed, or all (default: closed)
- `--limit INTEGER`: Maximum number of issues to collect (default: 10)
- `--token TEXT`: GitHub API token (defaults to GITHUB_TOKEN env var)
- `--download-attachments / --no-download-attachments`: Download issue and comment attachments (default: true)
- `--max-attachment-size INTEGER`: Maximum attachment size in MB (default: 10)
- `--exclude-repo, -x TEXT`: Repository to exclude from organization-wide search (can be used multiple times)
- `--exclude-repos TEXT`: Comma-separated list of repositories to exclude from organization-wide search

**Collection Modes:**
- **Single issue:** `--org ORGNAME --repo REPONAME --issue-number NUMBER`
- **Organization-wide:** `--org ORGNAME` (searches all repos in org)
- **Repository-specific:** `--org ORGNAME --repo REPONAME`

**Examples:**
```bash
# Collect single issue
uv run gh-analysis collect --org example-org --repo example-repo --issue-number 71

# Collect from entire organization (20 most recent closed issues)
uv run gh-analysis collect --org example-org --limit 20

# Collect bugs from specific repository
uv run gh-analysis collect --org example-org --repo example-repo --labels bug --limit 5

# Organization-wide collection excluding specific repositories
uv run gh-analysis collect --org example-org --exclude-repo private-repo --limit 15

# Exclude multiple repositories using multiple flags
uv run gh-analysis collect --org example-org --exclude-repo private-repo --exclude-repo test-repo --limit 10

# Exclude multiple repositories using comma-separated list
uv run gh-analysis collect --org example-org --exclude-repos "private-repo,test-repo,archived-repo" --limit 10

# Mix both exclusion approaches with additional filters
uv run gh-analysis collect --org example-org --exclude-repo private-repo --exclude-repos "test-repo,docs-repo" --labels bug --state open --limit 20
```

### batch (RECOMMENDED)
**Batch processing for cost-effective AI analysis (50% cheaper than individual processing).**

```bash
uv run gh-analysis batch [COMMAND] [OPTIONS]
```

#### submit
Submit a batch processing job for multiple issues.

```bash
uv run gh-analysis batch submit product-labeling [OPTIONS]
```

**Options:**
- `--org, -o TEXT`: GitHub organization name
- `--repo, -r TEXT`: GitHub repository name (optional for org-wide processing)
- `--issue-number INTEGER`: Specific issue number to process
- `--model TEXT`: AI model to use (e.g., 'openai:gpt-4o-mini', 'openai:o4-mini')
- `--thinking-effort TEXT`: Reasoning effort level for thinking models (low, medium, high)
- `--thinking-budget INTEGER`: Thinking token budget for Anthropic/Google models
- `--include-images / --no-include-images`: Include image analysis (default: true)

**Examples:**
```bash
# Batch process all collected issues for an organization (RECOMMENDED)
uv run gh-analysis batch submit product-labeling --org myorg

# Batch process all issues for a specific repository
uv run gh-analysis batch submit product-labeling --org myorg --repo myrepo

# Batch process with specific model
uv run gh-analysis batch submit product-labeling --org myorg --model openai:gpt-4o-mini
```

#### status
Check the status of a batch processing job.

```bash
uv run gh-analysis batch status <job-id>
```

#### collect
Collect and process results from a completed batch job.

```bash
uv run gh-analysis batch collect <job-id>
```

#### list
List all batch processing jobs.

```bash
uv run gh-analysis batch list
```

#### cancel
Cancel an active batch processing job.

```bash
uv run gh-analysis batch cancel <job-id>
```

**Notes:**
- Only jobs in states `pending`, `validating`, `in_progress`, or `finalizing` can be cancelled
- Already completed, failed, or cancelled jobs will show their current status without error
- Cancelling a job prevents further API charges for that batch

#### remove
Remove a batch job record and associated files.

```bash
uv run gh-analysis batch remove <job-id>
uv run gh-analysis batch remove <job-id> --force
```

**Options:**
- `--force`: Skip confirmation prompts

**Notes:**
- Removes job metadata file and associated input/output files
- Warns if job is still active and requires confirmation (or `--force` flag)
- Cannot be undone - use with caution

**Typical Batch Workflow:**
```bash
# 1. Collect issues
uv run gh-analysis collect --org myorg --limit 30

# 2. Submit batch job
uv run gh-analysis batch submit product-labeling --org myorg

# 3. Check status periodically (shows real-time progress)
uv run gh-analysis batch status <job-id>

# 4. Collect results when completed
uv run gh-analysis batch collect <job-id>

# 5. Update labels with dry run first
uv run gh-analysis update-labels --org myorg --dry-run
```

### process
**Individual AI processing commands (use only for single issues or testing).**

```bash
uv run gh-analysis process [COMMAND] [OPTIONS]
```

#### show-settings
Display available model settings that can be configured.

```bash
uv run gh-analysis process show-settings
```

Shows common settings like:
- `temperature`: Randomness in responses (0.0-1.0)
- `max_tokens`: Maximum tokens to generate
- `reasoning_effort`: Thinking effort for reasoning models
- `top_p`: Nucleus sampling parameter
- `timeout`: Request timeout in seconds
- `seed`: Random seed for deterministic results

#### product-labeling
Analyze GitHub issues for product labeling recommendations with optional image processing.

```bash
uv run gh-analysis process product-labeling [OPTIONS]
```

**Options:**
- `--org, -o TEXT`: GitHub organization name
- `--repo, -r TEXT`: GitHub repository name
- `--issue-number, -i INTEGER`: Specific issue number to process
- `--model, -m TEXT`: AI model to use (default: 'openai:o4-mini')
- `--setting TEXT`: Model settings as key=value (can be used multiple times)
- `--include-images / --no-include-images`: Include image analysis (default: true)
- `--dry-run, -d / --no-dry-run`: Show what would be processed without running AI (default: false)
- `--reprocess / --no-reprocess`: Force reprocessing of already reviewed items (default: false)

**Examples:**
```bash
# Show available model settings
uv run gh-analysis process show-settings

# Process all collected issues for a repository
uv run gh-analysis process product-labeling --org myorg --repo myrepo

# Process a specific issue with custom model
uv run gh-analysis process product-labeling --org myorg --repo myrepo --issue-number 123 --model openai:o4-mini

# Process with custom model settings
uv run gh-analysis process product-labeling --org myorg --repo myrepo \
  --model anthropic:claude-3-5-sonnet \
  --setting temperature=0.5 \
  --setting reasoning_effort=high

# Process with multiple settings
uv run gh-analysis process product-labeling --org myorg --repo myrepo --issue-number 123 \
  --model openai:o4-mini \
  --setting reasoning_effort=medium \
  --setting max_tokens=2000

# Dry run to see what would be processed
uv run gh-analysis process product-labeling --org myorg --repo myrepo --dry-run

# Force reprocessing of already reviewed items
uv run gh-analysis process product-labeling --org myorg --repo myrepo --reprocess
```

**Note on Model Settings:**
- Use `--setting` for any model-specific configuration
- PydanticAI will validate settings and provide clear error messages
- Not all settings are supported by all models
- Settings are passed as key=value pairs

### update-labels
Update GitHub issue labels based on AI recommendations from product-labeling analysis.

```bash
uv run gh-analysis update-labels [OPTIONS]
```

**Required Setup:**
- Set `GITHUB_TOKEN` environment variable with a token that has write access to the repository
- Must have AI analysis results from `process product-labeling` command

**Options:**
- `--org TEXT`: GitHub organization name (required)
- `--repo TEXT`: GitHub repository name (required for single repo operations)
- `--issue-number INTEGER`: Specific issue number to update
- `--min-confidence FLOAT`: Minimum confidence threshold for applying changes (default: 0.8)
- `--dry-run / --no-dry-run`: Preview changes without applying them (default: false)
- `--skip-comments / --no-skip-comments`: Update labels but don't post explanatory comments (default: false)
- `--force / --no-force`: Apply even low-confidence changes (default: false)
- `--max-issues INTEGER`: Maximum number of issues to process
- `--delay FLOAT`: Delay between API calls in seconds (default: 0.0)
- `--data-dir TEXT`: Data directory path (defaults to ./data)

**Recommended Workflow (Batch Processing):**
1. Collect issues: `uv run gh-analysis collect --org myorg --limit 30`
2. Submit batch job: `uv run gh-analysis batch submit product-labeling --org myorg`
3. Check status: `uv run gh-analysis batch status <job-id>`
4. Collect results: `uv run gh-analysis batch collect <job-id>`
5. Update labels: `uv run gh-analysis update-labels --org myorg --dry-run`

**Alternative Workflow (Individual Processing - for single issues only):**
1. Collect single issue: `uv run gh-analysis collect --org myorg --repo myrepo --issue-number 123`
2. Process individual issue: `uv run gh-analysis process product-labeling --org myorg --repo myrepo --issue-number 123`
3. Update labels: `uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123 --dry-run`

**Examples:**
```bash
# Preview changes for a specific issue (safe to run)
uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123 --dry-run

# Update all issues in a repository with high confidence threshold
uv run gh-analysis update-labels --org myorg --repo myrepo --min-confidence 0.9

# Update specific issue with custom confidence threshold
uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123 --min-confidence 0.75

# Apply all changes regardless of confidence (use with caution)
uv run gh-analysis update-labels --org myorg --repo myrepo --force

# Update labels without posting explanatory comments
uv run gh-analysis update-labels --org myorg --repo myrepo --skip-comments

# Process up to 5 issues with 1 second delay between API calls
uv run gh-analysis update-labels --org myorg --repo myrepo --max-issues 5 --delay 1.0
```

**Safety Features:**
- **Dry-run mode**: Always test with `--dry-run` first to preview changes, including exact GitHub comments that will be posted
- **Confidence thresholds**: Only applies changes above specified confidence level
- **User confirmation**: Prompts for confirmation before batch operations
- **Smart detection**: Only updates issues that actually need changes
- **Rate limiting**: Respects GitHub API limits and includes delay options
- **Error handling**: Continues processing other issues if one fails

**What It Does:**
1. **Analyzes AI recommendations** from product-labeling results
2. **Compares current labels** with AI recommendations
3. **Identifies needed changes** (additions/removals) above confidence threshold
4. **Updates GitHub labels** via API calls
5. **Posts explanatory comments** with AI reasoning (unless skipped)
6. **Provides detailed feedback** on what was changed and any failures

### status
Show storage status and statistics.

```bash
uv run gh-analysis status
```

Displays:
- Total number of issues in storage
- Storage size and location
- Issues breakdown by repository

### version
Show version information.

```bash
uv run gh-analysis version
```

## Model Configuration

### Model Format
All models must be specified in the format `provider:model-name`:
- ✅ `openai:o4-mini`
- ✅ `anthropic:claude-3-5-sonnet-latest`
- ❌ `o4-mini` (missing provider)

### Generic Settings Approach
The simplified AI architecture uses a generic `--setting` flag for all model configurations:

```bash
# OpenAI reasoning models
uv run gh-analysis process product-labeling --model openai:o4-mini \
  --setting reasoning_effort=medium

# Anthropic models with thinking
uv run gh-analysis process product-labeling --model anthropic:claude-3-5-sonnet-latest \
  --setting reasoning_effort=high \
  --setting temperature=0.5

# Multiple settings
uv run gh-analysis process product-labeling --model openai:gpt-4o \
  --setting temperature=0.7 \
  --setting max_tokens=2000 \
  --setting top_p=0.9
```

### Common Settings
- `temperature`: Controls randomness (0.0-1.0)
- `max_tokens`: Maximum response length
- `reasoning_effort`: For thinking models (low, medium, high)
- `top_p`: Nucleus sampling parameter
- `timeout`: Request timeout in seconds
- `seed`: For deterministic results

PydanticAI handles model-specific validation and will provide clear error messages for unsupported settings.

## Development Commands

```bash
# Setup
uv sync --all-extras

# Code quality (run all steps - required before commit)
uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest

# Individual tools
uv run ruff format .                    # Code formatting (automatically applies fixes - DO NOT manually edit files for formatting)
uv run ruff check --fix --unsafe-fixes  # Code quality and imports
uv run mypy .                           # Type checking
uv run pytest                          # Run tests
```

**IMPORTANT**: Ruff format automatically applies formatting fixes. Agents should **NOT** manually make formatting changes. Only intervene if ruff fails with actual errors (syntax errors, etc.).