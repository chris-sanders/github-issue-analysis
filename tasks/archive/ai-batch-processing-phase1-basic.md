# Task: AI Batch Processing - Phase 1: Basic OpenAI Batch Processing

**Status:** complete  
**Priority:** high  
**Estimated Time:** 3-4 hours  
**Dependencies:** None - works with existing JSON storage

## Description
Implement basic OpenAI Batch API integration for cost-effective AI processing. Works with existing JSON issue files without requiring DuckDB.

## Value Delivered
- **50% cost reduction** - OpenAI charges 50% less for batch API vs real-time API
- **High-volume processing** - Handle 100+ issues efficiently in one batch job
- **Asynchronous workflow** - Submit jobs and check back later (up to 24 hours)

## Files to Create
- `github_issue_analysis/ai/batch/batch_manager.py` - Core batch job management
- `github_issue_analysis/ai/batch/openai_provider.py` - OpenAI Batch API client
- `github_issue_analysis/ai/batch/models.py` - Batch job models
- `github_issue_analysis/cli/batch.py` - Batch processing CLI
- `tests/test_ai/test_batch.py` - Batch functionality tests

## Files to Modify
- `github_issue_analysis/cli/main.py` - Add batch commands
- `pyproject.toml` - Add any new dependencies

## New Operations
```bash
# Submit batch job using standard CLI patterns
uv run gh-analysis batch submit product-labeling --org myorg --repo myrepo

# Submit batch job for entire organization
uv run gh-analysis batch submit product-labeling --org myorg

# Submit specific issue to batch processing
uv run gh-analysis batch submit product-labeling --org myorg --repo myrepo --issue-number 123

# Check batch job status
uv run gh-analysis batch status <job-id>

# Collect completed batch results
uv run gh-analysis batch collect <job-id>

# List all batch jobs
uv run gh-analysis batch list
```

## New Functionality
- Process multiple issues at once instead of one-by-one
- 50% cheaper per API call (OpenAI's batch pricing)
- Submit job, go away, come back later for results
- Convert existing issue JSON files to OpenAI JSONL format
- Handle batch job lifecycle (submit → monitor → collect)

## Implementation Details

### CLI Command Design Principles

**Standard Flag Patterns (follow existing commands):**
- `--org, -o TEXT`: GitHub organization name (required for scoped operations)
- `--repo, -r TEXT`: GitHub repository name (optional, enables org-wide when omitted)  
- `--issue-number INTEGER`: Specific issue number for single-issue operations
- `--model TEXT`: AI model selection (e.g., 'openai:gpt-4o-mini')
- `--dry-run / --no-dry-run`: Preview mode without execution (default: false)

**Batch Command Implementation:**
```bash
# Follow same patterns as collect/process commands
uv run gh-analysis batch submit product-labeling [STANDARD_FLAGS]

# Where STANDARD_FLAGS match existing commands:
# --org myorg --repo myrepo          # Repository-specific  
# --org myorg                        # Organization-wide
# --org myorg --repo myrepo --issue-number 123  # Single issue
```

**Integration with Storage Manager:**
- Use existing `StorageManager.find_issues()` method with same filtering
- Maintain consistency with `collect` and `process` command behavior
- Leverage existing JSON file discovery and validation logic

### Batch Manager
```python
class BatchManager:
    """Manages AI batch processing jobs."""
    
    async def create_batch_job(self, 
                              processor_type: str,
                              org: str,
                              repo: Optional[str] = None,
                              issue_number: Optional[int] = None,
                              model_config: AIModelConfig) -> BatchJob:
        """Create batch job using standard filtering options."""
        
    async def check_job_status(self, job_id: str) -> BatchJobStatus:
        """Check status of batch job."""
        
    async def collect_results(self, job_id: str) -> Dict[str, Any]:
        """Download and process batch results."""
```

### OpenAI Provider
```python
class OpenAIBatchProvider:
    """OpenAI Batch API implementation."""
    
    def create_jsonl_file(self, issues: List[Dict], processor_config: Dict) -> Path:
        """Convert issues to OpenAI JSONL format with custom_id for tracking."""
        
    async def submit_batch(self, jsonl_file: Path) -> str:
        """Submit batch job to OpenAI."""
        
    async def get_batch_status(self, batch_id: str) -> Dict:
        """Get batch job status from OpenAI."""
        
    async def download_results(self, batch_id: str) -> List[Dict]:
        """Download completed batch results."""
```

### JSONL Format
```jsonl
{"custom_id": "org_repo_issue_123", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o-mini", "messages": [...]}}
{"custom_id": "org_repo_issue_124", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o-mini", "messages": [...]}}
```

## Validation Steps

### **Setup and Testing**
```bash
# 1. Ensure existing data is available
uv run gh-analysis status

# 2. Test batch submission with standard CLI patterns
uv run gh-analysis batch submit product-labeling --org test-org --repo test-repo

# 3. Check job status
uv run gh-analysis batch status <job-id>

# 4. Collect results when ready
uv run gh-analysis batch collect <job-id>

# 5. Verify results are in correct format
ls data/results/*_product-labeling.json
```

### **Error Handling**
```bash
# 6. Test with nonexistent organization/repository
uv run gh-analysis batch submit product-labeling --org nonexistent-org --repo nonexistent-repo

# 7. Test with no collected issues
uv run gh-analysis batch submit product-labeling --org empty-org --repo empty-repo
```

## Success Criteria
- [x] Create JSONL files from existing issue JSON files
- [x] Submit batch jobs to OpenAI Batch API  
- [x] Poll job status and handle completion
- [x] Download and parse batch results
- [x] Save results in existing JSON format (`data/results/`)
- [x] CLI commands for end-to-end batch workflow
- [x] Error handling for failed batch items
- [x] Cost tracking and comparison with real-time processing

## Agent Notes
[Document implementation approach, API integration challenges, and cost optimization strategies]