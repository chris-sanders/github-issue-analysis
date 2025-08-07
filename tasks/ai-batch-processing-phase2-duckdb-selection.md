# Task: AI Batch Processing - Phase 2: DuckDB-Integrated Batch Selection

**Status:** not started  
**Priority:** medium  
**Estimated Time:** 2-3 hours  
**Dependencies:** DuckDB Phase 1 (database foundation + query interface)

## Description
Extend batch processing with SQL-powered issue selection using DuckDB. Adds intelligent filtering and batch job tracking to database.

## Prerequisites
- AI Batch Processing Phase 1 completed
- DuckDB Phase 1 integration completed (database foundation + query interface)
- Database with collected issues

## Value Delivered
- **SQL-powered selection** - Use database queries to intelligently select issues for batching
- **Batch job persistence** - Track all batch jobs in database with full history
- **Avoid duplicate processing** - Skip issues that already have AI analysis

## Files to Create
- `github_issue_analysis/ai/batch/sql_selector.py` - SQL-based issue selection
- Database schema additions for batch tracking

## Files to Modify
- `github_issue_analysis/ai/batch/batch_manager.py` - Add SQL selection support
- `github_issue_analysis/storage/schema.sql` - Add batch job tracking tables
- `github_issue_analysis/storage/database.py` - Add batch job persistence methods
- `github_issue_analysis/cli/batch.py` - Add SQL selection options

## New Operations
```bash
# Batch process using SQL selection
uv run gh-analysis batch submit product-labeling --sql "SELECT * FROM issues WHERE state='open'"

# Batch process issues missing analysis
uv run gh-analysis batch submit product-labeling --missing-analysis

# Batch process specific repository
uv run gh-analysis batch submit product-labeling --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO

# Show batch job history from database
uv run gh-analysis batch history

# Show batch job details
uv run gh-analysis batch details <job-id>
```

## New Functionality
- Use SQL queries to select which issues to batch process
- Store batch job information in database for tracking
- Query previous batch jobs and their status
- Automatically skip issues that already have AI analysis
- Integrate with existing DuckDB query capabilities

## Implementation Details

### Database Schema Extension
```sql
-- Add to existing schema.sql from DuckDB Phase 1
CREATE TABLE IF NOT EXISTS batch_jobs (
    id INTEGER PRIMARY KEY,
    job_id VARCHAR UNIQUE NOT NULL,
    provider VARCHAR NOT NULL DEFAULT 'openai',
    processor VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    status VARCHAR NOT NULL, -- 'submitted', 'processing', 'completed', 'failed'
    issues_count INTEGER NOT NULL,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    submitted_at TIMESTAMP,
    completed_at TIMESTAMP,
    cost_estimate DECIMAL(10,4),
    selection_query TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS batch_items (
    id INTEGER PRIMARY KEY,
    batch_job_id INTEGER NOT NULL,
    issue_id INTEGER NOT NULL,
    custom_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL, -- 'pending', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (batch_job_id) REFERENCES batch_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_batch_items_batch_job_id ON batch_items(batch_job_id);
CREATE INDEX IF NOT EXISTS idx_batch_items_status ON batch_items(status);
```

### SQL Selector
```python
class SQLBatchSelector:
    """SQL-based issue selection for batch processing."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def select_issues_missing_analysis(self, processor: str) -> List[Dict[str, Any]]:
        """Select issues missing specific AI analysis."""
        
    def select_issues_by_query(self, sql_query: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """Select issues using custom SQL query."""
        
    def select_issues_by_filters(self, org: str = None, repo: str = None, 
                                state: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """Select issues using common filters."""
```

### Enhanced Batch Manager
```python
class BatchManager:
    """Enhanced batch manager with SQL selection support."""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db
        self.selector = SQLBatchSelector(db) if db else None
    
    async def create_batch_from_sql(self, 
                                   processor_type: str,
                                   sql_query: str,
                                   model_config: AIModelConfig) -> BatchJob:
        """Create batch job from SQL query selection."""
        
    async def create_batch_missing_analysis(self, 
                                           processor_type: str,
                                           model_config: AIModelConfig) -> BatchJob:
        """Create batch job for issues missing analysis."""
        
    def get_batch_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get batch job history from database."""
        
    def get_batch_details(self, job_id: str) -> Dict[str, Any]:
        """Get detailed batch job information."""
```

## Validation Steps

### **Setup and Database Integration**
```bash
# 1. Ensure DuckDB Phase 1 is working
uv run gh-analysis status  # Should show database enabled

# 2. Verify database has issues
uv run gh-analysis query sql "SELECT COUNT(*) FROM issues"

# 3. Test SQL-based batch selection
uv run gh-analysis batch submit product-labeling --sql "SELECT * FROM issues WHERE state='open' LIMIT 5"
```

### **Batch Job Tracking**
```bash
# 4. Check batch job was stored in database
uv run gh-analysis batch history

# 5. Test missing analysis selection
uv run gh-analysis batch submit product-labeling --missing-analysis

# 6. Verify batch job details
uv run gh-analysis batch details <job-id>
```

### **Database Queries**
```bash
# 7. Query batch jobs directly
uv run gh-analysis query sql "SELECT * FROM batch_jobs ORDER BY created_at DESC"

# 8. Check batch items tracking
uv run gh-analysis query sql "SELECT COUNT(*) FROM batch_items"
```

### **Integration Testing**
```bash
# 9. Test avoiding duplicate processing
# Run same batch twice, verify second run skips already processed issues

# 10. Test error handling with invalid SQL
uv run gh-analysis batch submit product-labeling --sql "INVALID SQL"
```

## Success Criteria
- [ ] SQL-based issue selection for batch processing
- [ ] Database persistence of batch jobs and status
- [ ] Query existing batch history and details
- [ ] Integration with DuckDB Phase 1 query interface
- [ ] Avoid duplicate processing through database checks
- [ ] Batch job and item tracking in database
- [ ] Enhanced CLI with SQL selection options
- [ ] Cost tracking and estimation
- [ ] Error handling for invalid queries

## Agent Notes
[Document SQL query optimization, database integration challenges, and batch tracking approach]