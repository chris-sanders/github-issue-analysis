# Architecture Overview

## Framework Integration

gh-analysis uses the Temporal PydanticAI Framework (git submodule) for shared infrastructure.

### Framework vs Application
- **Framework** (`framework/`): Shared infrastructure, no private data
  - MCP tool integration (`create_mcp_toolset`)
  - Agent utilities for Temporal-compatible agents
  - Common patterns shared with context-experiments
- **Application** (`gh_analysis/`): gh-analysis-specific logic
  - Agent prompts and response models
  - CLI interface and commands
  - Runner classes (GitHubIssueRunner, MemoryAwareGitHubRunner)
  - Snowflake integration for memory-enhanced runners
  - History trimming utilities
  - Business logic and workflows

### Direct Framework Usage
gh-analysis imports framework utilities directly - no adapter layer needed:
```python
from temporal_framework import create_mcp_toolset
```

The framework is designed to be flexible and handle common use cases:
- Automatically uses `uv run` if command not in PATH
- Creates isolated temp directories for MCP servers
- Manages environment variables
- Provides consistent API across projects

### Application-Specific Code
gh-analysis maintains its own utilities for app-specific needs:
- `GitHubIssueRunner` / `MemoryAwareGitHubRunner` - Runner base classes
- `create_history_trimmer()` - Context window management (model-specific)
- `search_evidence()` - Snowflake evidence search tool
- `SnowflakeDevClient` - Database connectivity
- Summary retrieval and case memory systems

## System Components

### Core Application
```
github_issue_analysis/
├── cli/              # Command-line interface
├── github_client/    # GitHub API integration
├── ai/              # AI processing layer
└── storage/         # Data persistence
```

### Data Flow
```
GitHub API → Issue Collection → JSON Storage → **Batch AI Processing** → Results
```

### CLI Commands
- `collect`: Fetch issues from GitHub using advanced search
- `batch`: **Batch AI processing (recommended)** - cost-effective parallel analysis
- `process`: Individual AI analysis (use only for single issues or testing)

## Component Details

### GitHub Client Layer
- **search.py**: Wrapper around GitHub advanced search API
- **fetcher.py**: Issue fetching with rate limiting and pagination
- **models.py**: Pydantic models for GitHub data structures

### AI Processing Layer
- **agents.py**: PydanticAI agent definitions (direct usage, no wrappers)
- **analysis.py**: Core analysis functions (`analyze_issue`, `prepare_issue_for_analysis`)
- **prompts.py**: Prompt constants for different agents
- **models.py**: Pydantic response models for structured AI output
- **image_utils.py**: Image loading and processing utilities
- **batch/**: Batch processing system for cost-effective parallel analysis

### Storage Layer
- **Issues**: JSON files in `data/issues/` named `org_repo_issue_<number>.json`
- **Results**: AI analysis results in `data/results/`
- **Attachments**: Files in `data/attachments/org_repo_issue_<number>/` directories
- **manager.py**: File I/O operations and data management

## Development Workflow

### Agent Development Process
1. Agent reads task specification from `tasks/task-name.md`
2. Creates git worktree: `git worktree add trees/task-name -b feature/task-name`
3. Implements feature with full test coverage
4. Documents progress and validation in task file
5. Creates pull request when complete

### Task Structure
Each task should deliver a complete, testable feature that can be used independently.

## Design Principles

- **Separation of Concerns**: Clear boundaries between GitHub API, AI processing, and storage
- **Direct PydanticAI Usage**: Agents are used directly without unnecessary wrappers
- **Extensibility**: Easy to add new agents and analysis types
- **Testability**: Each component can be tested in isolation
- **Agent-Friendly**: Clear documentation and minimal boilerplate for rapid development

## Adding New AI Agents

To add a new AI agent for a different analysis type:

1. **Define the agent** in `ai/agents.py`:
   ```python
   issue_classification_agent = Agent(
       output_type=IssueClassificationResponse,
       instructions=ISSUE_CLASSIFICATION_PROMPT,
       retries=2,
   )
   ```

2. **Create response model** in `ai/models.py`:
   ```python
   class IssueClassificationResponse(BaseModel):
       # Define your structured output
   ```

3. **Add prompt** in `ai/prompts.py`:
   ```python
   ISSUE_CLASSIFICATION_PROMPT = """..."""
   ```

4. **Create CLI command** in `cli/process.py`:
   ```python
   @app.command()
   def issue_classification(...):
       # Use analyze_issue() with your agent
       result = await analyze_issue(
           issue_classification_agent,
           issue_data,
           model=model,
           model_settings=model_settings,
       )
   ```

**Note**: The CLI command name (e.g., `issue-classification`) is mapped to the function name (`issue_classification`) by Typer. The function manually specifies which agent to use - there's no automatic registry or dynamic mapping.