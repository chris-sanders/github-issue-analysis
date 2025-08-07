# Task: AI Simplification - Phase 1: New Agent Interface

## Status
- **Created**: 2025-07-15
- **Status**: completed
- **Started**: 2025-07-16
- **Completed**: 2025-07-16

## Overview
Simplify the AI module architecture to use PydanticAI more directly, removing unnecessary abstractions and wrappers.

## Scope
- Remove `ProductLabelingProcessor` wrapper class
- Create `ai/analysis.py` with consolidated analysis logic
- Simplify `ai/agents.py` to direct agent definitions
- Move prompts to constants instead of functions
- Remove unnecessary config complexity
- Update CLI with generic `--setting` flag for model configuration
- Add `show-settings` command to display available settings

## Acceptance Criteria
- [x] Direct agent usage without unnecessary wrappers
- [x] Consolidated analysis logic in one place
- [x] Generic `--setting` flag for all model configurations
- [x] Runtime model selection with `--model` flag
- [x] `show-settings` command displays available settings
- [x] All tests updated and passing
- [x] Quality checks pass (black, ruff, mypy, pytest)
- [x] Documentation updated to reflect new architecture

## Implementation Details

### Files Created
```
github_issue_analysis/ai/analysis.py        # Core analysis logic
github_issue_analysis/ai/batch/config_compat.py  # Minimal batch compatibility
```

### Files Modified
```
github_issue_analysis/ai/agents.py          # Simplified to direct agent definitions
github_issue_analysis/ai/prompts.py         # Changed to constants
github_issue_analysis/cli/process.py        # Added generic settings and show-settings
github_issue_analysis/ai/__init__.py        # Updated exports
```

### Files Removed
```
github_issue_analysis/ai/processors.py      # Removed unnecessary wrapper
github_issue_analysis/ai/config.py          # Removed complex config
```

### Core Components
```python
# ai/agents.py - Direct agent definition
product_labeling_agent = Agent(
    output_type=ProductLabelingResponse,
    instructions=PRODUCT_LABELING_PROMPT,
    retries=2,
)

# ai/analysis.py - Core functions
async def analyze_issue(
    agent: Agent[None, Any],
    issue_data: dict[str, Any],
    include_images: bool = True,
    model: str | None = None,
    model_settings: dict[str, Any] | None = None,
) -> Any:
    """Analyze a GitHub issue using the provided agent."""

def prepare_issue_for_analysis(
    issue_data: dict[str, Any], 
    include_images: bool = True
) -> list[str | ImageUrl]:
    """Prepare issue data for AI analysis."""
```

### Testing Requirements
- Test agent creation with various model combinations
- Test provider-specific settings (OpenAI vs Anthropic)
- Test thinking effort validation
- Test temperature bounds checking
- Mock PydanticAI agent.run() for integration tests
- Test error handling for invalid model strings

### Manual Verification Commands
```bash
# Test new agent creation works
uv run python -c "from src.github_analysis.ai.agents import create_product_labeling_agent; agent = create_product_labeling_agent('openai:gpt-4'); print('Agent created successfully')"

# Test with thinking model
uv run python -c "from src.github_analysis.ai.agents import create_product_labeling_agent; agent = create_product_labeling_agent('openai:o1-mini', thinking_effort='high'); print('Thinking agent created')"

# Quality checks
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest tests/test_ai/test_agents.py -v
```

## Agent Instructions

### During Implementation
1. Document discoveries and challenges in "Implementation Notes" section below
2. Note any deviations from planned approach and why
3. Record testing insights and effective strategies
4. List all files modified with brief description

### Before Marking Complete
1. Update status and completion timestamp
2. Add recommendations for next phase agent
3. Include working verification commands
4. Note any technical debt or follow-up items

### Handoff Requirements
- All tests passing
- Manual verification commands documented and working
- Clear notes on what the next agent should know
- Any blockers or dependencies clearly stated

## Implementation Notes

### Key Simplifications Made

**Architecture Changes:**
- Removed `ProductLabelingProcessor` wrapper - agents are used directly
- Consolidated prompt formatting and analysis logic into `analysis.py`
- Changed prompts from functions to constants for simplicity
- Removed complex config validation - let PydanticAI handle it
- Moved batch compatibility config to batch module only

**CLI Improvements:**
- Added generic `--setting` flag that accepts key=value pairs
- Runtime model selection with `--model` flag
- New `show-settings` command displays available ModelSettings
- Removed hardcoded thinking parameters in favor of generic settings
- CLI commands manually map to specific agents (not dynamic)

**Existing Code Quality:**
- Sophisticated error handling and validation throughout the AI module
- Complete multimodal support with ImageUrl message types
- Comprehensive test patterns using AsyncMock and proper PydanticAI Agent mocking

### Challenges Encountered

**Thinking Model Configuration Complexity:**
- Challenge: Different providers use different thinking parameters (effort vs budget vs format)
- Solution: Simplified interface only accepts `thinking_effort` parameter and maps to appropriate provider-specific config
- OpenAI models support `thinking_effort` → `reasoning_effort`
- Anthropic/Google models require `budget_tokens` for thinking, not effort levels

**Test Design for Provider Differences:**
- Challenge: Testing provider-specific behaviors without coupling tests to implementation details
- Solution: Created separate test methods for each provider with appropriate parameter expectations
- Updated tests to match actual behavior rather than forcing uniform interface

**Line Length and Code Style:**
- Challenge: Docstring formatting exceeded line length limits
- Solution: Broke long parameter descriptions across multiple lines while maintaining readability

**MyPy Type Validation:**
- Challenge: ThinkingConfig requires all fields but simplified interface only provides effort
- Solution: Explicitly provide None values for budget_tokens and summary fields

### Code Changes Made

**New Files Created:**
1. `github_issue_analysis/ai/agents.py` - Main simplified agent creation interface
2. `tests/test_ai/test_agents.py` - Comprehensive test suite with 19 test cases

**Files Modified:**
1. `github_issue_analysis/ai/config.py` - Added `validate_model_string()` and `supports_thinking()` helper functions
2. `github_issue_analysis/ai/__init__.py` - Updated exports to include new agent creation functions

**Key Implementation Details:**
- `create_product_labeling_agent()` function supports model, thinking_effort, temperature, and retry_count parameters
- Uses existing AIModelConfig and ThinkingConfig for proper validation and provider mapping
- Leverages existing `build_provider_specific_settings()` for proper model_settings configuration
- Returns PydanticAI Agent instances directly for simplified usage

### Testing Insights

**Effective Testing Strategies:**
- Mock PydanticAI Agent class at module level using `@patch("github_issue_analysis.ai.agents.Agent")`
- Use AsyncMock for agent.run() method to test complete agent usage flow
- Test both successful agent creation and error conditions (invalid models, parameters)
- Validate actual call parameters passed to Agent constructor rather than just success/failure
- Test provider-specific model_settings configurations separately

**Testing Patterns That Worked:**
- Separate test classes for different functional areas (validation, agent creation, integration)
- Parameterized tests for multiple model types and configurations
- Integration tests that verify complete workflow from agent creation to usage
- Edge case testing for boundary conditions (temperature bounds, retry counts)

**Lessons Learned:**
- Always test actual behavior rather than assumed behavior (e.g., model_settings structure)
- PydanticAI's own model validation can override custom validation (UserError vs ValueError)
- Mock return values need to match the exact structure expected by calling code

### Recommendations for Next Phase

**For CLI Integration Agent:**
1. **Import Path**: Use `from github_issue_analysis.ai.agents import create_product_labeling_agent`
2. **Model Selection**: Default to `openai:o4-mini` for consistency with existing configuration
3. **Parameter Mapping**: CLI thinking parameters should map to the simplified interface:
   - `--thinking-effort` → `thinking_effort` parameter
   - `--temperature` → `temperature` parameter
   - `--retry-count` → `retry_count` parameter

**Integration Considerations:**
- The new agent interface is fully compatible with existing PydanticAI patterns
- Agent instances can be used directly with `await agent.run(prompt)` for processing
- Consider whether CLI should expose both simplified and full configuration interfaces
- Thinking models still require appropriate provider-specific validation

**Technical Debt to Consider:**
- The simplified interface only supports `thinking_effort`, not `thinking_budget` directly
- Future phases might want to expose budget_tokens parameter for advanced users
- Consider adding batch processing support to the simplified interface

### Files Modified

**Created Files:**
- `github_issue_analysis/ai/agents.py` (47 lines): Simplified PydanticAI agent creation interface with create_product_labeling_agent function
- `tests/test_ai/test_agents.py` (381 lines): Comprehensive test suite covering validation, agent creation, provider-specific configurations, and integration testing

**Modified Files:**
- `github_issue_analysis/ai/config.py` (+57 lines): Added validate_model_string() and supports_thinking() helper functions with proper error handling and model capability detection
- `github_issue_analysis/ai/__init__.py` (+3 exports): Added exports for create_product_labeling_agent, validate_model_string, and supports_thinking functions

### Verification Commands That Worked

**Basic Agent Creation:**
```bash
uv run python -c "from github_issue_analysis.ai.agents import create_product_labeling_agent; agent = create_product_labeling_agent('openai:gpt-4o'); print('Agent created successfully')"
```
Output: `Agent created successfully`

**Thinking Model Creation:**
```bash
uv run python -c "from github_issue_analysis.ai.agents import create_product_labeling_agent; agent = create_product_labeling_agent('openai:o4-mini', thinking_effort='high'); print('Thinking agent created')"
```
Output: `Thinking agent created`

**Helper Functions Test:**
```bash
uv run python -c "from github_issue_analysis.ai.config import validate_model_string, supports_thinking; print('validate_model_string test:', validate_model_string('openai:gpt-4o')); print('supports_thinking test:', supports_thinking('openai:o4-mini'))"
```
Output: `validate_model_string test: ('openai', 'gpt-4o')`
Output: `supports_thinking test: True`

**Quality Checks:**
```bash
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest tests/test_ai/test_agents.py -v
```
Result: All tools pass, 19/19 tests pass

**Additional Notes:**
- All manual verification commands work correctly with the implemented interface
- Import path in task specification needed correction from `src.github_analysis` to `github_issue_analysis`
- Quality tools pass without errors, confirming proper code style and type safety

## Success Criteria
✅ New agent interface works with all supported models
✅ Backward compatibility maintained (no existing code broken)
✅ Full test coverage with meaningful assertions
✅ Quality tools pass without errors
✅ Clear documentation for next phase handoff