# Task: Automatic Batch Splitting and Multi-Batch Importing for Large AI Processing

**Status:** planning  
**Priority:** high  
**Estimated Time:** 3-4 hours  
**Dependencies:** AI Batch Processing Phase 1 (completed - basic batch processing)

## Description
Implement automatic batch splitting for large issue collections using a fixed 30-issue batch size, with multi-batch job coordination and unified result importing. Enables processing of 200-400+ issues efficiently through simple splitting and group management.

## Prerequisites
- AI Batch Processing Phase 1 completed (basic OpenAI batch processing functional)
- Understanding that 30 issues per batch provides safe margin under token limits
- Large organizations need automatic splitting for 200-400+ issues

## Value Delivered
- **Scale beyond current limits** - Process 200-400+ issues without manual intervention
- **Simple and reliable** - Fixed 30-issue batches with safety margin under token limits
- **Unified user experience** - Multi-batch operations appear as single logical jobs
- **Zero complexity** - No token estimation or content analysis needed
- **Enterprise-ready** - Handle large-scale organizational issue processing

## Files to Create
- `github_issue_analysis/ai/batch/batch_splitter.py` - Simple batch splitting logic (30 issues per batch)
- `github_issue_analysis/ai/batch/batch_group_manager.py` - Multi-batch coordination
- `github_issue_analysis/ai/batch/group_models.py` - Batch group data models
- `tests/test_ai/test_batch_splitting.py` - Comprehensive batch splitting tests

## Files to Modify
- `github_issue_analysis/ai/batch/batch_manager.py` - Add splitting integration and group support
- `github_issue_analysis/ai/batch/models.py` - Add group-related fields to BatchJob model
- `github_issue_analysis/cli/batch.py` - Enhanced CLI with splitting feedback and group operations

## New Operations
```bash
# Existing commands work seamlessly with automatic splitting
uv run gh-analysis batch submit product-labeling --org myorg  # Auto-splits if >30 issues

# Enhanced status shows group progress  
uv run gh-analysis batch status <group-id>  # Shows all batches in group
uv run gh-analysis batch status <job-id>    # Individual batch status

# Group-level operations
uv run gh-analysis batch group-collect <group-id>  # Collect all results
uv run gh-analysis batch list --groups            # Show batch groups

# Preview splitting
uv run gh-analysis batch submit product-labeling --org myorg --dry-run  # Preview split plan

# Advanced group management
uv run gh-analysis batch group-cancel <group-id>
uv run gh-analysis batch group-retry <group-id> --failed-only
```

## New Functionality
- **Automatic splitting** - Split into 30-issue batches when collection >30 issues
- **Batch group coordination** - Track multiple related batches as single operation
- **Unified result collection** - Seamless aggregation of multi-batch results
- **Enhanced progress tracking** - Group-level status with individual batch details
- **Simple retry mechanisms** - Recover from partial failures efficiently
- **Transparent operation** - Users see single logical job regardless of splitting

## Implementation Details

### 1. Simple Batch Splitter
```python
class BatchSplitter:
    """Simple batch splitting using fixed 30-issue chunks."""
    
    BATCH_SIZE = 30  # Safe margin under token limits
    
    def split_issues(self, issues: List[Dict]) -> List[List[Dict]]:
        """Split issues into 30-issue chunks."""
        batches = []
        for i in range(0, len(issues), self.BATCH_SIZE):
            batch = issues[i:i + self.BATCH_SIZE]
            batches.append(batch)
        return batches
    
    def create_split_plan(self, issues: List[Dict]) -> Dict:
        """Create simple splitting plan."""
        batches = self.split_issues(issues)
        
        plan = {
            "total_issues": len(issues),
            "total_batches": len(batches),
            "split_required": len(batches) > 1,
            "batch_size": self.BATCH_SIZE,
            "batches": []
        }
        
        for i, batch in enumerate(batches):
            plan["batches"].append({
                "batch_number": i + 1,
                "issue_count": len(batch)
            })
        
        return plan
```

### 2. Batch Group Manager
```python
class BatchGroupManager:
    """Manages multi-batch operations as logical groups."""
    
    def __init__(self, batch_manager: BatchManager, storage_manager: StorageManager):
        self.batch_manager = batch_manager
        self.storage = storage_manager
        self.splitter = BatchSplitter()
    
    async def create_batch_group(self, 
                               processor_type: str,
                               issues: List[Dict],
                               model_config: AIModelConfig) -> BatchGroup:
        """Create batch group with automatic splitting."""
        
        # Create splitting plan
        split_plan = self.splitter.create_split_plan(issues)
        
        if not split_plan["split_required"]:
            # Single batch - delegate to existing batch manager
            batch_job = await self.batch_manager.create_batch_job(
                processor_type, issues, model_config
            )
            return BatchGroup(
                group_id=batch_job.job_id,
                child_job_ids=[batch_job.job_id],
                total_issues=len(issues),
                completion_status="submitted",
                is_split_job=False
            )
        
        # Multi-batch group
        group_id = f"group_{uuid.uuid4().hex[:12]}"
        child_jobs = []
        
        for i, batch_issues in enumerate(self.splitter.split_issues(issues)):
            batch_job = await self.batch_manager.create_batch_job(
                processor_type, batch_issues, model_config
            )
            # Add group metadata to batch job
            batch_job.parent_group_id = group_id
            batch_job.batch_sequence = i + 1
            batch_job.total_batches_in_group = len(split_plan["batches"])
            child_jobs.append(batch_job.job_id)
        
        batch_group = BatchGroup(
            group_id=group_id,
            child_job_ids=child_jobs,
            total_issues=len(issues),
            completion_status="submitted",
            is_split_job=True,
            split_plan=split_plan
        )
        
        # Save group metadata
        self._save_group_metadata(batch_group)
        return batch_group
    
    async def check_group_status(self, group_id: str) -> BatchGroupStatus:
        """Check status of all batches in group."""
        group = self._load_group_metadata(group_id)
        job_statuses = []
        
        for job_id in group.child_job_ids:
            status = await self.batch_manager.check_job_status(job_id)
            job_statuses.append(status)
        
        # Aggregate status
        completed_jobs = [s for s in job_statuses if s.status == "completed"]
        failed_jobs = [s for s in job_statuses if s.status == "failed"]
        
        return BatchGroupStatus(
            group_id=group_id,
            total_batches=len(group.child_job_ids),
            completed_batches=len(completed_jobs),
            failed_batches=len(failed_jobs),
            total_issues=group.total_issues,
            completed_issues=sum(s.completed_count for s in completed_jobs),
            status=self._determine_group_status(job_statuses)
        )
    
    async def collect_group_results(self, group_id: str) -> Dict:
        """Collect and aggregate results from all batches in group."""
        group = self._load_group_metadata(group_id)
        all_results = []
        
        for job_id in group.child_job_ids:
            try:
                results = await self.batch_manager.collect_results(job_id)
                all_results.extend(results.get('results', []))
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to collect results from {job_id}: {e}[/yellow]")
        
        return {
            "group_id": group_id,
            "total_results": len(all_results),
            "results": all_results,
            "collection_timestamp": datetime.utcnow().isoformat()
        }
```

### 3. Enhanced Models
```python
class BatchGroup(BaseModel):
    """Batch group for multi-batch operations."""
    group_id: str
    child_job_ids: List[str]
    total_issues: int
    completion_status: str
    is_split_job: bool = False
    split_plan: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BatchJob(BaseModel):
    """Enhanced batch job with group support."""
    # Existing fields...
    parent_group_id: Optional[str] = None
    batch_sequence: Optional[int] = None
    total_batches_in_group: Optional[int] = None

class BatchGroupStatus(BaseModel):
    """Group status aggregation."""
    group_id: str
    total_batches: int
    completed_batches: int
    failed_batches: int
    total_issues: int
    completed_issues: int
    status: str  # "pending", "processing", "completed", "partial_failure", "failed"
```

### 4. Enhanced CLI Integration
```python
# Enhanced submit command with splitting feedback
@app.command()
def submit(
    processor: str,
    org: str = typer.Option(..., help="GitHub organization"),
    repo: Optional[str] = typer.Option(None, help="Repository name"),
    issue_number: Optional[int] = typer.Option(None, help="Specific issue number"),
    model: str = typer.Option("openai:gpt-4o-mini", help="AI model"),
    dry_run: bool = typer.Option(False, help="Preview splitting without submission")
):
    """Submit batch processing with automatic splitting."""
    
    # Find issues using existing logic
    storage = StorageManager()
    issues = storage.find_issues(org=org, repo=repo, issue_number=issue_number)
    
    if not issues:
        console.print("[red]No issues found matching criteria[/red]")
        return
    
    # Create splitting plan
    splitter = BatchSplitter()
    split_plan = splitter.create_split_plan(issues)
    
    # Display splitting plan
    if split_plan["split_required"]:
        console.print(f"[yellow]Large batch detected: {split_plan['total_issues']} issues[/yellow]")
        console.print(f"[blue]Will split into {split_plan['total_batches']} batches of 30 issues each[/blue]")
        
        table = Table(title="Batch Splitting Plan")
        table.add_column("Batch", style="cyan")
        table.add_column("Issues", style="white")
        
        for batch in split_plan["batches"]:
            table.add_row(
                str(batch["batch_number"]),
                str(batch["issue_count"])
            )
        
        console.print(table)
    else:
        console.print(f"[green]Single batch: {len(issues)} issues[/green]")
    
    if dry_run:
        console.print("[blue]Dry run complete - no jobs submitted[/blue]")
        return
    
    # Confirm submission
    if split_plan["split_required"] and not typer.confirm(
        f"Submit {split_plan['total_batches']} batch jobs?"
    ):
        return
    
    # Submit batch group
    group_manager = BatchGroupManager(BatchManager(), storage)
    model_config = build_ai_config(model=model)
    
    batch_group = await group_manager.create_batch_group(
        processor, issues, model_config
    )
    
    if batch_group.is_split_job:
        console.print(f"[green]✓ Created batch group: {batch_group.group_id}[/green]")
        console.print(f"[blue]Submitted {len(batch_group.child_job_ids)} related batches[/blue]")
        console.print(f"[dim]Use 'batch status {batch_group.group_id}' to monitor progress[/dim]")
    else:
        console.print(f"[green]✓ Created batch job: {batch_group.group_id}[/green]")
```

## Validation Steps

### **Setup and Splitting Logic**
```bash
# 1. Test splitting preview for small collections
# Ask user to provide test organization for validation
# Example: uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --dry-run --limit 10

# 2. Test splitting preview for large collections
# Ask user to provide test organization for validation  
# Example: uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --dry-run --limit 100
```

### **Automatic Splitting**
```bash
# 3. Test small batch (no splitting required)
# Ask user to provide test organization for validation
# Example: uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --limit 20

# 4. Test large batch (auto-splitting into 30-issue chunks)
# Ask user to provide test organization for validation
# Example: uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --limit 80

# 5. Verify group creation and tracking
uv run gh-analysis batch list --groups
```

### **Multi-Batch Management**
```bash
# 6. Monitor group progress
uv run gh-analysis batch status <group-id>

# 7. Test individual batch status within group
uv run gh-analysis batch status <individual-job-id>

# 8. Collect group results when complete
uv run gh-analysis batch group-collect <group-id>
```

### **Integration and Edge Cases**
```bash
# 9. Test edge case: exactly 30 issues (no splitting)
uv run gh-analysis batch submit product-labeling --org test-org --limit 30

# 10. Test edge case: 31 issues (splits into 30 + 1)
uv run gh-analysis batch submit product-labeling --org test-org --limit 31

# 11. Test error handling
# Submit batch, cancel one job in group, verify partial collection works

# 12. Verify result consistency
# Ensure split batches produce same results as single batch for same issues
```

### **Backward Compatibility**
```bash
# 13. Verify existing small batch workflows unchanged
uv run gh-analysis batch submit product-labeling --org test-org --repo small-repo

# 14. Verify existing CLI commands work with groups
uv run gh-analysis batch list
uv run gh-analysis batch status <job-id>
uv run gh-analysis batch collect <job-id>
```

## Success Criteria
- [ ] Simple 30-issue batch splitting for collections >30 issues
- [ ] Multi-batch group coordination with unified status tracking
- [ ] Seamless result aggregation from split batches
- [ ] Enhanced CLI with splitting preview and group operations
- [ ] Backward compatibility - existing workflows unchanged
- [ ] Zero-complexity splitting - no token estimation needed
- [ ] Error handling for partial group failures
- [ ] Group-level operations (status, collect, cancel)
- [ ] Transparent user experience - splitting is automatic and invisible
- [ ] Comprehensive test coverage for all splitting scenarios

## Agent Notes
[Document token estimation accuracy, splitting strategy effectiveness, group coordination challenges, and result aggregation approach. Include any OpenAI API limitations discovered during implementation.]