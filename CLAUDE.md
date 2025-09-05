# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Required Commands

**Setup:**
```bash
uv sync --all-extras             # Install all dependencies including dev tools
# Set GITHUB_TOKEN and OPENAI_API_KEY environment variables
```

**Dependency Management:**
```bash
uv add package-name              # Add new dependency (updates pyproject.toml)
uv add --dev package-name        # Add development dependency
uv remove package-name           # Remove dependency (updates pyproject.toml)
uv sync                          # Sync environment with pyproject.toml
```
Always use `uv add/remove` instead of `pip install/uninstall` to maintain dependency tracking in pyproject.toml.

**Quality Checks (Required Before Every Commit):**
```bash
uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

All four steps must pass:
- **Ruff Format**: Code formatting consistency (automatically applies fixes - **NEVER MANUALLY FIX FORMATTING**)
- **Ruff Check**: Code quality, imports, style violations (automatically applies fixes)
- **MyPy**: Type checking and type annotations
- **Pytest**: All tests must pass

**CRITICAL**: Ruff format automatically fixes ALL formatting issues when you run it. NEVER manually edit files for formatting issues - ALWAYS run `uv run ruff format .` first. Ruff format will automatically fix line length, spacing, quotes, etc. This ensures agents never see formatting errors.

**IMPORTANT**: Always run `uv run ruff format .` first, then `uv run ruff check --fix` - this ensures consistent formatting and style!

**Runtime Requirements:**
- Never use `python` directly - Always use `uv run python` or `uv run <command>`
- Add type annotations during development, not after mypy fails
- Use specific types from `typing` module, avoid `Any`

**Type Annotation Examples:**
```python
from typing import List, Dict, Optional

def process_issues(issues: List[Dict[str, Any]]) -> Optional[str]:
    """Process GitHub issues and return summary."""
    data: Dict[str, Any] = {...}
    return result
```

## Memory-Enhanced Troubleshooting Setup

The memory+tool runners (suffix "_mt") require Snowflake access for enhanced troubleshooting with historical case retrieval and evidence search capabilities:

**Required Environment Variables:**
```bash
export SNOWFLAKE_ACCOUNT="your_account"
export SNOWFLAKE_USER="your_user"  
export SNOWFLAKE_PRIVATE_KEY_PATH="~/.snowflake/rsa_key.pem"
export SNOWFLAKE_WAREHOUSE="COMPUTE_WH"
```

**Available Memory+Tool Agents:**
- `claude_sonnet_mt`: Claude Sonnet 4 with memory injection and evidence search tools
- `gpt5_mini_medium_mt`: GPT-5 Mini (medium reasoning) with memory and evidence search
- `gpt5_mini_high_mt`: GPT-5 Mini (high reasoning) with memory and evidence search
- `gpt5_medium_mt`: GPT-5 (medium reasoning) with memory and evidence search
- `gpt5_high_mt`: GPT-5 (high reasoning) with memory and evidence search
- `gemini_25_pro_mt`: Gemini 2.5 Pro with memory injection and evidence search tools

**Test Memory Retrieval:**
```bash
# Test that Snowflake connection works
uv run python -c "from github_issue_analysis.runners.utils.summary_retrieval import SummaryRetrievalClient; client = SummaryRetrievalClient(); print('Connected to Snowflake')"
```

**CLI Usage:**
```bash
# Collect GitHub issues (various modes) - ask user for org/repo/issue values
uv run gh-analysis collect --org [ORG] --repo [REPO]                    # Repository-specific
uv run gh-analysis collect --org [ORG]                                  # Organization-wide  
uv run gh-analysis collect --org [ORG] --repo [REPO] --issue-number [NUM] # Single issue

# Show storage statistics
uv run gh-analysis status

# Show version information
uv run gh-analysis version

# AI processing commands (BATCH PROCESSING RECOMMENDED)
# Use batch processing for cost-effective analysis (50% cheaper than individual processing)
uv run gh-analysis batch submit product-labeling --org [ORG] --repo [REPO]   # Batch process all issues for repo
uv run gh-analysis batch submit product-labeling --org [ORG]               # Batch process all org issues
uv run gh-analysis batch status <job-id>                                   # Check batch job progress
uv run gh-analysis batch collect <job-id>                                  # Collect completed results
uv run gh-analysis batch list                                              # List all batch jobs

# Individual processing (use only for single issues or testing)
uv run gh-analysis process product-labeling --org [ORG] --repo [REPO] --issue-number [NUM]  # Single issue only
```

## Architecture

This is a Python CLI tool for GitHub issue collection and AI-powered analysis using a modular architecture:

### Core Structure
- **CLI Layer** (`cli/`): Typer-based command interface
- **GitHub Client** (`github_client/`): API integration with rate limiting and pagination
- **AI Processing** (`ai/`): OpenAI and Anthropic analysis capabilities
- **Storage** (`storage/`): JSON-based data persistence

### Data Flow
GitHub API → Issue Collection → JSON Storage (`data/issues/`) → **Batch AI Processing** → Results (`data/results/`)

**IMPORTANT**: Always use batch processing for multiple issues - it's 50% cheaper and processes in parallel.

### Reference Documentation
When implementing features, consult these docs for detailed specifications:
- `docs/architecture.md` - Component details and design principles
- `docs/data-schemas.md` - JSON schemas for issues, results, and tasks
- `docs/api-reference.md` - CLI commands and options

## Agent Development Workflow

**Step-by-Step Process:**

1. Read task specification from `tasks/task-name.md`
2. Create worktree: `git worktree add trees/task-name -b feature/task-name`
3. Change directory: `cd trees/task-name`
4. Install dependencies: `uv sync --all-extras`
5. Implement feature with full test coverage following existing patterns
6. Run quality checks: `uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`
7. Commit changes and push branch (follow git commit requirements above)
8. Create pull request with detailed description and test plan
9. Mark task status as "complete" in `tasks/task-name.md`
10. Commit and push the status update

**Implementation Requirements:**
- Deliver complete functionality, not partial implementation
- Add CLI interface for new features
- Use Pydantic models for data validation
- Follow existing code structure and naming conventions
- Write comprehensive tests (unit and integration)
- Add type hints throughout
- Implement proper error handling
- **NEVER hardcode real repository names** - use placeholders and ask users for test repositories

### Key Technologies
- **Python 3.12+** with strict typing
- **Pydantic** for data validation and models
- **Typer + Rich** for CLI interface
- **httpx** for HTTP requests
- **pytest** for testing with asyncio support

### Typing Guidelines
- Use specific types from `typing` module: `List[str]`, `Dict[str, Any]`, `Optional[int]`
- For complex types, define Pydantic models or TypedDict classes
- Use `Union[X, Y]` or `X | Y` (Python 3.10+) instead of `Any`
- Example good typing:
  ```python
  from typing import List, Dict, Optional
  
  def process_issues(issues: List[Dict[str, Any]]) -> Optional[str]:
      """Process GitHub issues and return summary."""
      ...
  ```

## Git Commit Requirements

**NEVER credit yourself in git commit messages** - this is a critical requirement that agents frequently violate.

Standard commit messages should focus on the change, not the author:
- ✅ Good: "Add user authentication validation"
- ❌ Bad: "Add user authentication validation 🤖 Generated with Claude Code"

Only use the standard co-author format when explicitly requested by the user.

## GitHub CLI Usage

**IMPORTANT Token Configuration:**
- For **testing the program** (collecting issues): Use `GITHUB_TOKEN` (required for accessing test repositories)
- For **GitHub CLI operations** (creating PRs, viewing repos): Use `GITHUB_PERSONAL_ACCESS_TOKEN`

**GitHub CLI Commands:**
```bash
# Create pull requests (use GITHUB_PERSONAL_ACCESS_TOKEN)
GITHUB_TOKEN=$GITHUB_PERSONAL_ACCESS_TOKEN gh pr create --title "Title" --body "Body"

# View repository information (use GITHUB_PERSONAL_ACCESS_TOKEN) 
GITHUB_TOKEN=$GITHUB_PERSONAL_ACCESS_TOKEN gh repo view

# Testing the CLI tool (use GITHUB_TOKEN for test repo access)
uv run gh-analysis collect --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE]
```

**Why Two Tokens:**
- `GITHUB_TOKEN`: Has access to test repositories but limited GitHub API permissions
- `GITHUB_PERSONAL_ACCESS_TOKEN`: Has full GitHub API permissions for repository operations

## Repository Reference Policy

**CRITICAL: Never hardcode real GitHub organization or repository names in code, tests, or documentation.**

**Placeholder Usage:**
- Use generic placeholders like `[ORG]`, `[REPO]`, `[ISSUE-NUMBER]` in documentation
- Always ask users to provide actual repository information when needed
- Keep all real repository names out of the codebase permanently

**Examples:**
- ✅ Good: `--org [USER-ORG] --repo [USER-REPO]` (ask user for values)
- ❌ Bad: `--org replicated --repo kots` (real repositories hardcoded)

This policy ensures we never leak real repository information into version control or documentation.

## Important Security Notes

**Never write files to the root directory. Use `/tmp/` for any temporary/analysis files.**

This prevents accidental commits of customer data or temporary analysis files.
