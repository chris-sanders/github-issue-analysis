# Temporal Architecture: Current vs Target State

## Current State (Phase 1) - NO TEMPORAL

### What Phase 1 Actually Does
```
User runs: uv run gh-analysis process troubleshoot ...
    ↓
CLI calls: Runner.analyze(issue_data)  
    ↓
Runner runs: agent.run(issue_data) - Direct PydanticAI agent
    ↓
Agent uses: MCP tools (via framework)
    ↓
Returns: TechnicalAnalysis result
```

**No Temporal server or workers involved!** Just:
- Direct Python execution
- Runner classes (GitHubIssueRunner)
- Framework MCP integration

### Architectural Pattern
```
gh-analysis CLI
    └─> Runner.analyze()
        └─> Agent.run()
            └─> MCP tools (framework)
            └─> LLM API calls
```

## Target State (Phase 2) - WITH TEMPORAL

### What Phase 2 Would Add

**1. Temporal Server** (must be running):
```bash
# In terminal 1: Start Temporal dev server
temporal server start-dev --ip '0.0.0.0'
```

**2. Worker Process** (must be running):
```bash
# In terminal 2: Start gh-analysis worker
uv run python workers/gh_analysis_worker.py
```

**3. CLI Submits to Temporal**:
```bash
# In terminal 3: Submit workflow execution
uv run gh-analysis process troubleshoot ...
```

### Workflow Execution Flow
```
User runs: uv run gh-analysis process troubleshoot ...
    ↓
CLI submits: TroubleshootWorkflow to Temporal
    ↓
Temporal server: Queues workflow on task queue
    ↓
Worker picks up: Executes workflow
    ↓
Workflow runs: TemporalAgent (each tool call = activity)
    ↓
Activities use: Framework utilities (MCP, memory, snowflake)
    ↓
Temporal tracks: Every step, can replay on failure
    ↓
Returns: Result to CLI
```

### Architectural Pattern (Temporal)
```
gh-analysis CLI
    └─> Temporal Client (submit workflow)
        └─> Temporal Server (orchestrate)
            └─> Worker Process
                └─> Workflow.run()
                    └─> TemporalAgent.run()
                        └─> Activity: retrieve_memory()
                        └─> Activity: tool calls via MCP
                        └─> Activity: save_results()
```

## Key Differences

### Phase 1 (Current)
- ❌ No Temporal server needed
- ❌ No worker process needed
- ❌ No workflow orchestration
- ✅ Direct Python execution
- ✅ Uses Runner pattern
- ✅ Framework MCP integration

### Phase 2 (Target)
- ✅ Temporal server required
- ✅ Worker process required
- ✅ Workflow orchestration
- ✅ Durable execution (survives crashes)
- ✅ Activity-level retries
- ✅ Temporal UI for observability
- ✅ Each tool call is an activity
- ✅ Memory/Snowflake queries are activities

## Example: exp05-temporal (Full Temporal)

```bash
# Terminal 1: Temporal server
temporal server start-dev --ip '0.0.0.0'

# Terminal 2: Worker
cd /Users/chris/src/context-experiments/trees/exp05-temporal
uv run python exp/exp05_temporal/workers/main_worker.py

# Terminal 3: Run analysis
uv run python exp/exp05_temporal/test_single.py
```

**exp05-temporal has:**
- `workers/main_worker.py` - Registers workflows and activities
- `workflows/github_analysis.py` - Workflow definitions
- `activities.py` - Activity definitions
- `agents/troubleshoot.py` - TemporalAgent definitions

**gh-analysis currently has:**
- ❌ No workers
- ❌ No workflows  
- ❌ No activities
- ❌ No TemporalAgent
- ✅ Just Runner classes

## What Phase 2 Would Create

### 1. Worker Process
```python
# gh_analysis/workers/main_worker.py
from temporalio.client import Client
from temporalio.worker import Worker

from gh_analysis.workflows import TroubleshootWorkflow
from gh_analysis.activities import fetch_github_issue, retrieve_memory
from gh_analysis.agents import gpt5_medium_agent

async def main():
    client = await Client.connect("localhost:7233")
    
    worker = Worker(
        client,
        task_queue="gh-analysis-queue",
        workflows=[TroubleshootWorkflow],
        activities=[fetch_github_issue, retrieve_memory],
        # TemporalAgent activities registered automatically
    )
    
    await worker.run()
```

### 2. Workflow Definition
```python
# gh_analysis/workflows/troubleshoot.py
from temporalio import workflow
from gh_analysis.agents import gpt5_medium_agent

@workflow.defn
class TroubleshootWorkflow:
    @workflow.run
    async def run(self, org: str, repo: str, issue_number: int) -> dict:
        # Fetch issue (activity)
        issue_data = await workflow.execute_activity(
            fetch_github_issue,
            args=(org, repo, issue_number),
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Retrieve memory (activity)
        memory_context = await workflow.execute_activity(
            retrieve_memory,
            args=(issue_data,),
            start_to_close_timeout=timedelta(minutes=2),
        )
        
        # Run agent (TemporalAgent - each tool call = activity)
        result = await gpt5_medium_agent.run(issue_data)
        
        return result.output
```

### 3. CLI Triggers Workflow
```python
# gh_analysis/cli/process.py (Phase 2)
async def troubleshoot(org: str, repo: str, issue_number: int):
    # Connect to Temporal
    client = await Client.connect("localhost:7233")
    
    # Submit workflow execution
    result = await client.execute_workflow(
        TroubleshootWorkflow.run,
        args=(org, repo, issue_number),
        id=f"troubleshoot-{org}-{repo}-{issue_number}",
        task_queue="gh-analysis-queue",
    )
    
    return result
```

## Why Temporal?

### Benefits of Phase 2
1. **Durability** - Worker can crash, workflow resumes
2. **Observability** - Every step visible in Temporal UI
3. **Retries** - Activity-level retry policies
4. **History** - Full execution history preserved
5. **Tool Isolation** - Each tool call is separate activity
6. **Parallel Execution** - Multiple workflows at once
7. **Long Running** - Workflows can run for days

### What You Lose Without Temporal
- No durability (process crash = start over)
- No built-in observability
- Manual retry logic
- No execution history
- No tool-level isolation

## Summary

| Feature | Phase 1 (Current) | Phase 2 (Temporal) |
|---------|-------------------|-------------------|
| Temporal Server | Not needed | **Required** |
| Worker Process | Not needed | **Required** |
| Framework MCP | ✅ Yes | ✅ Yes |
| Shared Utilities | ❌ Duplicated | ✅ In framework |
| Runner Pattern | ✅ Still exists | ❌ Removed |
| Workflows | ❌ No | ✅ Yes |
| Activities | ❌ No | ✅ Yes |
| TemporalAgent | ❌ No | ✅ Yes |
| Durability | ❌ No | ✅ Yes |
| Observability | Limited | ✅ Temporal UI |

## Answer to Your Question

**Phase 1**: CLI runs agents directly, no Temporal server/workers needed.

**Phase 2**: CLI would submit to Temporal, requiring:
1. `temporal server start-dev` (running)
2. `uv run python workers/main_worker.py` (running)
3. CLI submits workflow execution requests
