# Task: Add Interactive Mode to Troubleshoot Processor

**Status:** complete

**Description:**
Add an interactive mode (`--interactive`, `-i`) to the troubleshoot processor that enables users to continue conversations with the AI agent after initial analysis, allowing them to ask follow-up questions about the issue.

## Acceptance Criteria

- [ ] Add `--interactive` and `-i` flags to the troubleshoot command
- [ ] After initial analysis completes, present an interactive prompt for follow-up questions
- [ ] Maintain conversation context using PydanticAI's `message_history` feature
- [ ] Support multi-line input using backslash continuation
- [ ] Provide clear exit mechanism (type "exit" or Ctrl+C)
- [ ] Display helpful prompts and instructions when entering interactive mode
- [ ] Preserve original analysis results in JSON output regardless of interactive session
- [ ] Handle edge cases gracefully (empty input, connection errors, etc.)
- [ ] Add functional tests for interactive mode
- [ ] Update CLI help text

## CRITICAL: Parallel Development Strategy

**USE THE TASK TOOL WITH MULTIPLE PARALLEL SUB-AGENTS TO SPEED DEVELOPMENT**

When implementing this feature, launch parallel sub-agents for independent components:

```python
# Example of parallel sub-agent usage:
# Launch these SIMULTANEOUSLY, not sequentially:

Task 1: "Update CLI command" - Add interactive flag to troubleshoot command
Task 2: "Create interactive module" - Build interactive.py with session handler  
Task 3: "Create response model" - Add InteractiveTroubleshootingResponse to models.py
Task 4: "Write functional tests" - Create test_troubleshooting_interactive.py
```

These tasks can run in PARALLEL because they don't depend on each other initially. After all sub-agents complete, integrate their work and test the full flow.

## Implementation Design

### 1. CLI Command Enhancement
File: `github_issue_analysis/cli/process.py`

Add parameter to `troubleshoot()` function:
```python
interactive: bool = typer.Option(
    False,
    "--interactive",
    "-i", 
    help="Enter interactive mode after analysis for follow-up questions",
    rich_help_panel="Processing Options",
)
```

Pass through to `_run_troubleshoot()` and after saving results, call interactive session if flag is set.

### 2. Interactive Session Module
Create: `github_issue_analysis/ai/interactive.py`

```python
from rich.prompt import Prompt
from rich.console import Console
from pydantic_ai import Agent
from typing import Any

console = Console()

async def run_interactive_session(
    agent: Agent[None, Any],
    initial_result: RunResult,
    issue_data: dict[str, Any],
    include_images: bool = True,
) -> None:
    """Run interactive troubleshooting session after initial analysis."""
    
    # Display interactive mode header
    console.print("\n[bold blue]── Interactive Mode ──────────────────────────────────[/bold blue]")
    console.print("Ask follow-up questions about this issue.")
    console.print("• Type 'exit' or press Ctrl+C to end")
    console.print("• Use '\\' at line end for multi-line input")
    console.print("[bold blue]" + "─" * 55 + "[/bold blue]\n")
    
    message_history = initial_result.new_messages()
    
    while True:
        try:
            # Get user input with multi-line support
            user_input = get_multiline_input()
            
            if user_input.lower() == 'exit':
                console.print("Session ended. Thank you!")
                break
                
            if not user_input.strip():
                continue
                
            # Run with context
            result = await agent.run(
                user_input,
                message_history=message_history
            )
            
            # Display response
            console.print(f"\n{result.output}\n")
            
            # Update message history for next iteration
            message_history = result.new_messages()
            
        except KeyboardInterrupt:
            console.print("\nSession ended. Thank you!")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("[yellow]You can continue asking questions or type 'exit' to end.[/yellow]")

def get_multiline_input() -> str:
    """Get input with backslash continuation support."""
    lines = []
    prompt = ">>> "
    
    while True:
        line = Prompt.ask(prompt, default="")
        
        if line.endswith("\\"):
            lines.append(line[:-1])  # Remove backslash
            prompt = "    "  # Indent continuation
        else:
            lines.append(line)
            break
    
    return "\n".join(lines)
```

### 3. Response Model
File: `github_issue_analysis/ai/models.py`

Add new model for interactive responses:
```python
class InteractiveTroubleshootingResponse(BaseModel):
    """Response model for interactive follow-up questions."""
    answer: str = Field(description="Direct answer to the user's question")
    additional_findings: list[str] = Field(
        default_factory=list,
        description="Any new findings discovered while answering"
    )
    references_used: list[str] = Field(
        default_factory=list,
        description="References to initial analysis or new tools used"
    )
```

### 4. Integration Point
File: `github_issue_analysis/cli/process.py`

In `_run_troubleshoot()`, after saving results:
```python
# Save results (existing code)
with open(result_file, "w") as f:
    json.dump(result_data, f, indent=2)
console.print(f"\n[green]✓ Results saved to {result_file.name}[/green]")

# Start interactive session if requested
if interactive:
    from ..ai.interactive import run_interactive_session
    await run_interactive_session(
        troubleshoot_agent,
        result,  # The RunResult from initial analysis
        processed_issue_data,
        include_images=include_images
    )
```

### 5. Agent Updates
The existing troubleshooting agents already support conversation via PydanticAI's message_history. No changes needed to agent creation, just use them in conversational mode.

## Functional Testing Strategy

Create: `tests/test_troubleshooting_interactive.py`

Focus on REAL BEHAVIOR, minimal mocking:

```python
"""Functional tests for interactive troubleshoot mode."""

import asyncio
from unittest.mock import patch, AsyncMock
from github_issue_analysis.ai.interactive import get_multiline_input, run_interactive_session

class TestMultilineInput:
    """Test multi-line input handling."""
    
    @patch('github_issue_analysis.ai.interactive.Prompt.ask')
    def test_single_line_input(self, mock_ask):
        """Test normal single-line input."""
        mock_ask.return_value = "What is the error?"
        result = get_multiline_input()
        assert result == "What is the error?"
        assert mock_ask.call_count == 1
    
    @patch('github_issue_analysis.ai.interactive.Prompt.ask')
    def test_multiline_with_backslash(self, mock_ask):
        """Test backslash continuation."""
        mock_ask.side_effect = [
            "First line\\",
            "Second line\\", 
            "Third line"
        ]
        result = get_multiline_input()
        assert result == "First line\nSecond line\nThird line"
        assert mock_ask.call_count == 3

class TestInteractiveSession:
    """Test interactive session flow."""
    
    @patch('github_issue_analysis.ai.interactive.Prompt.ask')
    async def test_exit_command(self, mock_ask):
        """Test that 'exit' ends the session."""
        mock_ask.side_effect = ["What's wrong?", "exit"]
        
        # Create minimal mock agent that tracks calls
        mock_agent = AsyncMock()
        mock_agent.run.return_value = AsyncMock(
            output="Here's the answer",
            new_messages=lambda: []
        )
        
        mock_result = AsyncMock(new_messages=lambda: [])
        
        await run_interactive_session(
            mock_agent,
            mock_result,
            {"issue": {"title": "Test"}},
            include_images=False
        )
        
        # Verify one question was processed before exit
        assert mock_agent.run.call_count == 1
        
    @patch('github_issue_analysis.ai.interactive.Prompt.ask')
    async def test_keyboard_interrupt(self, mock_ask):
        """Test Ctrl+C handling."""
        mock_ask.side_effect = KeyboardInterrupt()
        
        mock_agent = AsyncMock()
        mock_result = AsyncMock(new_messages=lambda: [])
        
        # Should exit gracefully
        await run_interactive_session(
            mock_agent,
            mock_result,
            {"issue": {"title": "Test"}},
            include_images=False
        )
        
        # No agent calls should have been made
        assert mock_agent.run.call_count == 0
```

### Integration Test
Create a REAL functional test that uses actual agents:

```python
async def test_full_interactive_flow():
    """Test complete flow with real components (requires API keys)."""
    import os
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Requires OPENAI_API_KEY")
    
    # Use a simple test agent
    from pydantic_ai import Agent
    agent = Agent(
        model="openai:gpt-4o-mini",
        instructions="You are a helpful assistant answering questions about a GitHub issue."
    )
    
    # Simulate initial analysis
    initial = await agent.run("Initial analysis of test issue")
    
    # Test interactive session with mock input
    with patch('github_issue_analysis.ai.interactive.Prompt.ask') as mock_ask:
        mock_ask.side_effect = [
            "What's the root cause?",
            "exit"
        ]
        
        await run_interactive_session(
            agent,
            initial,
            {"issue": {"title": "Test Issue"}},
            include_images=False
        )
    
    # Verify session completed without errors
    assert mock_ask.call_count == 2
```

## Manual Testing Commands

```bash
# Set up environment
export SBCTL_TOKEN=test_token
export OPENAI_API_KEY=your_key

# Test with a real issue
uv run gh-analysis process troubleshoot \
    --org microsoft --repo vscode --issue-number 100000 \
    --interactive --agent o3_medium

# Test multi-line input:
# Type: "Here is my error:\[ENTER]
#       [paste stack trace]\[ENTER]
#       What does this mean?"

# Test exit mechanisms:
# 1. Type "exit"
# 2. Press Ctrl+C
```

## Validation Steps

1. **Basic Flow**
   ```bash
   # Run troubleshoot with interactive mode
   uv run gh-analysis process troubleshoot \
       --org microsoft --repo vscode --issue-number 100000 -i
   
   # Verify:
   # - Initial analysis completes and saves
   # - Interactive prompt appears with instructions
   # - Questions get contextual responses
   # - Exit works properly
   ```

2. **Error Recovery**
   - Disconnect network during interactive session
   - Verify error message appears but session continues
   - User can still exit cleanly

3. **Quality Checks**
   ```bash
   uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
   ```

## Implementation Notes

- Each troubleshoot run is independent - no session persistence between runs
- If the GitHub issue gets new comments during interactive mode, user must exit and re-run
- Initial analysis always completes and saves before entering interactive mode
- The same MCP tools remain available during interactive session

## Agent Notes

[Agent should document implementation progress, decisions, and test results here]

### Implementation Checklist
- [x] Update CLI command with interactive flag
- [x] Create interactive.py module with session handler
- [x] Implement conversation loop with proper context management  
- [x] Add InteractiveTroubleshootingResponse model
- [x] Handle multi-line input with backslash continuation
- [x] Add functional tests
- [x] Manual testing with real issues
- [x] Ensure all quality checks pass

### Implementation Summary

**Completed:** January 2025

Successfully implemented interactive mode for troubleshooting processor with all acceptance criteria met:

✅ **CLI Enhancement:** Added `--interactive` flag to troubleshoot command  
✅ **Interactive Session:** Created `interactive.py` module with conversation loop  
✅ **Context Management:** Maintains conversation context using PydanticAI's `message_history`  
✅ **Multi-line Input:** Supports backslash continuation for complex inputs  
✅ **Exit Mechanisms:** Both "exit" command and Ctrl+C work gracefully  
✅ **Error Handling:** Session continues after API errors with helpful messages  
✅ **Response Model:** Added `InteractiveTroubleshootingResponse` for structured responses  
✅ **Comprehensive Tests:** 14 test cases covering all functionality including real API integration  
✅ **Quality Assurance:** All tests pass, code formatted with ruff, type-checked with mypy  

**Key Features:**
- Interactive prompt appears after initial analysis completes
- Message history preserved across questions for contextual conversations  
- Rich console formatting with clear instructions and headers
- Robust error handling that doesn't crash the session
- Original analysis results always saved regardless of interactive session

**Usage:**
```bash
uv run gh-analysis process troubleshoot --org myorg --repo myrepo --issue-number 123 --interactive
```