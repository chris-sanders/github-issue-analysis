# Task: Fix "Cannot instantiate typing.Union" Error in Troubleshoot Command

**Status:** ready

**Description:**
Fix the "Cannot instantiate typing.Union" error that occurs when running the troubleshoot command. The error appears during AI analysis execution, likely in the response parsing phase where PydanticAI attempts to deserialize the AI response into the TroubleshootingResponse model. This error affects both version 0.3.0 and 0.3.1, indicating it's not related to recent dependency updates but rather a deeper compatibility issue between Python 3.13, Pydantic, and PydanticAI libraries.

## New Functionality
When this task is complete, users will be able to:
- Successfully run troubleshoot analysis commands without encountering Union instantiation errors
- Process GitHub issues using all available troubleshooting agents (o3_medium, o3_high, opus_41)
- Get structured troubleshooting responses with confidence scores, tool usage reports, and technical analysis
- Use interactive mode for follow-up questions after initial analysis

## Acceptance Criteria

- [ ] **Root Cause Identification**: Identify the exact location and cause of the Union instantiation error in the codebase
- [ ] **Error Reproduction**: Create a reliable unit test that reproduces the Union instantiation error without requiring external API calls
- [ ] **Union Type Analysis**: Examine all Union type usage patterns in the codebase, particularly in Pydantic models and PydanticAI integration
- [ ] **Fix Implementation**: Implement a solution that resolves the Union instantiation issue while maintaining type safety
- [ ] **Backward Compatibility**: Ensure the fix doesn't break existing functionality for product-labeling or other AI analysis commands
- [ ] **Model Validation**: Verify that TroubleshootingResponse, TechnicalAnalysis, and InteractiveTroubleshootingResponse models work correctly with the fix
- [ ] **Integration Testing**: Test the fix with actual troubleshooting agent execution using mock responses
- [ ] **Documentation**: Update any relevant documentation if the fix requires changes to type annotations or model definitions

## Implementation Plan - Parallel Sub-Agent Execution

**CRITICAL: Use multiple Task tool calls simultaneously to maximize development speed. Each sub-task below should be executed in parallel by different agents.**

### Immediate Parallel Launch (All sub-agents start simultaneously)

Launch these 6 sub-agents in parallel using the Task tool in a single message:

1. **Sub-Agent A: Error Reproduction & Stack Trace Analysis**
   - Create functional test suite in `tests/test_union_instantiation.py` using REAL data structures
   - Use actual GitHub issue data from existing collected issues (no API calls needed)
   - Implement detailed logging and exception handling in troubleshooting code paths
   - Test REAL TroubleshootingResponse instantiation with various data combinations
   - Test actual PydanticAI agent creation and configuration with real models
   - **Deliverable**: Failing functional test using real data + exact root cause location

2. **Sub-Agent B: Union Type & Pydantic Model Audit**  
   - Scan entire codebase for Union type usage patterns (grep, analysis)
   - Review all Pydantic model definitions for v2 compatibility issues
   - Check TroubleshootingResponse, TechnicalAnalysis, InteractiveTroubleshootingResponse models
   - Analyze field validators, custom validation logic, and model configurations
   - **Deliverable**: Comprehensive audit report of Union usage + recommended fixes

3. **Sub-Agent C: Dependency Compatibility Investigation**
   - Investigate Python 3.13, Pydantic v2, PydanticAI version compatibility
   - Compare troubleshoot-mcp-server versions between 1.10.0 and 1.11.0 for breaking changes
   - Test different combinations of type annotation approaches
   - Research known issues with Union types in the current dependency stack
   - **Deliverable**: Compatibility matrix + specific version constraints if needed

4. **Sub-Agent D: PydanticAI Integration Deep Dive**
   - Review how agents are configured with output_type parameters
   - Examine agent response parsing and deserialization code paths
   - Test REAL troubleshooting agent creation with actual environment setup
   - Create functional tests using real TroubleshootingResponse objects with edge case data
   - Test actual agent.run() calls with controlled inputs (fake API keys to trigger specific error paths)
   - **Deliverable**: Fixed PydanticAI integration + functional testing framework

5. **Sub-Agent E: Union Type Refactoring Implementation**
   - Replace legacy Union[X, Y] with modern X | Y syntax throughout codebase
   - Update Optional[X] to X | None syntax where applicable
   - Modernize type imports and remove unnecessary typing imports
   - Test model serialization/deserialization with updated annotations
   - **Deliverable**: Refactored type annotations + validation tests

6. **Sub-Agent F: Functional Integration Testing Framework**
   - Create comprehensive functional tests for all troubleshooting agents using REAL components
   - Test actual CLI command execution with controlled error scenarios (invalid API keys, network issues)
   - Test real command-line interface with various parameter combinations and real issue data
   - Create end-to-end functional validation using actual file I/O, real Pydantic models, and real agent configurations
   - Use existing collected GitHub issues from data/issues/ directory for realistic test scenarios
   - **Deliverable**: Complete functional test suite + end-to-end validation commands

### Parallel Development Benefits

- **6x Speed Improvement**: Instead of 7-9 hours sequential, target 1.5-2 hours total with parallel execution
- **Comprehensive Coverage**: Each agent focuses on one specific aspect, ensuring thorough investigation
- **Risk Mitigation**: Multiple approaches increase likelihood of finding the root cause quickly
- **Quality Assurance**: Parallel testing and validation catches edge cases early

### Coordination Protocol

1. **Launch Phase** (First 15 minutes): All 6 agents start simultaneously with clear, non-overlapping deliverables
2. **Progress Check** (30 minutes): Quick sync to ensure no overlap and identify any blockers
3. **Integration Phase** (45-60 minutes): Combine findings and implement unified solution
4. **Validation Phase** (75-90 minutes): Run all tests and validate complete fix

### Sub-Agent Communication

Each sub-agent should:
- Update their progress in their respective section of this task file
- Share critical findings immediately (don't wait for completion)
- Flag any blockers or dependencies on other sub-agents
- Provide specific commands for testing their deliverables

## Technical Implementation Details

### Key Files to Modify
- `github_issue_analysis/ai/models.py`: Update Union type annotations and field definitions
- `github_issue_analysis/ai/analysis.py`: Add error handling and debugging for Union parsing
- `github_issue_analysis/ai/troubleshooting_agents.py`: Review agent configuration for type compatibility
- `tests/test_union_instantiation.py`: New comprehensive test suite

### Type Annotation Updates
Replace legacy Union syntax:
```python
# Before (potentially problematic)
from typing import Union, Optional
field: Union[str, None] = None
optional_field: Optional[List[str]] = None

# After (modern Python 3.10+ syntax)
field: str | None = None
optional_field: list[str] | None = None
```

### Pydantic Model Configuration
Ensure models have proper configuration for v2 compatibility:
```python
class TroubleshootingResponse(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        extra='forbid',
        use_enum_values=True
    )
```

### Error Handling Enhancement
Add specific Union error catching:
```python
try:
    result = await agent.run(message_parts, **kwargs)
    return result.output
except (TypeError, ValueError) as e:
    if "Union" in str(e) or "typing" in str(e):
        logger.error(f"Union type instantiation error: {e}")
        raise UnionInstantiationError(f"Failed to parse AI response: {e}")
    raise
```

## Testing Strategy

### Functional Unit Tests (Using Real Data)
```bash
# Test Pydantic model instantiation with REAL troubleshooting response data
uv run pytest tests/test_union_instantiation.py::test_real_troubleshooting_response_instantiation -v

# Test model validation with REAL GitHub issue data from data/issues/
uv run pytest tests/test_union_instantiation.py::test_model_validation_with_real_issues -v

# Test Union type parsing with actual TroubleshootingResponse objects
uv run pytest tests/test_union_instantiation.py::test_union_type_compatibility_real_data -v
```

### Functional Integration Tests (Using Real Components)
```bash
# Test troubleshooting agent creation with REAL agent configurations
uv run pytest tests/test_union_instantiation.py::test_real_agent_creation_all_types -v

# Test the full troubleshoot command execution with controlled error scenarios
uv run pytest tests/test_union_instantiation.py::test_troubleshoot_command_real_execution -v

# Test actual CLI interface with real issue files from data/issues/ directory
uv run pytest tests/test_union_instantiation.py::test_cli_integration_with_real_issues -v
```

### Manual Validation Commands
```bash
# Test agent creation (should not fail)
uv run python -c "
from github_issue_analysis.ai.troubleshooting_agents import create_troubleshooting_agent
import os; os.environ['SBCTL_TOKEN']='test'; os.environ['OPENAI_API_KEY']='test'
agent = create_troubleshooting_agent('o3_medium', 'test', None)
print('Agent creation successful')
"

# Test model instantiation with realistic data
uv run python -c "
from github_issue_analysis.ai.models import TroubleshootingResponse, TechnicalAnalysis
analysis = TechnicalAnalysis(root_cause='test', key_findings=['test'], remediation='test', explanation='test')
response = TroubleshootingResponse(analysis=analysis, confidence_score=0.5, processing_time_seconds=1.0)
print('Model instantiation successful')
"

# Test the troubleshoot command (no --dry-run needed as this command doesn't write to GitHub)
uv run gh-analysis process troubleshoot --org test --repo test --issue-number 1
```

### Parallel Agent Launch Command

**Execute this single command to launch all 6 sub-agents simultaneously:**

```bash
# The main agent should make 6 Task tool calls in one message:
# Task 1: "Error reproduction analysis" -> Sub-Agent A
# Task 2: "Union type codebase audit" -> Sub-Agent B  
# Task 3: "Dependency compatibility research" -> Sub-Agent C
# Task 4: "PydanticAI integration investigation" -> Sub-Agent D
# Task 5: "Union type refactoring implementation" -> Sub-Agent E
# Task 6: "Integration testing framework creation" -> Sub-Agent F
```

## Quality Assurance

### Pre-commit Quality Checks
```bash
# Required before any commit - all must pass
uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

### Specific Type Checking
```bash
# Ensure no Union-related type errors
uv run mypy github_issue_analysis/ai/models.py --strict

# Check troubleshooting module type consistency
uv run mypy github_issue_analysis/ai/troubleshooting_agents.py --strict

# Verify analysis module type safety
uv run mypy github_issue_analysis/ai/analysis.py --strict
```

## Dependencies and Considerations

### External Dependencies
- Maintain compatibility with current PydanticAI version (avoid downgrading)
- Ensure Python 3.13 compatibility is preserved
- Keep troubleshoot-mcp-server integration functional
- Verify OpenAI and Anthropic API client compatibility

### Backward Compatibility
- All existing product-labeling functionality must continue to work
- Batch processing commands should remain unaffected
- Label update functionality must work with any model changes
- CLI interface should remain unchanged

### Performance Impact
- Model instantiation should not be significantly slower
- Memory usage should not increase noticeably
- Type checking overhead should be minimal

## Error Handling Requirements

### Graceful Degradation
- If Union parsing fails, provide clear error messages explaining the issue
- Suggest potential solutions (API key validation, dependency check)
- Maintain error logging for debugging purposes
- Continue processing other issues in batch operations

### User Experience
- Error messages should be actionable and user-friendly
- Include information about which troubleshooting agent was being used
- Provide steps to report issues if errors persist
- Maintain dry-run functionality to test without API calls

## Functional Testing Requirements

### Real Data Sources
- **Use existing collected issues**: Leverage files in `data/issues/` directory for realistic test scenarios
- **Real Pydantic model objects**: Instantiate actual TroubleshootingResponse, TechnicalAnalysis objects with varied data
- **Actual CLI execution**: Test real command-line interface with controlled error scenarios
- **Real file I/O**: Test actual JSON reading/writing with real GitHub issue data structures

### Functional Test Examples

```bash
# Test with REAL issue data (no API calls needed)
uv run python -c "
import json
from pathlib import Path
from github_issue_analysis.ai.models import TroubleshootingResponse, TechnicalAnalysis

# Load actual issue data if available
data_dir = Path('data/issues')
if data_dir.exists():
    issue_files = list(data_dir.glob('*.json'))
    if issue_files:
        with open(issue_files[0]) as f:
            real_issue_data = json.load(f)
        print(f'Testing with real issue: {real_issue_data[\"issue\"][\"number\"]}')

# Test real model instantiation
analysis = TechnicalAnalysis(
    root_cause='Database connection timeout',
    key_findings=['Connection pool exhausted', 'High query latency'], 
    remediation='Increase connection pool size and add query timeout',
    explanation='The issue is caused by...'
)
response = TroubleshootingResponse(
    analysis=analysis,
    confidence_score=0.85,
    tools_used=['docker', 'kubectl'], 
    processing_time_seconds=45.2
)
print('Real model instantiation successful')
"

# Test REAL agent creation and configuration
uv run python -c "
import os
from github_issue_analysis.ai.troubleshooting_agents import create_troubleshooting_agent

# Set up real environment (invalid keys to test error handling)
os.environ['SBCTL_TOKEN'] = 'test_token_invalid'
os.environ['OPENAI_API_KEY'] = 'sk-test_key_invalid'

# Create real agent objects
for agent_name in ['o3_medium', 'o3_high', 'opus_41']:
    try:
        if agent_name == 'opus_41':
            os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-test_invalid'
        agent = create_troubleshooting_agent(agent_name, 'test_token_invalid', None)
        print(f'Real {agent_name} agent created successfully')
    except Exception as e:
        print(f'{agent_name} creation error (expected): {type(e).__name__}')
"

# Test REAL CLI execution with controlled errors
uv run gh-analysis process troubleshoot --org nonexistent --repo nonexistent --issue-number 999
```

### Mock-Free Testing Strategy
- **No mocking of Pydantic models**: Use real model instantiation with varied data
- **No mocking of PydanticAI agents**: Create actual agent objects with invalid API keys to test error paths
- **No mocking of file I/O**: Use real JSON files from data/issues/ directory
- **No mocking of CLI**: Execute actual command-line interface with controlled inputs
- **Minimal mocking**: Only mock external API calls (OpenAI, Anthropic) when necessary for specific error path testing

### Realistic Error Scenarios
Test these functional scenarios without mocking:
1. **Invalid API keys**: Real agent creation with fake keys to trigger authentication errors
2. **Malformed issue data**: Real JSON files with intentionally problematic data structures
3. **Type annotation edge cases**: Real Union types with complex nested structures
4. **CLI parameter validation**: Real command execution with invalid parameter combinations
5. **File system errors**: Real file operations with permission issues or missing directories

## Agent Notes

**Functional Testing Priority:**
Focus on using REAL components and data structures throughout testing. Only use mocking when absolutely necessary for external API calls. This ensures tests validate actual system behavior rather than test doubles.

**Key Investigation Points:**
1. Use existing GitHub issue data from data/issues/ directory for realistic testing
2. Test actual TroubleshootingResponse model instantiation with varied real data combinations
3. Create real PydanticAI agents with controlled error scenarios (invalid API keys)
4. Test real CLI execution paths with actual parameter validation

**Validation Requirements:**
The fix is complete when:
1. All functional tests pass using real data and components
2. Real model instantiation works with complex Union type scenarios
3. End-to-end functional validation passes with actual CLI execution
4. **Final User Test Case**: Agent must ask the user for a specific test case to validate the fix
5. **Iterative Improvement**: If the user-provided test case fails, improve the fix rather than reporting failure

**Final Validation Protocol:**
- After implementing the fix and passing all internal tests, ask the user: "Please provide a specific troubleshoot command to test the fix"
- Execute the user-provided test case exactly as specified
- If it fails, analyze the failure and improve the fix implementation
- Repeat until the user-provided test case passes successfully
- Do NOT document or save the user-provided test case in any files or git commits