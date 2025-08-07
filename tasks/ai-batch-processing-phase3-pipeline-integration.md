# Task: AI Batch Processing - Phase 3: Pipeline Batch Mode Integration

**Status:** not started  
**Priority:** medium  
**Estimated Time:** 2-3 hours  
**Dependencies:** DuckDB Phase 2 (AI processing integration with pipeline)

## Description
Add batch execution mode to existing DuckDB Phase 2 pipeline commands. Allows all current pipeline workflows to run in batch mode instead of real-time.

## Prerequisites
- AI Batch Processing Phase 1 completed (basic batch processing)
- AI Batch Processing Phase 2 completed (DuckDB integration)  
- DuckDB Phase 2 completed (AI processing integration with pipeline)
- Existing `AIProcessingPipeline` class functional

## Value Delivered
- **Workflow consistency** - Use familiar pipeline commands with batch execution
- **Batch existing workflows** - Convert any current pipeline operation to batch mode
- **Seamless integration** - Same commands, just add `--batch-mode` flag

## Files to Modify
- `github_issue_analysis/ai/pipeline.py` - Add batch execution mode to existing pipeline
- `github_issue_analysis/ai/batch/batch_manager.py` - Pipeline integration
- `github_issue_analysis/cli/process_query.py` - Add --batch-mode option to existing commands

## New Operations
```bash
# Existing pipeline commands with --batch-mode added
uv run gh-analysis process-query missing product-labeling --batch-mode
uv run gh-analysis process-query reprocess product-labeling --threshold 0.7 --batch-mode
uv run gh-analysis process-query custom product-labeling "SELECT * FROM issues WHERE state='open'" --batch-mode

# Repository and filtering with batch mode
uv run gh-analysis process-query missing product-labeling --org replicated --repo kots --batch-mode

# Monitor batch jobs from pipeline
uv run gh-analysis process-query batch-status
```

## New Functionality
- All existing DuckDB Phase 2 pipeline commands can run in batch mode
- Same issue selection logic (missing analysis, low confidence, custom SQL) but executed as batch jobs
- Pipeline-managed batch job monitoring
- Automatic result storage in existing AI results tables

## Implementation Details

### Enhanced Pipeline Class
```python
class AIProcessingPipeline:
    """Enhanced pipeline with batch execution support."""
    
    def __init__(self, db: DatabaseManager = None, batch_manager: BatchManager = None):
        self.db = db or DatabaseManager()
        self.batch_manager = batch_manager or BatchManager(self.db)
        self.selected_issues: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self.batch_mode = False
        self.batch_jobs: List[str] = []
    
    def enable_batch_mode(self) -> 'AIProcessingPipeline':
        """Enable batch execution mode."""
        self.batch_mode = True
        return self
    
    async def process_with(self, processor_name: str, **kwargs) -> 'AIProcessingPipeline':
        """Process selected issues with AI (batch or real-time)."""
        if self.batch_mode:
            return await self._process_batch(processor_name, **kwargs)
        else:
            return await self._process_realtime(processor_name, **kwargs)
    
    async def _process_batch(self, processor_name: str, **kwargs) -> 'AIProcessingPipeline':
        """Process issues in batch mode."""
        if not self.selected_issues:
            console.print("[yellow]No issues selected for batch processing[/yellow]")
            return self
        
        # Convert selected issues to issue files list for batch manager
        issue_files = [Path(issue['file_path']) for issue in self.selected_issues]
        
        # Build AI configuration
        model_config = build_ai_config(**kwargs)
        
        # Create batch job
        batch_job = await self.batch_manager.create_batch_job(
            processor_name, issue_files, model_config
        )
        
        self.batch_jobs.append(batch_job.job_id)
        console.print(f"[green]✓ Created batch job: {batch_job.job_id}[/green]")
        console.print(f"[blue]Processing {len(self.selected_issues)} issues in batch mode[/blue]")
        
        return self
    
    def get_batch_status(self) -> Dict[str, Any]:
        """Get status of all batch jobs created by this pipeline."""
        if not self.batch_jobs:
            return {"batch_jobs": [], "total_jobs": 0}
        
        statuses = []
        for job_id in self.batch_jobs:
            try:
                status = asyncio.run(self.batch_manager.check_job_status(job_id))
                statuses.append({
                    "job_id": job_id,
                    "status": status.status,
                    "progress": f"{status.completed_count}/{status.total_count}"
                })
            except Exception as e:
                statuses.append({
                    "job_id": job_id,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "batch_jobs": statuses,
            "total_jobs": len(self.batch_jobs)
        }
```

### Enhanced Process Query Commands
```python
# Modify existing process_query.py commands

@app.command()
def missing(
    processor: str = typer.Argument(..., help="Processor name (e.g., 'product-labeling')"),
    limit: Optional[int] = typer.Option(None, help="Limit number of issues to process"),
    org: Optional[str] = typer.Option(None, help="Filter by organization"),
    repo: Optional[str] = typer.Option(None, help="Filter by repository"),
    state: Optional[str] = typer.Option("open", help="Filter by issue state"),
    batch_mode: bool = typer.Option(False, help="Execute in batch mode instead of real-time")
):
    """Process issues missing AI analysis."""
    pipeline = create_pipeline()
    
    if batch_mode:
        pipeline.enable_batch_mode()
    
    pipeline.where_missing_analysis(processor)
    
    if state:
        pipeline.where_state(state)
    
    if org and repo:
        pipeline.where_repo(org, repo)
    
    if limit:
        pipeline.limit(limit)
    
    # Show selection summary
    console.print(f"Will process {len(pipeline.selected_issues)} issues missing {processor} analysis")
    console.print(f"Mode: {'Batch' if batch_mode else 'Real-time'}")
    
    if not typer.confirm("Continue with processing?"):
        return
    
    # Process
    asyncio.run(pipeline.process_with(processor))
    
    # Show results
    if batch_mode:
        console.print("Batch job submitted. Use 'process-query batch-status' to monitor progress.")
    else:
        summary = pipeline.get_results_summary()
        if summary:
            console.print(f"✅ Processed {summary['total_processed']} issues")

@app.command()
def batch_status():
    """Show status of batch jobs created by pipeline commands."""
    # Implementation to show batch job status
    pass
```

### Batch Status Command
```python
@app.command()
def batch_status():
    """Show status of batch jobs created by pipeline commands."""
    try:
        db = DatabaseManager()
        batch_manager = BatchManager(db)
        
        # Get recent batch jobs
        recent_jobs = db.query_issues('''
            SELECT job_id, processor, status, issues_count, completed_count, 
                   created_at, completed_at
            FROM batch_jobs 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        
        if not recent_jobs:
            console.print("[yellow]No batch jobs found[/yellow]")
            return
        
        table = Table(title="Recent Batch Jobs")
        table.add_column("Job ID", style="cyan")
        table.add_column("Processor", style="white")
        table.add_column("Status", style="green")
        table.add_column("Progress", style="blue")
        table.add_column("Created", style="dim")
        
        for job in recent_jobs:
            progress = f"{job['completed_count'] or 0}/{job['issues_count']}"
            created = job['created_at'][:16] if job['created_at'] else ""
            
            table.add_row(
                job['job_id'][:12] + "...",
                job['processor'],
                job['status'],
                progress,
                created
            )
        
        console.print(table)
        
    except ImportError:
        console.print("[red]Database not available[/red]")
    except Exception as e:
        console.print(f"[red]Error checking batch status: {e}[/red]")
```

## Validation Steps

### **Setup and Prerequisites**
```bash
# 1. Ensure DuckDB Phase 2 is working
uv run gh-analysis process-query missing product-labeling --limit 1

# 2. Ensure batch processing Phase 1 & 2 are working
uv run gh-analysis batch history
```

### **Pipeline Batch Mode Testing**
```bash
# 3. Test missing analysis in batch mode
uv run gh-analysis process-query missing product-labeling --batch-mode --limit 5

# 4. Test reprocessing in batch mode
uv run gh-analysis process-query reprocess product-labeling --threshold 0.8 --batch-mode --limit 3

# 5. Test custom query in batch mode
uv run gh-analysis process-query custom product-labeling "SELECT * FROM issues WHERE state='closed'" --batch-mode --limit 2
```

### **Batch Monitoring**
```bash
# 6. Check batch job status
uv run gh-analysis process-query batch-status

# 7. Verify batch jobs are tracked in database
uv run gh-analysis query sql "SELECT job_id, processor, status FROM batch_jobs ORDER BY created_at DESC LIMIT 5"
```

### **Integration Testing**
```bash
# 8. Test same command in real-time vs batch mode
uv run gh-analysis process-query missing product-labeling --limit 2  # Real-time
uv run gh-analysis process-query missing product-labeling --limit 2 --batch-mode  # Batch

# 9. Verify results end up in same location
ls data/results/*_product-labeling.json
```

### **Error Handling**
```bash
# 10. Test batch mode with invalid processor
uv run gh-analysis process-query missing invalid-processor --batch-mode

# 11. Test batch status with no jobs
uv run gh-analysis process-query batch-status
```

## Success Criteria
- [ ] `--batch-mode` flag added to all existing process-query commands
- [ ] Pipeline filters work with batch processing
- [ ] Batch jobs integrate with existing AI results storage from DuckDB Phase 2
- [ ] Pipeline can monitor and report batch job status
- [ ] Seamless workflow between batch and real-time processing
- [ ] All existing pipeline functionality preserved in batch mode
- [ ] Batch job tracking integrated with DuckDB schema
- [ ] Error handling for batch mode failures
- [ ] Progress reporting for batch operations

## Agent Notes
[Document pipeline integration approach, batch/real-time workflow consistency, and result storage alignment]