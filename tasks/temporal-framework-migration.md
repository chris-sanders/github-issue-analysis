# Task: Migrate to Temporal Framework via Submodule

## Status
**Status:** In Progress - Phase 1 Complete, Phase 2 Needed
**Assigned:** Claude Code
**Priority:** High
**Estimated Effort:** 4-5 days total
**Actual Effort So Far:** 1 day (Phase 1)

## Current State (2025-10-12)

### ✅ Phase 1 Complete: Basic Framework Integration
- Added framework submodule
- Migrated MCP integration to use `create_mcp_toolset()`
- Documentation updated
- Tests passing (465 tests pass)

### ❌ Phase 2 Needed: Full Migration
**IMPORTANT DISCOVERY**: After reviewing exp05-temporal, realized the migration is incomplete:

1. **Framework is missing shared utilities**
   - exp05 and gh-analysis BOTH have: memory_runner, history, snowflake_base, snowflake_dev_client, summary_retrieval
   - These should be in framework, not duplicated

2. **Runner pattern should be eliminated**
   - Current: GitHubIssueRunner, MemoryAwareGitHubRunner classes
   - Should be: Temporal workflows + activities + TemporalAgent
   - exp05-temporal shows the pattern: direct TemporalAgent usage, no Runner classes

3. **Temporal integration not implemented**
   - gh-analysis still uses Runner pattern
   - Should convert to workflows/activities like exp05-temporal demo

## Phase 2 Plan: Complete Migration

### Step 1: Add Shared Utilities to Framework
Work on framework feature branch: `feature/add-shared-utilities`

Move these from both exp05 and gh-analysis into framework:
- `memory/` - memory injection and retrieval
  - `memory_runner.py` → adapt to work with TemporalAgent
  - `memory_preprocessor.py` → context preparation
- `history.py` - history trimming utilities
- `snowflake/` - database integration
  - `snowflake_base.py` - base client
  - `snowflake_dev_client.py` - development client
  - `summary_retrieval.py` - case retrieval
- `tools.py` - shared tool functions (search_evidence, etc.)

**Key Decision**: Should these work with TemporalAgent or be Temporal activities?
- Memory retrieval → Temporal activity (external operation)
- History trimming → Utility function (in-process)
- Snowflake queries → Temporal activity (external operation)

### Step 2: Convert gh-analysis to Temporal Pattern

Replace Runner pattern with Temporal workflows:

**Before** (Runner pattern):
```python
class GPT5MediumRunner(GitHubIssueRunner):
    def __init__(self):
        agent = Agent(...)
        super().__init__("gpt5-medium", agent)

    async def analyze(self, issue_data):
        return await self.agent.run(issue_data)
```

**After** (Temporal pattern):
```python
# agents/troubleshoot.py
gpt5_medium_agent = TemporalAgent(
    Agent(
        name="gpt5-medium",
        model=OpenAIResponsesModel("gpt-5"),
        output_type=TechnicalAnalysis,
        instructions=TROUBLESHOOTING_PROMPT,
        toolsets=[mcp_tools],
        model_settings={"openai_reasoning_effort": "medium"},
    ),
    model_activity_config={
        "start_to_close_timeout": timedelta(minutes=2)
    }
)

# workflows/troubleshoot.py
@workflow.defn
class TroubleshootWorkflow:
    @workflow.run
    async def run(self, issue_data: dict) -> TechnicalAnalysis:
        # Temporal handles durability, retries, observability
        result = await gpt5_medium_agent.run(issue_data)
        return result.output

# activities/memory.py
@activity.defn
async def retrieve_memory(issue_data: dict) -> str:
    """Retrieve similar cases from Snowflake."""
    # Use framework's Snowflake utilities
    pass
```

### Step 3: Update CLI to Use Workflows

CLI commands should trigger Temporal workflows, not Runner classes:

```python
# cli/process.py
async def troubleshoot(issue_number: int, agent_name: str):
    # Start Temporal workflow
    client = await Client.connect("localhost:7233")
    result = await client.execute_workflow(
        TroubleshootWorkflow.run,
        issue_data,
        id=f"troubleshoot-{org}-{repo}-{issue_number}",
        task_queue="gh-analysis-queue",
    )
```

### Step 4: Remove Old Code

Delete deprecated patterns:
- `gh_analysis/runners/base/` - GitHubIssueRunner classes
- `gh_analysis/runners/troubleshooting/` - old runner implementations
- `gh_analysis/runners/utils/` - now in framework
- Replace with Temporal workflows/activities

## Overview

Migrate gh-analysis from vendored runner utilities to using the centralized Temporal PydanticAI Framework as a git submodule. This eliminates code duplication, provides a single source of truth for agent infrastructure, and enables both context-experiments and gh-analysis to share the same framework without pulling in private data.

## Background

### The Problem
Currently gh-analysis vendors code from context-experiments:
- `gh_analysis/runners/utils/` - copied utilities (commits 8d9eb8d, 9dbf697)
- `gh_analysis/runners/summary/utils/` - duplicate utilities
- Manual synchronization when utilities are updated
- Code duplication across repositories

### The Solution
The Temporal framework at `~/src/temporal` (branch: `pydantic-temporal-framework`) provides:
- **MCP Integration**: `create_mcp_toolset()` - flexible MCP server creation with auto-discovery
- **Agent Creation**: `create_temporal_agent()` - helper for Temporal-compatible agents
- **Observability**: `init_observability()`, tracing, and monitoring utilities
- **Shared Infrastructure**: Common patterns for both context-experiments and gh-analysis

### Proven Pattern (exp05-temporal)
The exp05-temporal worktree in context-experiments demonstrates this works:
```python
from framework.temporal_framework import create_mcp_toolset

# Direct usage - no adapter needed!
mcp_tools = create_mcp_toolset(
    "troubleshoot-mcp-server",
    env={
        "SBCTL_TOKEN": sbctl_token,
        "GITHUB_TOKEN": github_token,
        "MCP_BUNDLE_STORAGE": str(bundle_storage),
    },
    toolset_id="troubleshoot-mcp",
)
```

### Key Principle: Framework Should Be Easy
**If the framework is hard to use, we fix THE FRAMEWORK, not create adapters.**

The whole point is that gh-analysis and context-experiments share the same infrastructure code via submodule. The framework contains ONLY infrastructure (no private data, no actual GitHub repos, no customer information).

## Acceptance Criteria

### Submodule Setup
- [ ] Temporal framework added as git submodule at `framework/` directory
- [ ] Submodule tracks `~/src/temporal` on `pydantic-temporal-framework` branch
- [ ] `.gitmodules` configured for easy updates
- [ ] `git submodule init && git submodule update` works correctly

### Remove Vendored Code
- [ ] Delete `gh_analysis/runners/utils/` directory (currently vendored)
- [ ] Delete `gh_analysis/runners/summary/utils/` directory (duplicate utilities)
- [ ] All import statements updated to use framework
- [ ] No broken imports remaining

### Direct Framework Usage
- [ ] Import `create_mcp_toolset` from framework for MCP servers
- [ ] Import `create_temporal_agent` from framework for agent creation (if used)
- [ ] Import observability utilities from framework (init_observability, etc.)
- [ ] NO adapter layer created (framework is designed to be used directly)

### Update All Runners
- [ ] All runners in `gh_analysis/runners/troubleshooting/` use framework imports
- [ ] All runners in `gh_analysis/runners/summary/` use framework imports
- [ ] All runners in `gh_analysis/runners/base/` use framework imports
- [ ] Memory-enhanced runners use framework utilities
- [ ] All existing functionality preserved - no behavioral changes

### Testing and Validation
- [ ] All existing tests pass
- [ ] CLI commands work identically
- [ ] MCP server integration works via framework
- [ ] Observability/tracing works with framework utilities
- [ ] Quality checks pass: `uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`

### Documentation
- [ ] Update `CLAUDE.md` with submodule workflow
- [ ] Document how to update framework submodule
- [ ] Update architecture docs to reference framework
- [ ] Note: "If framework is hard to use, fix the framework, not gh-analysis"

## Implementation Plan

### Phase 1: Add Temporal Framework as Submodule

#### Step 1.1: Initialize Submodule
```bash
# From gh-analysis repository root
cd /Users/chris/src/github-issue-analysis

# Add temporal framework as submodule
git submodule add /Users/chris/src/temporal framework

# Configure submodule to track pydantic-temporal-framework branch
cd framework
git checkout pydantic-temporal-framework
cd ..

# Update .gitmodules to track the branch
git config -f .gitmodules submodule.framework.branch pydantic-temporal-framework

# Commit submodule addition
git add .gitmodules framework
git commit -m "Add temporal framework as submodule"
```

**Validation**:
```bash
# Verify submodule configuration
git submodule status
cat .gitmodules

# Test framework imports work
uv run python -c "from framework.temporal_framework import create_mcp_toolset; print('✓ Framework accessible')"
```

#### Step 1.2: Update Dependencies
Check framework dependencies and ensure compatibility:
```bash
# Check framework dependencies
cat framework/pyproject.toml

# Key dependencies (should already be compatible):
# - pydantic-ai>=1.0.14 (gh-analysis already has this)
# - temporalio[pydantic]>=1.18.0 (may need to add)
# - mcp>=1.16.0 (may need to add)
```

Add to gh-analysis `pyproject.toml` if needed:
```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "temporalio[pydantic]>=1.18.0",  # If not already present
    "mcp>=1.16.0",  # If not already present
]
```

Then sync:
```bash
uv sync --all-extras
```

### Phase 2: Update Runner Imports (Direct Framework Usage)

#### Step 2.1: Update Product Labeling Runner
**Before** (vendored imports):
```python
from ..utils.github_runner import GitHubIssueRunner
from ...ai.models import ProductLabelingResponse
from ...ai.prompts import PRODUCT_LABELING_PROMPT
```

**After** (framework imports - if needed):
```python
# Import from framework ONLY if we were using vendored utilities
# Otherwise, keep using pydantic-ai directly (which is what we do now)

from pydantic_ai import Agent
from gh_analysis.ai.models import ProductLabelingResponse
from gh_analysis.ai.prompts import PRODUCT_LABELING_PROMPT
```

**Note**: Product labeling currently doesn't use vendored utils, so minimal changes needed.

#### Step 2.2: Update Troubleshooting Runners
**Before** (vendored imports):
```python
from ..utils.github_runner import GitHubIssueRunner
from ..utils.history import create_history_trimmer
from ..adapters.mcp_adapter import create_troubleshoot_mcp_server
```

**After** (direct framework usage):
```python
# Import directly from framework submodule - NO ADAPTER
from framework.temporal_framework import create_mcp_toolset
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel

from gh_analysis.ai.models import TechnicalAnalysis
from gh_analysis.ai.prompts import TROUBLESHOOTING_PROMPT


class GPT5MediumTroubleshootRunner:
    """GPT-5 Medium reasoning troubleshooting."""

    def __init__(self) -> None:
        # Create MCP toolset using framework (auto-handles uv run)
        mcp_tools = create_mcp_toolset(
            server_command="troubleshoot-mcp-server",
            token_env="SBCTL_TOKEN",
            env={
                "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
                # Add any gh-analysis-specific env vars here
            },
            toolset_id="troubleshoot-mcp",
        )

        # Create agent using standard PydanticAI
        self.agent = Agent(
            model=OpenAIResponsesModel("gpt-5"),
            output_type=TechnicalAnalysis,
            instructions=TROUBLESHOOTING_PROMPT,
            toolsets=[mcp_tools],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1800.0,
                "openai_reasoning_effort": "medium",
                "stream": False,
                "parallel_tool_calls": True,
            },
        )
        self.runner_name = "gpt5-medium"

    async def analyze(self, issue_data: dict) -> TechnicalAnalysis:
        """Run troubleshooting analysis."""
        result = await self.agent.run(issue_data)
        return result.output
```

**Key Points**:
- Import `create_mcp_toolset` directly from framework
- Framework automatically handles `uv run` if binary not in PATH (line 94-104 of mcp.py)
- No adapter needed - framework is flexible by design
- Pass environment variables directly to framework function

#### Step 2.3: Update Memory-Enhanced Runners
Memory-enhanced runners need Snowflake utilities. Check if framework has these:
```bash
ls framework/temporal_framework/
```

If framework doesn't have Snowflake utilities:
- **Option A**: Keep Snowflake utilities in gh-analysis (they're app-specific)
- **Option B**: Add Snowflake utilities to framework (if they're generic enough)

For now, keep Snowflake-specific code in gh-analysis:
```python
from framework.temporal_framework import create_mcp_toolset
from gh_analysis.runners.utils.summary_retrieval import SummaryRetrievalClient  # Keep this
```

### Phase 3: Remove Vendored Code

#### Step 3.1: Identify What Can Be Deleted
Audit what's currently vendored:
```bash
# Check what's in vendored utils
ls -la gh_analysis/runners/utils/
ls -la gh_analysis/runners/summary/utils/

# Check what framework provides
ls -la framework/temporal_framework/
```

Delete utilities that framework provides:
- MCP server creation → framework has `create_mcp_toolset`
- History trimming → check if framework has this
- Tracing/observability → framework has this
- GitHub context building → check if framework has this

Keep gh-analysis-specific utilities:
- Snowflake integration (app-specific)
- Any gh-analysis-specific business logic

#### Step 3.2: Remove Vendored Directories
```bash
# Remove vendored utils (carefully - check dependencies first!)
git rm -r gh_analysis/runners/utils/
git rm -r gh_analysis/runners/summary/utils/

# Commit removal
git commit -m "Remove vendored utilities (now using framework submodule)"
```

**IMPORTANT**: Only do this AFTER updating all imports!

### Phase 4: Update All Runner Files

Apply the direct framework import pattern to:
- [ ] `gh_analysis/runners/base/product_labeling.py`
- [ ] `gh_analysis/runners/troubleshooting/gpt5_mini_medium.py`
- [ ] `gh_analysis/runners/troubleshooting/gpt5_mini_high.py`
- [ ] `gh_analysis/runners/troubleshooting/gpt5_medium.py`
- [ ] `gh_analysis/runners/troubleshooting/gpt5_high.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/claude_sonnet_memory_tool.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/gemini_25_pro_memory_tool.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/gpt5_high_memory_tool.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/gpt5_medium_memory_tool.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/gpt5_mini_high_memory_tool.py`
- [ ] `gh_analysis/runners/troubleshooting/memory_tool/gpt5_mini_medium_memory_tool.py`
- [ ] `gh_analysis/runners/summary/multi_summary.py`
- [ ] All specialized summary agents

For each file:
1. Replace vendored imports with framework imports
2. Use `create_mcp_toolset` directly from framework
3. Keep existing model settings and configurations
4. No behavioral changes

### Phase 5: Add Observability (Optional)

If we want Phoenix tracing like exp05-temporal has:
```python
from framework.temporal_framework.observability import (
    init_observability,
    flush_traces,
    get_temporal_interceptor,
)

# At application startup (in CLI or worker)
init_observability(project_name="gh-analysis")

# At shutdown
flush_traces(timeout_seconds=5)
```

Check if framework has observability module:
```bash
ls framework/temporal_framework/observability.py
```

If not, we can add it to the framework (benefits all projects).

### Phase 6: Testing and Validation

#### Step 6.1: Run Test Suite
```bash
# Format and lint
uv run ruff format . && uv run ruff check --fix --unsafe-fixes

# Type checking
uv run mypy .

# Run all tests
uv run pytest -v
```

#### Step 6.2: Integration Testing
**CRITICAL**: User must provide test repository information.

```bash
# Collect test issue (user provides org/repo/issue)
uv run gh-analysis collect \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE]

# Test product labeling
uv run gh-analysis process product-labeling \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
  --dry-run

# Test troubleshooting with framework MCP
uv run gh-analysis process troubleshoot \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
  --agent gpt5_medium --dry-run

# Test memory-enhanced runner
uv run gh-analysis process troubleshoot \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
  --agent claude_sonnet_mt --dry-run
```

#### Step 6.3: Verify Framework Integration
```bash
# Test framework MCP toolset creation
uv run python -c "
import os
os.environ['SBCTL_TOKEN'] = 'test-token'
from framework.temporal_framework import create_mcp_toolset
mcp = create_mcp_toolset('troubleshoot-mcp-server', token_env='SBCTL_TOKEN')
print('✓ Framework MCP toolset created')
"

# Test framework auto-handles uv run
uv run python -c "
import os
os.environ['SBCTL_TOKEN'] = 'test-token'
from framework.temporal_framework import create_mcp_toolset
# Even if binary not in PATH, framework uses uv run automatically
mcp = create_mcp_toolset('troubleshoot-mcp-server', token_env='SBCTL_TOKEN')
print('✓ Framework auto-handled command not in PATH')
"
```

### Phase 7: Documentation

#### Step 7.1: Update CLAUDE.md
```markdown
## Temporal Framework Integration

gh-analysis uses the Temporal PydanticAI Framework as a git submodule for shared infrastructure.

### First-Time Setup
```bash
# Clone with submodules
git clone --recurse-submodules <repo-url>

# Or initialize after clone
git submodule init
git submodule update
```

### Framework Location
- Submodule: `framework/` directory
- Repository: `~/src/temporal`
- Branch: `pydantic-temporal-framework`

### Framework Provides
- **MCP Integration**: `create_mcp_toolset()` - flexible MCP server creation
- **Agent Utilities**: Helper functions for creating Temporal-compatible agents
- **Observability**: Tracing and monitoring utilities

### Usage Pattern
```python
# Import directly from framework - NO ADAPTERS
from framework.temporal_framework import create_mcp_toolset

# Create MCP toolset
mcp_tools = create_mcp_toolset(
    server_command="troubleshoot-mcp-server",
    token_env="SBCTL_TOKEN",
    env={"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
)

# Use with agent
agent = Agent(
    model="gpt-5",
    toolsets=[mcp_tools],
    ...
)
```

### Updating Framework
```bash
# Pull latest framework changes
cd framework
git pull origin pydantic-temporal-framework
cd ..

# Commit submodule update
git add framework
git commit -m "Update temporal framework"
```

### Important Principle
**If the framework is hard to use, fix THE FRAMEWORK, not gh-analysis.**

The framework is shared infrastructure. If we need new features:
1. Add them to the framework repository
2. Update the submodule in gh-analysis
3. Benefits all projects using the framework
```

#### Step 7.2: Update Architecture Documentation
```markdown
## Framework Integration

gh-analysis uses the Temporal PydanticAI Framework (git submodule) for:
- **MCP Tool Integration**: Auto-discovery and flexible MCP server creation
- **Agent Infrastructure**: Utilities for creating Temporal-compatible agents
- **Observability**: Tracing, monitoring, and instrumentation

### Framework vs Application
- **Framework** (`framework/`): Shared infrastructure, no private data
- **Application** (`gh_analysis/`): gh-analysis-specific logic, prompts, models

### Direct Usage Pattern
gh-analysis imports framework utilities directly:
```python
from framework.temporal_framework import create_mcp_toolset
```

No adapter layer needed - the framework is designed to be flexible.

### Application-Specific Code
gh-analysis maintains its own:
- Agent prompts (`gh_analysis/ai/prompts.py`)
- Response models (`gh_analysis/ai/models.py`)
- CLI interface (`gh_analysis/cli/`)
- Snowflake integration (app-specific utility)
```

## Testing Strategy

### Unit Tests
- [ ] Test framework imports work correctly
- [ ] Test runner instantiation with framework imports
- [ ] Test MCP server creation via framework
- [ ] Test backward compatibility with existing interfaces

### Integration Tests
**NEVER hardcode repository information - always ask user.**

```bash
# User provides org/repo/issue for all tests
uv run gh-analysis collect --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE]

# Test product labeling
uv run gh-analysis process product-labeling \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] --dry-run

# Test troubleshooting
uv run gh-analysis process troubleshoot \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
  --agent gpt5_medium --dry-run

# Test memory-enhanced
uv run gh-analysis process troubleshoot \
  --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
  --agent claude_sonnet_mt --dry-run
```

### Validation Checklist
- [ ] All CLI commands work identically
- [ ] MCP server integration works via framework
- [ ] Agent behavior unchanged
- [ ] Tracing/observability works (if enabled)
- [ ] Submodule initializes on fresh clone
- [ ] Quality checks pass

## Dependencies

### Framework Dependencies
From `framework/pyproject.toml`:
```toml
temporalio[pydantic]>=1.18.0
pydantic-ai>=1.0.14
mcp>=1.16.0
pydantic>=2.11.9
httpx>=0.28.1
```

Check for conflicts:
```bash
uv sync --all-extras
uv tree | grep -E "(pydantic|temporal|mcp)"
```

## Migration Checklist

### Preparation
- [ ] Review framework API in `framework/temporal_framework/`
- [ ] Understand `create_mcp_toolset()` flexibility
- [ ] Identify which vendored code framework replaces
- [ ] Plan import changes for all runners

### Implementation
- [ ] Add temporal framework as submodule at `framework/`
- [ ] Configure submodule to track `pydantic-temporal-framework` branch
- [ ] Update `pyproject.toml` dependencies if needed
- [ ] Update all runner imports to use framework directly
- [ ] Remove vendored code directories
- [ ] Update import references throughout codebase

### Testing
- [ ] Run full test suite
- [ ] Test MCP integration via framework
- [ ] Test all runner types
- [ ] Verify on fresh clone with submodule init

### Documentation
- [ ] Update `CLAUDE.md` with submodule workflow
- [ ] Update architecture docs
- [ ] Document framework usage pattern
- [ ] Note principle: "Fix framework, not gh-analysis"

### Cleanup
- [ ] Remove vendored directories
- [ ] Clean up unused imports
- [ ] Run quality checks

## Success Metrics

### Functional
- [ ] 100% feature parity
- [ ] All CLI commands work
- [ ] All tests pass
- [ ] MCP integration works

### Code Quality
- [ ] Passes ruff format
- [ ] Passes ruff check
- [ ] Passes mypy
- [ ] Passes pytest

### Architecture
- [ ] No vendored code duplication
- [ ] Direct framework usage (no adapters)
- [ ] Framework updates via submodule
- [ ] Clear separation: framework vs application

## Key Insights

### Why No Adapters?
The framework is designed to be flexible:
- `create_mcp_toolset()` takes any command, args, env
- Automatically handles `uv run` if binary not in PATH
- Takes environment variables as dict
- No gh-analysis-specific assumptions

### When to Create Abstractions?
Only when we find repeated boilerplate:
```python
# If we're repeating this everywhere:
mcp_tools = create_mcp_toolset(
    "troubleshoot-mcp-server",
    token_env="SBCTL_TOKEN",
    env={"GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", "")},
)

# We could create a helper:
def get_troubleshoot_tools():
    return create_mcp_toolset(...)
```

But this is convenience, not necessity.

### Framework Evolution
If framework is missing features:
1. Add to `~/src/temporal` repository
2. Update submodule in gh-analysis
3. Benefits both projects
4. Keeps infrastructure shared

## Notes

- **Proven Pattern**: exp05-temporal already uses this successfully
- **No Breaking Changes**: Users see identical behavior
- **Framework First**: Fix framework, not applications
- **Shared Benefits**: Improvements help all projects

## Future Enhancements

### Once Migration Complete
- Pull framework updates via `git submodule update`
- Contribute framework improvements back
- Add Temporal workflows for orchestration
- Use framework's observability features

### If Framework Needs Features
- Add to framework repository
- Update submodule
- Benefits context-experiments and gh-analysis both

## Related Files

- Framework: `~/src/temporal` (branch: `pydantic-temporal-framework`)
- Reference: `~/src/context-experiments/trees/exp05-temporal` (working example)
- Previous Migration: `tasks/migrate-to-runner-pattern.md`
