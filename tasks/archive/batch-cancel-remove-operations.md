# Task: Batch Job Cancel and Remove Operations

**Status:** complete  
**Priority:** medium  
**Estimated Time:** 2-3 hours  
**Dependencies:** Existing batch processing system (ai-batch-processing-phase1-basic.md)

## Description
Add capabilities to cancel active batch jobs and remove batch job records from the system. Currently users can only submit, check status, collect results, and list batch jobs, but cannot cancel mistaken submissions or clean up old job records.

## Problem Statement
Users need the ability to:
1. **Cancel active batch jobs** - If they submit a job by mistake or with wrong parameters, they should be able to cancel it before it completes to avoid unnecessary API costs
2. **Remove batch job records** - Clean up local job metadata files to maintain a tidy system and remove failed/unwanted job records

## Value Delivered
- **Cost control** - Cancel jobs before they incur API charges
- **Mistake recovery** - Undo accidental submissions with wrong parameters
- **System hygiene** - Remove old/failed jobs to keep the system clean
- **User control** - Full lifecycle management of batch jobs

## Current System Analysis
- **Batch jobs stored in**: `data/batch/jobs/{job_id}.json`
- **Job states**: pending, validating, in_progress, finalizing, completed, failed, cancelled
- **OpenAI API**: Supports batch cancellation via `DELETE /v1/batches/{batch_id}`
- **Current commands**: submit, status, collect, list

## Acceptance Criteria

### Cancel Functionality
- [ ] Add `cancel` command to CLI: `uv run gh-analysis batch cancel <job-id>`
- [ ] Implement `cancel_batch()` method in OpenAI provider to call DELETE API
- [ ] Implement `cancel_job()` method in BatchManager 
- [ ] Handle different job states appropriately:
  - ✅ Can cancel: pending, validating, in_progress, finalizing
  - ❌ Cannot cancel: completed, failed, already cancelled
- [ ] Update local job status to "cancelled" when successful
- [ ] Provide clear feedback about cancellation status
- [ ] Handle API errors gracefully (job already completed, etc.)

### Remove Functionality  
- [ ] Add `remove` command to CLI: `uv run gh-analysis batch remove <job-id>`
- [ ] Implement `remove_job()` method in BatchManager
- [ ] Remove job metadata file from `data/batch/jobs/`
- [ ] Optionally remove associated input/output files
- [ ] Confirm before removing (unless --force flag used)
- [ ] Handle cases where job doesn't exist
- [ ] Provide clear feedback about what was removed

### Safety Features
- [ ] Confirmation prompts before destructive operations
- [ ] `--force` flag to skip confirmations
- [ ] Clear error messages for invalid operations

### CLI Integration
- [ ] Add both commands to batch sub-command group
- [ ] Consistent help text and error handling
- [ ] Rich console output with appropriate colors
- [ ] Integration with existing batch command patterns

### Testing
- [ ] Unit tests for cancel/remove functionality
- [ ] Integration tests with mocked OpenAI API
- [ ] Error handling tests for edge cases
- [ ] CLI command tests

## Implementation Plan

### Files to Modify
1. **`github_issue_analysis/ai/batch/openai_provider.py`**
   - Add `cancel_batch(batch_id: str)` method
   - Handle OpenAI API cancellation endpoint

2. **`github_issue_analysis/ai/batch/batch_manager.py`**
   - Add `cancel_job(job_id: str)` method
   - Add `remove_job(job_id: str, force: bool = False)` method
   - Status validation logic

3. **`github_issue_analysis/cli/batch.py`**
   - Add `cancel` command
   - Add `remove` command
   - Rich output formatting

4. **`docs/api-reference.md`**
   - Document new commands and options

### New CLI Commands

```bash
# Cancel an active batch job
uv run gh-analysis batch cancel <job-id>

# Remove a batch job record (with confirmation)
uv run gh-analysis batch remove <job-id>

# Remove a batch job record (skip confirmation)
uv run gh-analysis batch remove <job-id> --force
```

### OpenAI Provider Method
```python
async def cancel_batch(self, batch_id: str) -> dict[str, Any]:
    """Cancel a batch job via OpenAI API.
    
    Args:
        batch_id: OpenAI batch ID to cancel
        
    Returns:
        Updated batch status information
        
    Raises:
        Exception: If cancellation fails
    """
```

### BatchManager Methods
```python
async def cancel_job(self, job_id: str) -> BatchJob:
    """Cancel a batch job.
    
    Args:
        job_id: Local batch job ID
        
    Returns:
        Updated batch job with cancelled status
        
    Raises:
        ValueError: If job cannot be cancelled
    """

def remove_job(self, job_id: str, force: bool = False) -> bool:
    """Remove a batch job record.
    
    Args:
        job_id: Local batch job ID
        force: Skip confirmation prompt
        
    Returns:
        True if job was removed, False if cancelled by user
        
    Raises:
        ValueError: If job doesn't exist
    """
```

## Edge Cases and Error Handling

### Cancellation
- **Job already completed**: Show friendly message, don't error
- **Job already cancelled**: Show current status, don't error  
- **Network error**: Retry with exponential backoff
- **Invalid job ID**: Clear error message
- **OpenAI API error**: Pass through API error details

### Removal
- **Job doesn't exist**: Clear error message
- **Job is active**: Warn user, require confirmation or --force
- **File permissions**: Handle gracefully
- **Partial removal**: Warn about what couldn't be removed

## Validation Steps

```bash
# Setup: Create a test batch job
uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER --dry-run

# Test cancellation
uv run gh-analysis batch cancel <job-id>
uv run gh-analysis batch status <job-id>  # Should show cancelled

# Test removal with confirmation
uv run gh-analysis batch remove <job-id>
# Should prompt for confirmation

# Test removal with force
uv run gh-analysis batch remove <job-id> --force
# Should remove without confirmation


# Test error cases
uv run gh-analysis batch cancel nonexistent-job
uv run gh-analysis batch remove nonexistent-job

# Run all tests
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

## Agent Notes
**Key Implementation Details:**
- OpenAI Batch API DELETE endpoint: `DELETE /v1/batches/{batch_id}`
- Job state validation is critical - only cancel jobs in cancelable states
- File cleanup should be optional but recommended
- Rich console output should match existing batch command patterns
- Error handling should be consistent with existing batch operations
- Consider adding batch removal of multiple jobs in future enhancement

**Integration Points:**
- Reuse existing BatchManager patterns and error handling
- Follow existing CLI command structure and help text format
- Maintain consistency with existing OpenAI provider async patterns
- Use existing Rich console styling and color schemes

**Testing Strategy:**
- Mock OpenAI API responses for unit tests
- Test both success and failure scenarios
- Verify file system operations work correctly
- Ensure CLI commands integrate properly with existing batch commands