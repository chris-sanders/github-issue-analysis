# Temporal Integration V2 - Status

## Setup Complete ✅

**Location**: `/Users/chris/src/github-issue-analysis/trees/temporal-v2`
**Branch**: `feature/temporal-v2`

**Completed**:
- Fresh worktree from main
- Git submodule at `src/framework/` pointing to ~/src/temporal
- pyproject.toml configured with Temporal/Phoenix dependencies
- All subprocesses killed
- Ports clear (6006, 7233, 8233)

## Blocked: Framework Structure Mismatch ❌

**Issue**: Framework submodule missing observability.py and loaders.py

**Framework Repo** (`~/src/temporal`):
- Has: `temporal/` directory
- Contains: `__init__.py`, `agents.py`, `mcp.py`, `models.py`
- Missing: `observability.py`, `loaders.py`

**Exp05's Framework** (working copy):
- Has: `temporal/` directory
- Contains: All above PLUS `observability.py`, `loaders.py`

## Options to Proceed

### Option 1: Copy Missing Files to Framework Repo
```bash
cp /Users/chris/src/context-experiments/trees/exp05-temporal/src/framework/temporal/observability.py \
   ~/src/temporal/temporal/
cp /Users/chris/src/context-experiments/trees/exp05-temporal/src/framework/temporal/loaders.py \
   ~/src/temporal/temporal/

cd ~/src/temporal
git add temporal/observability.py temporal/loaders.py
git commit -m "Add observability and loaders modules"
```

Then update submodule in temporal-v2.

### Option 2: Copy Framework as Regular Files
```bash
cd /Users/chris/src/github-issue-analysis/trees/temporal-v2
rm -rf src/framework
cp -r /Users/chris/src/context-experiments/trees/exp05-temporal/src/framework src/
```

Faster but loses submodule tracking.

## What's Ready to Copy (from temporal-clean)

Once framework imports work, these files can be copied:
- `gh_analysis/agents/troubleshoot.py` - Agent definitions (use AgentPlugin pattern)
- `gh_analysis/workflows/troubleshoot.py` - Workflow with agent calls
- `gh_analysis/activities/github.py` - GitHub fetching activity
- `gh_analysis/temporal/` - Models and lifecycle manager
- `gh_analysis/workers/` - Worker setup
- `gh_analysis/cli/troubleshoot.py` - CLI command

## Key Learning

Exp05 **STILL USES** `AgentPlugin(gpt5_mini_medium_agent)` with module-level agents (from latest system reminders). The TypeError isn't from AgentPlugin itself but from the combination with TracingInterceptor + Agent.instrument_all() in the same process.

## Recommendation

Use **Option 1** to preserve submodule tracking for the framework. Then implement with exp05's current working pattern (AgentPlugin + module-level agents).
