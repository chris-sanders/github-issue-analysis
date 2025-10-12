# Integration Testing Guide - Temporal Framework Migration

## Prerequisites

### Required Environment Variables
```bash
export SBCTL_TOKEN="your-sbctl-token"          # Required for MCP tools
export OPENAI_API_KEY="your-openai-key"       # Required for GPT-5 agents
export ANTHROPIC_API_KEY="your-anthropic-key" # Required for Claude agents
export GITHUB_TOKEN="your-github-token"        # Optional but recommended
```

### Required Tools
```bash
# Temporal CLI (for observability)
brew install temporal

# Verify installation
temporal --version
```

### Test Repository Information
You'll need a GitHub repository with an issue to test against.
**DO NOT hardcode** - provide at runtime:
- Organization: `YOUR_ORG`
- Repository: `YOUR_REPO`
- Issue Number: `YOUR_ISSUE`

## What to Test

### Test 1: GPT-5 Agent via Temporal
```bash
uv run gh-analysis process troubleshoot \
  --org YOUR_ORG \
  --repo YOUR_REPO \
  --issue-number YOUR_ISSUE \
  --agent gpt5_medium
```

**Expected behavior**:
1. CLI prints: "✓ Using gpt5_medium agent with Temporal orchestration"
2. CLI prints: "🚀 Starting Temporal infrastructure..."
3. CLI prints: "✓ Temporal server and worker ready"
4. CLI prints: "📋 Executing troubleshoot workflow..."
5. Workflow executes (may take 5-30 minutes depending on issue complexity)
6. CLI prints: "✓ Analysis completed in X.Xs"
7. CLI prints: "View workflow in Temporal UI: http://localhost:8233"
8. Analysis results displayed
9. Results saved to `data/results/troubleshoot/`
10. CLI cleans up and exits

**Verify in Temporal UI** (http://localhost:8233):
- Workflow appears with ID: `troubleshoot-YOUR_ORG-YOUR_REPO-YOUR_ISSUE`
- Activities visible:
  - `fetch_github_issue` - GitHub API call
  - `run_agent_analysis` - Agent execution
  - Tool calls from TemporalAgent (each MCP tool call = activity)
- Workflow status: Completed
- Execution timeline shows all steps

### Test 2: Claude Agent via Temporal
```bash
uv run gh-analysis process troubleshoot \
  --org YOUR_ORG \
  --repo YOUR_REPO \
  --issue-number YOUR_ISSUE \
  --agent claude_sonnet_4_5
```

**Expected behavior**:
- Same flow as Test 1
- Uses Anthropic API instead of OpenAI
- Verifies multi-provider support (OpenAI + Anthropic)

**Verify in Temporal UI**:
- New workflow execution
- Different agent activities
- Claude-specific tool calls

### Test 3: Dry Run (No Temporal)
```bash
uv run gh-analysis process troubleshoot \
  --org YOUR_ORG \
  --repo YOUR_REPO \
  --issue-number YOUR_ISSUE \
  --agent gpt5_medium \
  --dry-run
```

**Expected behavior**:
- Prints: "Would analyze YOUR_ORG/YOUR_REPO#YOUR_ISSUE with gpt5_medium agent via Temporal"
- Prints: "Temporal orchestration: workflow + activities"
- Exits without running workflow
- No Temporal server started

### Test 4: All Available Agents
Test each agent to verify they all work:

```bash
# GPT-5 Mini Medium
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent gpt5_mini_medium

# GPT-5 Mini High  
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent gpt5_mini_high

# GPT-5 Medium
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent gpt5_medium

# GPT-5 High
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent gpt5_high

# Claude Sonnet 4
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent claude_sonnet_4

# Claude Sonnet 4.5
uv run gh-analysis process troubleshoot --org X --repo Y --issue-number Z --agent claude_sonnet_4_5
```

### Test 5: Framework Utilities Verification

**Verify NO vendored code is used**:
```bash
# This should fail (runners deleted)
uv run python -c "from gh_analysis.runners import get_runner"  # Should error

# These should work (framework)
uv run python -c "
from temporal_framework import create_mcp_toolset
from temporal_framework.history import create_history_trimmer
from temporal_framework.snowflake import SummaryRetrievalClient
from temporal_framework.memory import retrieve_and_format_memory
from temporal_framework.tools import search_evidence
print('✓ All utilities from framework')
"

# Agent imports
uv run python -c "
from gh_analysis.agents import get_agent, AVAILABLE_AGENTS
print(f'✓ Agents: {list(AVAILABLE_AGENTS.keys())}')
"
```

## What Success Looks Like

### CLI Output Example
```
✓ Using gpt5_medium agent with Temporal orchestration
🚀 Starting Temporal infrastructure...
✓ Temporal server and worker ready
📋 Executing troubleshoot workflow...
✓ Analysis completed in 127.3s
View workflow in Temporal UI: http://localhost:8233

🔍 Troubleshoot Analysis Results

✅ Root Cause Identified

Root Cause:
[Analysis output...]

Evidence:
1. [Evidence item...]

Recommended Solution:
[Solution output...]

Analysis Validation:
[Validation output...]

✓ Results saved to org_repo_issue_123_troubleshoot_gpt5_medium.json
```

### Temporal UI Shows
- Workflow ID: `troubleshoot-org-repo-123`
- Status: Completed
- Activities:
  - `fetch_github_issue` (5-10s)
  - `run_agent_analysis` (60-300s)
  - Tool calls as sub-activities (1-30s each)
- Full execution history
- Replay capability

## Troubleshooting

### Issue: "temporal: command not found"
```bash
brew install temporal
```

### Issue: "Failed to connect to Temporal"
The TemporalManager should start the server automatically. If it fails:
```bash
# Check if port 7233 is already in use
lsof -i :7233

# Manually test server startup
temporal server start-dev --ip '0.0.0.0'
```

### Issue: "SBCTL_TOKEN not set"
```bash
export SBCTL_TOKEN="your-token"
```

### Issue: "Unknown agent: XXX"
Run to see available agents:
```bash
uv run python -c "
from gh_analysis.agents import AVAILABLE_AGENTS
print('Available:', list(AVAILABLE_AGENTS.keys()))
"
```

### Issue: Workflow times out
- GPT-5 can be slow with many tool calls
- Claude extended thinking can take time
- Check Temporal UI for activity details
- Increase timeout if needed

## Success Criteria

✅ **All 6 agents work** (4 GPT-5 + 2 Claude)
✅ **Single command execution** (no manual server/worker start)
✅ **Framework utilities used** (no vendored code)
✅ **Temporal observability** (visible in UI)
✅ **Results saved correctly**
✅ **Clean shutdown** (server and worker stopped)

## Next Steps After Testing

Once integration tests pass:

1. **Merge framework branch**:
   ```bash
   cd /Users/chris/src/temporal
   git checkout pydantic-temporal-framework
   git merge feature/add-shared-utilities
   git push
   ```

2. **Update gh-analysis submodule**:
   ```bash
   cd trees/temporal-framework-migration/framework
   git pull origin pydantic-temporal-framework
   cd ..
   git add framework
   git commit -m "Update framework with merged utilities"
   ```

3. **Create pull request**:
   ```bash
   gh pr create --title "Migrate to Temporal Framework" --body "..."
   ```

4. **Update context-experiments** to use framework utilities (remove duplication there too)
