# Fix Thinking Flags Confusion and Remove o1-mini References

## Problem Statement

Agents testing the CLI are getting confused about how to activate thinking with o4-mini and keep trying to switch to the deprecated o1-mini model because of misleading help messages and error messages. The system needs to be updated to:

1. Remove all references to deprecated o1-mini
2. Fix error messages that suggest wrong thinking flags
3. Clarify which models support thinking capabilities
4. Update help text to be more accurate about o4-mini thinking support

## Current Issues Found

### 1. Deprecated o1-mini in Error Messages
- **File**: `github_issue_analysis/ai/capabilities.py:153-154`
- **Issue**: Error message suggests deprecated `o1-mini` when thinking flags are used incorrectly
- **Current Text**: `"OpenAI o1 models: o1-mini, o1-preview"`

### 2. o1-mini in Capability Examples  
- **File**: `github_issue_analysis/ai/capabilities.py:111,115`
- **Issue**: Functions return o1-mini as example model for thinking capabilities
- **Impact**: Agents see o1-mini suggested in error messages

### 3. Confusing CLI Help Text
- **Files**: `cli/process.py:34-35`, `cli/batch.py:34-35`
- **Issue**: Help text says thinking-effort is "for OpenAI o1 models" but doesn't mention o4-mini
- **Impact**: Agents don't realize o4-mini supports thinking-effort flag

### 4. Test Files Using Deprecated Model
- **Files**: Multiple test files in `tests/` directory
- **Issue**: Tests still use o1-mini for thinking capability validation
- **Impact**: Inconsistent examples for developers

### 5. Documentation Gaps
- **File**: `docs/api-reference.md`
- **Issue**: Shows o4-mini examples but doesn't explain thinking capabilities
- **Impact**: Incomplete guidance for users

## Required Implementation

### Phase 1: Dynamic Capability Detection

1. **Enhance Capability Introspection**:
   - Extend existing capability detection to dynamically identify thinking support
   - Remove hardcoded model lists from error messages and help text
   - Use runtime model inspection to determine compatibility

2. **Smart Error Messages**:
   - When incompatible thinking flags are used, analyze the current model selection
   - Provide contextual guidance showing which flags ARE compatible with the current model
   - Show alternative models that support the requested thinking capability
   - Never suggest specific models - instead clarify what's compatible

3. **Fix Test Files**:
   - Replace all o1-mini references in test files with current supported models
   - Update test expectations to validate dynamic capability detection
   - Ensure tests verify correct thinking behavior and error messaging

### Phase 2: Context-Aware Help and Validation

1. **Dynamic CLI Help Text**:
   - Remove hardcoded model references from help text
   - Make help text generic: `"Reasoning effort level for compatible thinking models"`
   - Add runtime model compatibility checking during command execution

2. **Intelligent Validation**:
   - When users specify model + thinking flags, validate compatibility dynamically
   - Show contextual error messages based on the specific model chosen
   - Distinguish between thinking-effort (OpenAI) and thinking-budget (Anthropic/Google) based on model provider detection

### Phase 3: Documentation Updates

1. **API Reference**:
   - `docs/api-reference.md`: Add section explaining dynamic thinking capability detection
   - Include examples showing how to check model compatibility
   - Document the validation process and error message patterns

2. **CLAUDE.md Updates**:
   - Add examples of thinking flag usage with capability checking
   - Explain how the system determines model compatibility at runtime

## Acceptance Criteria

### Functional Requirements
- [x] All hardcoded model references removed from error messages and help text
- [x] Dynamic capability detection determines thinking support at runtime
- [x] Error messages show compatible flags for the current model selection
- [x] Batch processing errors provide contextual guidance based on model capabilities
- [x] All tests validate dynamic capability detection instead of hardcoded models

### User Experience Requirements  
- [x] Users get contextual feedback about flag compatibility with their chosen model
- [x] Error messages provide actionable guidance without suggesting specific models
- [x] Clear distinction between thinking-effort vs thinking-budget based on provider detection
- [x] Documentation explains the dynamic capability system rather than static model lists

### Technical Requirements
- [x] All tests pass after model updates
- [x] Type checking passes (mypy)
- [x] Code formatting passes (ruff, black)
- [x] No breaking changes to existing functionality

## Implementation Guidelines

### Dynamic Capability System
The new approach should work like this:

**Example 1 - Incompatible Flags:**
```
$ uv run gh-analysis process --model openai:gpt-4o --thinking-effort high
Error: Model 'gpt-4o' does not support thinking-effort flag.
Compatible flags for this model: [none - standard processing]
For thinking capabilities, try a model that supports reasoning.
```

**Example 2 - Compatible Usage:**
```
$ uv run gh-analysis process --model openai:o4-mini --thinking-effort medium
✓ Using thinking-capable model with reasoning effort: medium
```

**Example 3 - Provider Mismatch:**
```
$ uv run gh-analysis process --model anthropic:claude-3-haiku --thinking-effort high  
Error: Model 'claude-3-haiku' does not support OpenAI thinking-effort flag.
Compatible flags for this model: --thinking-budget (Anthropic reasoning control)
```

### Code Quality
- Follow existing error message patterns and formatting
- Maintain consistent terminology across all files
- Use clear, actionable language in help text
- Add type hints where missing

### Testing Strategy
- Update existing tests to use o4-mini instead of o1-mini
- Add new tests for error message accuracy
- Test CLI help text rendering
- Validate thinking flag validation logic

### Files to Modify
**Core Changes:**
- `github_issue_analysis/ai/capabilities.py`
- `github_issue_analysis/ai/batch/openai_provider.py` 
- `github_issue_analysis/cli/process.py`
- `github_issue_analysis/cli/batch.py`

**Test Updates:**
- `tests/test_cli/test_thinking_validation.py`
- `tests/test_ai/test_thinking_models.py`
- `tests/test_ai/test_processors.py`
- Any other test files referencing o1-mini

**Documentation:**
- `docs/api-reference.md`
- `CLAUDE.md` (if needed)

## Verification Steps

1. **Run CLI Commands**:
   ```bash
   uv run gh-analysis process --help
   uv run gh-analysis batch --help
   ```
   Verify help text uses generic language about compatible models

2. **Test Error Messages**:
   ```bash
   uv run gh-analysis process product-labeling --model openai:gpt-4o --thinking-effort high
   ```
   Should explain that gpt-4o doesn't support thinking-effort and show compatible flags

3. **Run Quality Checks**:
   ```bash
   uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
   ```

4. **Test Actual Thinking**:
   ```bash
   # Test with a thinking-capable model (system should detect compatibility)
   # Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis process product-labeling --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number 71 --model openai:o4-mini --thinking-effort medium
   ```

## Success Metrics

- No agent confusion about thinking flags in testing
- Contextual error messages guide users to compatible flag combinations for their chosen model
- All documentation and help text uses dynamic capability detection instead of hardcoded model lists
- Zero hardcoded model references in user-facing text - all compatibility determined at runtime

## Status

- [x] **Task Status**: Complete
- [ ] **Assignee**: TBD
- [ ] **Priority**: High (affects agent testing experience)
- [ ] **Estimated Effort**: 2-3 hours