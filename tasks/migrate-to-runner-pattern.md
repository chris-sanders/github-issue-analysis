# Task: Migrate github-issue-analysis to Runner Pattern

## Status
**Status:** Completed  
**Assigned:** TBD  
**Priority:** High  
**Estimated Effort:** 2-3 days  

## Overview

Migrate the github-issue-analysis tool from its current scattered agent implementation to the organized runner pattern developed in exp05. This will centralize agent configurations, improve maintainability, enable better observability through Phoenix/MLflow tracing, and facilitate easier addition of new agents with updated tools.

## Background

The current implementation in `github_issue_analysis/ai/` has several limitations:
- Agents are defined separately from their prompts, tools, and configurations
- No centralized place to manage agent variations (different models, reasoning levels)
- Limited observability and tracing capabilities
- Difficult to add new agents or modify existing ones
- Error handling and retry logic scattered across modules

The exp05 runner pattern provides a clean solution:
- Self-contained runner classes that encapsulate everything needed for an agent
- Built-in Phoenix/MLflow tracing with span IDs for evaluation
- Consistent error handling with automatic retry logic for model-specific issues
- Model-specific patches applied automatically when needed
- Easy CLI integration for swapping agents

## Acceptance Criteria

### Core Infrastructure
- [ ] Copy `src/utils/` directory from `/Users/chris/src/context-experiments/trees/exp05/` to `github_issue_analysis/runners/utils/`
- [ ] All copied utilities work with github-issue-analysis environment (no import errors)
- [ ] MCP server configuration adapted for local `uv run troubleshoot-mcp-server` command

### Runner Implementation  
- [ ] Create `runners/` directory with proper structure:
  ```
  github_issue_analysis/
  ├── runners/
  │   ├── __init__.py           # Runner registry
  │   ├── utils/                # Copied from exp05
  │   ├── base/
  │   │   ├── __init__.py
  │   │   └── product_labeling.py
  │   └── troubleshooting/
  │       ├── __init__.py
  │       ├── gpt5_mini_medium.py
  │       ├── gpt5_mini_high.py
  │       ├── gpt5_medium.py
  │       ├── gpt5_high.py
  │       ├── o3_medium.py
  │       └── o3_high.py
  ```

- [ ] Implement `ProductLabelingRunner` that produces identical output to current implementation
- [ ] Implement all 6 troubleshooting runners that match current agent configurations:
  - GPT-5 Mini Medium/High reasoning
  - GPT-5 Medium/High reasoning  
  - O3 Medium/High reasoning
- [ ] Runner registry with `get_runner(name: str)` function for CLI integration

### CLI Integration
- [ ] Update `cli/process.py` to use runners instead of direct agent creation
- [ ] `product-labeling` command works identically to current implementation
- [ ] `troubleshoot` command works with all runner variations
- [ ] All existing CLI flags and options continue to work
- [ ] Error messages remain helpful and specific

### Backward Compatibility
- [ ] All existing functionality works unchanged from user perspective
- [ ] Same input formats, same output formats, same file locations
- [ ] Existing batch processing works with new runners
- [ ] No breaking changes to stored results format

### Testing
- [ ] Unit tests for each runner class
- [ ] Integration tests with real GitHub issues using `--dry-run`
- [ ] Verification that output matches current implementation exactly
- [ ] All existing tests pass without modification

## Implementation Details

### Phase 1: Infrastructure Copy (NO MODIFICATIONS)
Copy the entire `src/utils/` directory structure **WITHOUT ANY MODIFICATIONS**:
- `base_runner.py` - Core execution logic with retry handling
- `github_runner.py` - GitHub issue context building  
- `github_context.py` - Issue formatting utilities
- `mcp.py` - MCP server configuration (will be wrapped, not modified)
- `history.py` - Context length management
- `gemini_patches.py` - Model-specific monkey patches
- Tracing utilities: `phoenix_integration.py`, `context_tracking.py`, `mcp_instrumentation.py`

**CRITICAL:** DO NOT MODIFY ANY FILES IN UTILS/ - These remain pristine for future updates from exp05

### Phase 2: Create Adapter Layer (NEW)
Create `runners/adapters/` directory to wrap utils that need different behavior:

**Directory Structure:**
```
github_issue_analysis/
├── runners/
│   ├── utils/           # UNMODIFIED copy from exp05
│   ├── adapters/        # Our customizations  
│   │   ├── __init__.py
│   │   └── mcp_adapter.py
│   ├── base/
│   └── troubleshooting/
```

**MCP Adapter Implementation:**
Create `runners/adapters/mcp_adapter.py`:
```python
"""MCP adapter to bridge between utils and github-issue-analysis."""

import os
import tempfile
import logging
from typing import Optional
from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)

def create_troubleshoot_mcp_server(log_handler: Optional = None) -> MCPServerStdio:
    """Create MCP server using github-issue-analysis's local approach.
    
    This adapter provides the same interface as utils.mcp but uses
    our local uv run approach instead of podman.
    """
    sbctl_token = os.getenv("SBCTL_TOKEN")
    if not sbctl_token:
        raise ValueError("SBCTL_TOKEN environment variable is required")
    
    github_token = os.getenv("GITHUB_TOKEN")  # Optional in our case
    
    # Create isolated temp directory (matching utils pattern)
    isolated_temp = tempfile.mkdtemp(prefix="mcp-troubleshoot-")
    logger.info(f"Created MCP workspace: {isolated_temp}")
    
    # Prepare environment (matching current implementation)
    env = os.environ.copy()
    env["SBCTL_TOKEN"] = sbctl_token
    env["TMPDIR"] = isolated_temp
    env["PYTHONPATH"] = env.get("PYTHONPATH", "")
    env["PYTHONWARNINGS"] = "ignore"
    
    if github_token:
        env["GITHUB_TOKEN"] = github_token
        logger.debug("GitHub token provided to MCP server")
    
    # Use our local uv run approach (preserving current behavior)
    log_file = f"{isolated_temp}/mcp-server.log"
    return MCPServerStdio(
        "sh",
        args=["-c", f"uv run troubleshoot-mcp-server 2>{log_file}"],
        env=env,
        timeout=120.0,  # Longer timeout for GPT-5 compatibility
        max_retries=3,  # Match our current retry logic
    )
```

### Phase 3: Product Labeling Runner
Create `runners/base/product_labeling.py`:
```python
"""Product labeling runner using runner pattern."""

from pydantic_ai import Agent
from ..utils.github_runner import GitHubIssueRunner
from ...ai.models import ProductLabelingResponse
from ...ai.prompts import PRODUCT_LABELING_PROMPT

class ProductLabelingRunner(GitHubIssueRunner):
    """Product labeling analysis using runner pattern."""
    
    def __init__(self, model_name="openai:o4-mini", model_settings=None):
        # Create agent with same configuration as current implementation
        agent = Agent(
            model=model_name,
            output_type=ProductLabelingResponse,
            instructions=PRODUCT_LABELING_PROMPT,
            retries=2,
            instrument=True,
            model_settings=model_settings or {},
        )
        super().__init__("product-labeling", agent)
```

### Phase 4: Troubleshooting Runners
Each troubleshooting runner must match current `troubleshooting_agents.py` configurations exactly:

**Example: GPT5MediumTroubleshootRunner**
```python
"""GPT-5 Medium reasoning troubleshooting runner."""

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from ..utils.github_runner import GitHubIssueRunner
from ..adapters.mcp_adapter import create_troubleshoot_mcp_server
from ..utils.history import create_history_trimmer
from ...ai.models import TechnicalAnalysis
from ...ai.prompts import TROUBLESHOOTING_PROMPT

class GPT5MediumTroubleshootRunner(GitHubIssueRunner):
    """GPT-5 Medium reasoning troubleshooting analysis."""
    
    def __init__(self):
        # Match current agent configuration exactly
        history_trimmer = create_history_trimmer(
            max_tokens=400_000, critical_ratio=0.9, high_ratio=0.8
        )
        
        agent = Agent(
            model=OpenAIResponsesModel("gpt-5"),
            output_type=TechnicalAnalysis,
            instructions=TROUBLESHOOTING_PROMPT,
            history_processors=[history_trimmer],
            toolsets=[create_troubleshoot_mcp_server()],
            instrument=True,
            retries=2,
            model_settings={
                "timeout": 1800.0,
                "openai_reasoning_effort": "medium",
                "stream": False,
                "parallel_tool_calls": True,
            },
        )
        super().__init__("gpt5-medium", agent)
```

**Critical Requirements:**
- Model settings must match current `troubleshooting_agents.py` exactly
- Timeouts, reasoning effort, retries, and other parameters identical
- History trimming configurations preserved
- MCP server integration identical

### Phase 5: Runner Registry
Create `runners/__init__.py`:
```python
"""Runner registry for github-issue-analysis."""

from typing import Dict, Type, Union
from .utils.github_runner import GitHubIssueRunner
from .base.product_labeling import ProductLabelingRunner
from .troubleshooting.gpt5_mini_medium import GPT5MiniMediumTroubleshootRunner
from .troubleshooting.gpt5_mini_high import GPT5MiniHighTroubleshootRunner
from .troubleshooting.gpt5_medium import GPT5MediumTroubleshootRunner
from .troubleshooting.gpt5_high import GPT5HighTroubleshootRunner
from .troubleshooting.o3_medium import O3MediumTroubleshootRunner
from .troubleshooting.o3_high import O3HighTroubleshootRunner

RUNNERS: Dict[str, Type[GitHubIssueRunner]] = {
    "product-labeling": ProductLabelingRunner,
    "gpt5_mini_medium": GPT5MiniMediumTroubleshootRunner,
    "gpt5_mini_high": GPT5MiniHighTroubleshootRunner,
    "gpt5_medium": GPT5MediumTroubleshootRunner,
    "gpt5_high": GPT5HighTroubleshootRunner,
    "o3_medium": O3MediumTroubleshootRunner,
    "o3_high": O3HighTroubleshootRunner,
}

def get_runner(name: str, **kwargs) -> GitHubIssueRunner:
    """Get runner instance by name."""
    if name not in RUNNERS:
        available = ", ".join(RUNNERS.keys())
        raise ValueError(f"Unknown runner: {name}. Available: {available}")
    
    runner_class = RUNNERS[name]
    return runner_class(**kwargs)

def list_runners() -> Dict[str, str]:
    """Get list of available runners with descriptions."""
    return {
        "product-labeling": "Product label recommendations using configurable models",
        "gpt5_mini_medium": "GPT-5 Mini with medium reasoning for troubleshooting",
        "gpt5_mini_high": "GPT-5 Mini with high reasoning for troubleshooting",
        "gpt5_medium": "GPT-5 with medium reasoning for troubleshooting",
        "gpt5_high": "GPT-5 with high reasoning for troubleshooting",
        "o3_medium": "OpenAI O3 with medium reasoning for troubleshooting",
        "o3_high": "OpenAI O3 with high reasoning for troubleshooting",
    }
```

### Phase 6: CLI Integration
Update `cli/process.py` to use runners:

**Product Labeling Integration:**
```python
# In product_labeling command function
async def _process_single_issue(
    file_path: Path,
    recommendation_manager: RecommendationManager,
    results_dir: Path,
    model: str,
    model_settings: dict[str, Any],
    include_images: bool,
    reprocess: bool,
    semaphore: asyncio.Semaphore,
) -> str:
    """Process single issue using runner pattern."""
    async with semaphore:
        # Load issue data
        with open(file_path) as f:
            issue_data = json.load(f)
        
        # Check reprocessing logic (unchanged)
        # ... existing logic ...
        
        # Use runner instead of direct agent
        from ..runners import get_runner
        
        runner = get_runner(
            "product-labeling", 
            model_name=model, 
            model_settings=model_settings
        )
        
        # Analyze using runner
        result = await runner.analyze(issue_data)
        
        # Save result (unchanged)
        # ... existing save logic ...
```

**Troubleshooting Integration:**
```python
# In troubleshoot command function  
async def _run_troubleshoot(
    org: str | None,
    repo: str | None,
    issue_number: int | None,
    url: str | None,
    agent_name: str,
    include_images: bool,
    limit_comments: int | None,
    dry_run: bool,
    interactive: bool,
) -> None:
    """Run troubleshooting using runner pattern."""
    
    # Existing validation logic unchanged
    # ... URL parsing, environment validation ...
    
    # Use runner instead of create_troubleshooting_agent
    from ..runners import get_runner
    
    try:
        runner = get_runner(agent_name)
        console.print(f"[blue]✓ Created {agent_name} troubleshoot runner[/blue]")
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        return
    
    # Load issue data (unchanged)
    # ... existing issue loading logic ...
    
    # Analyze using runner
    result = await runner.analyze(processed_issue_data)
    
    # Display and save results (unchanged) 
    # ... existing result handling ...
```

### Phase 7: Tracing Configuration
Add optional tracing support:
```python
# In runners/utils/tracing.py
"""Tracing configuration for runners."""

import os
from typing import Optional

def setup_tracing(backend: Optional[str] = None) -> str:
    """Setup tracing backend."""
    backend = backend or os.getenv("TRACING_BACKEND", "file").lower()
    
    if backend == "phoenix":
        try:
            from .phoenix_integration import setup_phoenix_tracing
            setup_phoenix_tracing()
            return "phoenix"
        except ImportError:
            print("Phoenix tracing unavailable, falling back to file")
            return "file"
    elif backend == "mlflow":
        try:
            import mlflow
            # MLflow setup if needed
            return "mlflow"
        except ImportError:
            print("MLflow tracing unavailable, falling back to file") 
            return "file"
    
    return "file"
```

## Testing Strategy

**CRITICAL REPOSITORY POLICY:**
- NEVER hardcode real GitHub organization or repository names in code, tests, or documentation
- ALWAYS ask the user to provide repository information for validation testing  
- Use placeholder values like `[USER-PROVIDED-ORG]` in documentation
- Keep all real repository information out of the codebase

### Unit Tests
Create `tests/runners/` directory with tests for each runner:

```bash
# Test adapter layer functionality
uv run pytest tests/runners/adapters/test_mcp_adapter.py -v

# Test runner creation and basic functionality
uv run pytest tests/runners/test_product_labeling.py -v
uv run pytest tests/runners/test_troubleshooting.py -v
uv run pytest tests/runners/test_registry.py -v
```

**Required Test Cases:**
- **Adapter layer**: MCP server creation, environment setup, proper interface matching
- **Runner instantiation**: All runners create without errors
- **Agent configuration**: Model, settings, tools configured correctly
- **Registry functionality**: Lookup, error handling, list operations work
- **Model-specific patches**: Applied correctly for each model type

### Integration Tests  
Test with real GitHub issues using `--dry-run`:

**IMPORTANT:** Before testing, ask the user to provide:
- GitHub organization name (never hardcode real org names)  
- Repository name (never hardcode real repo names)
- Issue number (never hardcode real issue numbers)

All repository information must be user-provided at runtime, not embedded in code or documentation.

```bash
# Collect test issue if not present (ask user for org/repo/issue)
uv run github-analysis collect --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE]

# Test product labeling with runner (safe, dry-run only)
uv run github-analysis process product-labeling --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE] --dry-run

# Test troubleshooting with each runner type (safe, dry-run only)  
uv run github-analysis process troubleshoot --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE] --agent gpt5_medium --dry-run
uv run github-analysis process troubleshoot --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE] --agent o3_high --dry-run
```

**Critical Validation:**
- CLI commands work identically to current implementation
- Help text shows correct options and descriptions  
- Error messages remain helpful and specific
- No functional regression in any existing feature

### Output Verification
Compare runner outputs with current implementation:

**IMPORTANT:** Use the same user-provided repository information from Integration Tests above.

```bash
# Generate results with current implementation (ask user for org/repo/issue)
uv run github-analysis process product-labeling --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE] 

# Generate results with runner implementation  
uv run github-analysis process product-labeling --org [USER-PROVIDED-ORG] --repo [USER-PROVIDED-REPO] --issue-number [USER-PROVIDED-ISSUE]

# Compare JSON outputs - they must be identical
```

## Migration Checklist

### Infrastructure Setup
- [ ] Copy `src/utils/` from exp05 to `github_issue_analysis/runners/utils/` WITHOUT ANY MODIFICATIONS
- [ ] Create `runners/adapters/` directory structure
- [ ] Implement `mcp_adapter.py` with local uv run approach
- [ ] Add proper `__init__.py` files for adapter imports
- [ ] Verify utils imports work without modifications
- [ ] Test adapter creates functional MCP server

### Runner Implementation  
- [ ] Create `runners/` directory structure with proper `__init__.py` files
- [ ] Implement `ProductLabelingRunner` with identical output to current
- [ ] Implement `GPT5MiniMediumTroubleshootRunner` matching current config
- [ ] Implement `GPT5MiniHighTroubleshootRunner` matching current config
- [ ] Implement `GPT5MediumTroubleshootRunner` matching current config
- [ ] Implement `GPT5HighTroubleshootRunner` matching current config  
- [ ] Implement `O3MediumTroubleshootRunner` matching current config
- [ ] Implement `O3HighTroubleshootRunner` matching current config
- [ ] Create runner registry with `get_runner()` function
- [ ] Add `list_runners()` utility for CLI help

### CLI Integration
- [ ] Update `cli/process.py` product-labeling command to use ProductLabelingRunner
- [ ] Update `cli/process.py` troubleshoot command to use troubleshooting runners  
- [ ] Preserve all existing CLI flags and behavior
- [ ] Update help text to reference runner pattern where appropriate
- [ ] Ensure error messages remain clear and actionable

### Testing and Validation
- [ ] Write unit tests for all runners
- [ ] Write integration tests using `--dry-run`
- [ ] Test runner registry and error handling
- [ ] Verify backward compatibility with existing workflows
- [ ] Test with various model settings and configurations
- [ ] Validate tracing works (if enabled)

### Quality Assurance
- [ ] Run full test suite: `uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`
- [ ] All existing tests pass without modification
- [ ] No breaking changes to CLI interface
- [ ] No changes to output file formats or locations
- [ ] Performance equivalent to current implementation

### Documentation  
- [ ] Update `docs/architecture.md` with runner pattern explanation
- [ ] Create `docs/runners.md` with detailed runner documentation
- [ ] Update `CLAUDE.md` with runner usage examples
- [ ] Add inline code documentation for all new classes

### Cleanup
- [ ] Mark deprecated functions in `ai/agents.py` and `ai/troubleshooting_agents.py`
- [ ] Remove unused imports and dead code
- [ ] Update `pyproject.toml` dependencies if needed

## Dependencies

### New Dependencies
Check if these packages from exp05 are needed and add to `pyproject.toml`:
```toml
# Tracing dependencies (optional)
opentelemetry-api = { version = "^1.20.0", optional = true }
opentelemetry-sdk = { version = "^1.20.0", optional = true }
opentelemetry-exporter-otlp = { version = "^1.20.0", optional = true }
arize-phoenix = { version = "^4.0.0", optional = true }
mlflow = { version = "^2.8.0", optional = true }

[tool.uv.extras]
tracing = ["opentelemetry-api", "opentelemetry-sdk", "opentelemetry-exporter-otlp", "arize-phoenix"]
mlflow = ["mlflow"]
```

### Environment Variables
Document required environment variables:
- `SBCTL_TOKEN` - Required for MCP troubleshooting tools
- `GITHUB_TOKEN` - Optional for enhanced GitHub operations  
- `OPENAI_API_KEY` - Required for GPT-5 and O3 models
- `ANTHROPIC_API_KEY` - Required for future Claude runners
- `TRACING_BACKEND` - Optional: "file", "phoenix", or "mlflow"

## Future Enhancements Enabled

Once this migration is complete, these features become trivial to add:

### New Model Runners
- Claude Opus 4.1 runner (when available)
- Gemini 2.5 Pro runner (with patches from exp05)
- Any future model with proper configuration

### Enhanced Runners  
- Memory-aware runners with case retrieval (from exp05/memory/)
- Tool-enhanced runners with evidence search capabilities
- Multi-agent orchestration runners

### Advanced Features
- Automatic model selection based on issue complexity
- Cost optimization through model routing
- Performance monitoring and A/B testing framework
- Custom prompts per runner configuration

## Adapter Pattern Benefits

The adapter pattern approach ensures maintainability and clean separation:

### Future Update Process
Updating from exp05 becomes trivial:
```bash
# Simply copy latest utils (overwrites safely)
cp -r /Users/chris/src/context-experiments/trees/exp05/src/utils/* \
      /Users/chris/src/github-issue-analysis/github_issue_analysis/runners/utils/

# Adapters continue working without changes
```

### Clear Separation
- **utils/**: Unmodified exp05 code - updates automatically
- **adapters/**: Our customizations - clearly isolated and maintainable
- **runners/**: Import from adapters when behavior differs, from utils when identical

### No Modification Risk
- Zero chance of accidentally breaking exp05 compatibility
- All customizations visible and documented in adapters/
- Easy to audit what differs between the two projects

## Success Metrics

### Functional Requirements
- [ ] 100% feature parity with current implementation
- [ ] No breaking changes to existing workflows  
- [ ] All existing tests pass without modification
- [ ] CLI interface remains identical from user perspective

### Code Quality
- [ ] Passes all linting: `uv run ruff format . && uv run ruff check --fix --unsafe-fixes`  
- [ ] Passes type checking: `uv run mypy .`
- [ ] Passes all tests: `uv run pytest`
- [ ] Test coverage maintained or improved

### Architecture Improvements
- [ ] Agent configurations centralized in runner classes
- [ ] Easy to add new agents without modifying multiple files
- [ ] Built-in observability and tracing capabilities  
- [ ] Consistent error handling across all agents

## Notes

- This migration maintains 100% backward compatibility
- Users will see no functional changes in CLI behavior
- Internal architecture becomes much cleaner and maintainable
- **Adapter pattern ensures future exp05 updates work seamlessly**
- Foundation is laid for advanced features like memory and multi-agent workflows
- All current batch processing and recommendation management continues to work unchanged
- Utils remain unmodified - all customizations isolated in adapters/

## Risk Mitigation

- Comprehensive testing with `--dry-run` prevents accidental API calls
- Gradual migration allows rollback at any phase
- Runner registry allows easy switching between old and new implementations during transition
- All changes are additive - original code remains until migration is verified complete