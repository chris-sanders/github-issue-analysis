# Temporal Framework Migration Status

## Branch: feature/temporal-framework-migration

Last updated: 2025-10-12

## ✅ What's Complete

### Phase 1: Framework Submodule (100% done)
- ✅ Framework added as git submodule at `framework/`
- ✅ Submodule tracks `pydantic-temporal-framework` branch
- ✅ pyproject.toml updated with framework dependencies
- ✅ All tests passing (465 tests)

### Phase 2a: Framework Utilities (100% done)
**Framework branch**: `feature/add-shared-utilities` (commit a3ddd17)

Added to framework:
- ✅ `temporal_framework/history/` - History trimming
- ✅ `temporal_framework/snowflake/` - Database (base, client, retrieval)
- ✅ `temporal_framework/memory/` - Memory retrieval
- ✅ `temporal_framework/tools/` - search_evidence tool

All utilities tested and importable from framework.

### Phase 2b: Temporal Infrastructure (100% done)
Created in gh-analysis:
- ✅ `gh_analysis/temporal/manager.py` - CLI-managed Temporal lifecycle
- ✅ `gh_analysis/workflows/troubleshoot.py` - TroubleshootWorkflow
- ✅ `gh_analysis/activities/github.py` - fetch_github_issue
- ✅ `gh_analysis/activities/analysis.py` - run_agent_analysis
- ✅ `gh_analysis/agents/troubleshoot.py` - 4 TemporalAgents
- ✅ `gh_analysis/workers/main_worker.py` - Worker factory

## ⬜ What Remains (Phase 2c)

### 1. Update CLI Command (Critical - ~2-3 hours)
**File**: `gh_analysis/cli/process.py`
**Function**: `_run_troubleshoot()` (line 588)

**Current pattern** (lines 702-710):
```python
from ..runners import get_runner
runner = get_runner(agent_name)
# ... load issue ...
result = await runner.analyze(issue_data)
```

**Target pattern**:
```python
from ..temporal import TemporalManager
from ..workflows import TroubleshootWorkflow

async with TemporalManager() as tm:
    result = await tm.execute_workflow(
        TroubleshootWorkflow,
        args=(org, repo, issue_number, agent_name),
        workflow_id=f"troubleshoot-{org}-{repo}-{issue_number}",
    )
```

**Changes needed**:
1. Replace `get_runner()` with `TemporalManager` context manager
2. Remove issue file loading (workflow fetches from GitHub directly)
3. Simplify - Temporal handles orchestration
4. Keep validation (env vars, agent names)

### 2. Fix Import Issues (~1 hour)
Some new files may have import errors that need fixing:
- `gh_analysis/activities/github.py` - May need GitHubClient import fixes
- `gh_analysis/agents/troubleshoot.py` - Verify all imports work
- Run `uv run mypy .` to find type issues

### 3. Test End-to-End (~1-2 hours)
**Test command**:
```bash
# Requires: SBCTL_TOKEN, OPENAI_API_KEY, test issue
uv run gh-analysis process troubleshoot \
  --org YOUR_ORG --repo YOUR_REPO --issue-number YOUR_ISSUE \
  --agent gpt5_medium
```

**Expected flow**:
1. CLI starts Temporal server (subprocess)
2. CLI starts worker (background task)
3. CLI executes TroubleshootWorkflow
4. Workflow → fetch_github_issue activity
5. Workflow → run_agent_analysis activity
6. TemporalAgent runs (each tool call = activity)
7. Result returned to CLI
8. CLI shuts down worker and server

**Verification**:
- Command completes successfully
- Temporal UI shows workflow: http://localhost:8233
- All activities visible
- Tool calls shown as activities
- Result displayed correctly

### 4. Remove Vendored Code (~1 hour)
Once Temporal pattern works, delete old code:
```bash
git rm -r gh_analysis/runners/
# Entire directory gone - replaced by workflows/activities/agents
```

Files to remove:
- `gh_analysis/runners/base/` - Old Runner classes
- `gh_analysis/runners/troubleshooting/` - Old implementations
- `gh_analysis/runners/summary/` - Old summary runners
- `gh_analysis/runners/utils/` - Now in framework
- `gh_analysis/runners/adapters/` - No longer needed

### 5. Update Tests (~2-3 hours)
Tests currently expect Runner pattern. Need to update:
- Tests that import from `gh_analysis.runners`
- Tests that use `Runner.analyze()`
- Add tests for Temporal workflows/activities
- May use `WorkflowEnvironment` for isolated testing

### 6. Merge Framework Branch (~30 minutes)
```bash
# In framework repository
cd /Users/chris/src/temporal
git checkout pydantic-temporal-framework
git merge feature/add-shared-utilities
git push

# In gh-analysis
cd trees/temporal-framework-migration
cd framework
git pull origin pydantic-temporal-framework
cd ..
git add framework
git commit -m "Update framework with merged utilities"
```

## Current File Structure

### Framework (feature/add-shared-utilities)
```
framework/temporal_framework/
├── __init__.py
├── mcp.py              ✅ MCP integration
├── agents.py           ✅ Agent helpers
├── models.py           ✅ Base models
├── history/            ✅ NEW
│   ├── __init__.py
│   └── trimming.py
├── snowflake/          ✅ NEW
│   ├── __init__.py
│   ├── base.py
│   ├── client.py
│   └── retrieval.py
├── memory/             ✅ NEW
│   ├── __init__.py
│   └── retrieval.py
└── tools/              ✅ NEW
    ├── __init__.py
    └── evidence.py
```

### gh-analysis (feature/temporal-framework-migration)
```
gh_analysis/
├── temporal/           ✅ NEW
│   ├── __init__.py
│   └── manager.py
├── workflows/          ✅ NEW
│   ├── __init__.py
│   └── troubleshoot.py
├── activities/         ✅ NEW
│   ├── __init__.py
│   ├── github.py
│   └── analysis.py
├── agents/             ✅ NEW
│   ├── __init__.py
│   └── troubleshoot.py
├── workers/            ✅ NEW
│   ├── __init__.py
│   └── main_worker.py
├── runners/            ⬜ TO DELETE
│   └── ... (entire directory)
└── cli/                ⬜ TO UPDATE
    └── process.py (line 588: _run_troubleshoot)
```

## Next Agent Handoff Instructions

If another agent continues this work:

1. **Start here**: Read this file (MIGRATION_STATUS.md)
2. **Review**: Check `tasks/temporal-framework-migration.md` for full context
3. **Current branch**: `feature/temporal-framework-migration` in trees/temporal-framework-migration
4. **Framework branch**: `feature/add-shared-utilities` in framework/ submodule

### Step-by-Step to Complete:

1. Update `gh_analysis/cli/process.py` function `_run_troubleshoot()`:
   - Replace Runner pattern with TemporalManager
   - See "Target pattern" above

2. Fix any import errors:
   ```bash
   uv run ruff format . && uv run ruff check --fix && uv run mypy .
   ```

3. Test with real issue (requires tokens):
   ```bash
   export SBCTL_TOKEN="..."
   export OPENAI_API_KEY="..."
   uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent gpt5_medium
   ```

4. If test passes, remove vendored code:
   ```bash
   git rm -r gh_analysis/runners/
   ```

5. Update affected tests

6. Merge framework branch and update submodule

## Key Architectural Change

**Before** (Runner pattern):
```
CLI → Runner.analyze() → Agent.run() → Result
```

**After** (Temporal pattern):
```
CLI → TemporalManager → Workflow → Activities → TemporalAgent → Result
                ↓
         [Temporal Server]
                ↓
            [Worker]
```

All managed by CLI in single command!

## Testing Notes

**Quick smoke test** (no Temporal):
```bash
# Test framework imports
uv run python -c "
from temporal_framework import create_mcp_toolset
from temporal_framework.history import create_history_trimmer
from temporal_framework.snowflake import SummaryRetrievalClient
from temporal_framework.memory import retrieve_and_format_memory
from temporal_framework.tools import search_evidence
print('✓ All framework utilities accessible')
"

# Test agent definitions
uv run python -c "
from gh_analysis.agents import get_agent
agent = get_agent('gpt5_medium')
print(f'✓ Agent created: {type(agent).__name__}')
"
```

**Full test** (with Temporal):
```bash
# Requires temporal CLI installed
temporal --version

# Run troubleshoot command
uv run gh-analysis process troubleshoot ... 
```
