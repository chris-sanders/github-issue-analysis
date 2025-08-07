# Task: AI Simplification - Phase 3: Batch Processing

## Status
- **Created**: 2025-07-15
- **Status**: pending
- **Started**: [To be filled by agent]
- **Completed**: [To be filled by agent]
- **Depends On**: Phase 2 (CLI Integration)

## Overview
Update batch processing to use the new agent interface and provide full AI configuration options for batch jobs. This phase ensures batch processing benefits from the simplified architecture.

## Scope
- Update `cli/batch.py` to use new agent creation functions
- Add AI configuration options to batch submit command
- Ensure batch job serialization works with new agent config
- Update batch processing logic to use new interface
- Comprehensive batch processing testing

## Acceptance Criteria
- [ ] `batch submit` command uses new agent interface
- [ ] All AI configuration options available for batch jobs
- [ ] Batch job storage/retrieval works with new config format
- [ ] Batch processing execution uses new agents
- [ ] Backward compatibility with existing batch jobs
- [ ] Integration tests cover batch workflows
- [ ] Quality checks pass (black, ruff, mypy, pytest)

## Implementation Details

### Files to Modify
```
src/github_analysis/cli/batch.py       # Batch commands update
src/github_analysis/ai/batch.py        # Batch processing logic
tests/test_cli/test_batch.py            # Batch integration tests
```

### New Batch CLI Options
```python
@batch_app.command("submit")
async def submit_batch(
    processor: str,
    org: str = Option(..., help="GitHub organization"),
    repo: str = Option(None, help="Repository name"),
    
    # AI configuration options (same as CLI)
    model: str = Option("openai:gpt-4", help="AI model (provider:name)"),
    thinking_effort: str = Option(None, help="Thinking effort level"),
    temperature: float = Option(0.0, help="Model temperature"),
    retry_count: int = Option(2, help="Number of retries"),
    
    # Batch-specific options
    max_items: int = Option(None, help="Maximum items per batch"),
    dry_run: bool = Option(False, help="Preview batch job"),
):
```

### Batch Configuration Serialization
```python
# Ensure batch jobs store new agent config format
batch_config = {
    "processor": "product-labeling",
    "ai_config": {
        "model": model,
        "thinking_effort": thinking_effort,
        "temperature": temperature,
        "retry_count": retry_count,
    },
    "options": {
        "include_images": include_images,
        "max_items": max_items,
    }
}
```

### Testing Requirements
- Test batch job creation with new AI options
- Test batch job execution uses correct agent configuration
- Test batch status and collection commands
- Test backward compatibility with old batch job format
- Test batch processing with various model configurations
- Test error handling in batch processing

### Manual Verification Commands
```bash
# Submit batch job with new options
uv run gh-analysis batch submit product-labeling \
    --org test --repo test \
    --model anthropic:claude-3-haiku-20241022 \
    --thinking-effort medium \
    --temperature 0.3 \
    --retry-count 3 \
    --dry-run

# Check batch job management
uv run gh-analysis batch list
uv run gh-analysis batch status <job-id>

# Quality checks
uv run pytest tests/test_cli/test_batch.py -v
```

## Agent Instructions

### During Implementation
1. Document discoveries and challenges in "Implementation Notes" section below
2. Note any deviations from planned approach and why
3. Record testing insights and effective strategies
4. List all files modified with brief description

### Learning from Previous Phases
[Read Phase 1 & 2 notes for insights about agent creation, CLI patterns, etc.]

### Before Marking Complete
1. Update status and completion timestamp
2. Add recommendations for next phase agent (legacy cleanup)
3. Include working verification commands
4. Note any technical debt or follow-up items

### Handoff Requirements
- All tests passing
- Manual verification commands documented and working
- Clear notes on what the cleanup agent should know
- Any blockers or dependencies clearly stated

## Implementation Notes
[Agent fills this in during work]

### Discoveries
[What did you learn about batch processing, serialization, etc.?]

### Challenges Encountered
[What problems did you face and how did you solve them?]

### Code Changes Made
[List of files created/modified and why]

### Testing Insights
[What batch testing strategies worked? What to avoid?]

### Recommendations for Next Phase
[What should the legacy cleanup agent know?]

### Files Modified
[Detailed list with descriptions]

### Verification Commands That Worked
[Copy the exact commands that successfully verify this phase]

## Success Criteria
✅ Batch processing uses new agent interface
✅ All AI configuration options available in batch mode
✅ Batch job storage/retrieval works correctly
✅ Backward compatibility maintained
✅ Comprehensive test coverage
✅ End-to-end batch workflows verified