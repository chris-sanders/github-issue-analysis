# Task: DuckDB Integration - Phase 2: AI Processing Integration

**Status:** not started  
**Priority:** high  
**Estimated Time:** 3-4 hours  
**Prerequisites:** Phase 1 completed, AI processing available

## Description
Integrate DuckDB queries with AI processing pipeline for intelligent issue selection, result tracking, and processing analytics. Builds directly on Phase 1 database foundation.

## Prerequisites
- Phase 1 DuckDB integration completed (database foundation + query interface)
- AI processing system available (product labeling or other processors)
- Existing AI results stored in `data/results/`

## Files to Create
- `github_issue_analysis/ai/pipeline.py` - AI processing pipeline with SQL selection
- `github_issue_analysis/cli/process_query.py` - Query-based processing commands
- `tests/test_ai/test_pipeline.py` - Pipeline integration tests

## Files to Modify
- `github_issue_analysis/storage/database.py` - Add AI results storage methods
- `github_issue_analysis/storage/schema.sql` - Add AI results tables
- `github_issue_analysis/storage/queries.py` - Extend label_summary alias with AI data
- `github_issue_analysis/cli/main.py` - Add process-query commands

## Implementation Details

### **Query Alias Extensions**

**Extended `label_summary` Alias:**
Phase 1 provides basic label usage percentages per repository. Phase 2 extends this with AI recommendation data:

```python
# Add to queries.py - extended label_summary alias
QUERY_ALIASES['label_summary'] = {
    'sql': '''
        SELECT 
            i.org || '/' || i.repo as repository,
            l.name as label,
            COUNT(*) as issue_count,
            ROUND(COUNT(*) * 100.0 / 
                (SELECT COUNT(*) FROM issues i2 WHERE i2.org = i.org AND i2.repo = i.repo), 1
            ) as current_percentage,
            
            -- AI recommendation data
            COUNT(ar.label) as recommended_count,
            ROUND(COUNT(ar.label) * 100.0 / 
                (SELECT COUNT(*) FROM issues i3 WHERE i3.org = i.org AND i3.repo = i.repo), 1
            ) as recommended_percentage,
            
            -- Impact analysis
            CASE 
                WHEN COUNT(ar.label) > COUNT(*) THEN 'Under-labeled'
                WHEN COUNT(ar.label) < COUNT(*) THEN 'Over-labeled'
                ELSE 'Balanced'
            END as recommendation_impact,
            
            AVG(ar.confidence) as avg_ai_confidence
            
        FROM labels l
        JOIN issues i ON l.issue_id = i.id
        LEFT JOIN ai_results air ON i.id = air.issue_id
        LEFT JOIN ai_recommendations ar ON air.id = ar.result_id AND ar.label = l.name
        GROUP BY i.org, i.repo, l.name
        ORDER BY i.org, i.repo, current_percentage DESC
    ''',
    'description': 'Label usage percentages per repository with AI recommendation analysis'
}
```

**Extended Output Columns:**
- `repository` - Repository name (org/repo)
- `label` - Label name
- `issue_count` - Current issues with this label
- `current_percentage` - Current usage percentage
- `recommended_count` - Issues AI recommends should have this label
- `recommended_percentage` - AI recommended usage percentage
- `recommendation_impact` - Under-labeled/Over-labeled/Balanced
- `avg_ai_confidence` - Average AI confidence for this label

**Usage Examples:**
```bash
# Show label analysis for all repositories
uv run gh-analysis query alias label_summary

# Filter to specific repository
uv run gh-analysis query sql "SELECT * FROM (${label_summary_sql}) WHERE repository = 'replicated/kots'"

# Find under-labeled issues
uv run gh-analysis query sql "SELECT * FROM (${label_summary_sql}) WHERE recommendation_impact = 'Under-labeled'"
```

### **AI Results Schema Extension**
```sql
-- Add to existing schema.sql from Phase 1
CREATE TABLE IF NOT EXISTS ai_results (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    processor VARCHAR NOT NULL,
    model VARCHAR NOT NULL,
    confidence DECIMAL(5,4),
    result JSON NOT NULL,
    processing_time_ms INTEGER,
    created_at TIMESTAMP NOT NULL,
    file_path VARCHAR,  -- Reference to JSON result file
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
    UNIQUE(issue_id, processor)
);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id INTEGER PRIMARY KEY,
    result_id INTEGER NOT NULL,
    label VARCHAR NOT NULL,
    confidence DECIMAL(5,4) NOT NULL,
    reasoning TEXT,
    FOREIGN KEY (result_id) REFERENCES ai_results(id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_ai_results_processor ON ai_results(processor);
CREATE INDEX IF NOT EXISTS idx_ai_results_confidence ON ai_results(confidence);
CREATE INDEX IF NOT EXISTS idx_ai_results_created_at ON ai_results(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_label ON ai_recommendations(label);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_confidence ON ai_recommendations(confidence);
```

### **Database Manager Extensions**
```python
# Add these methods to existing database.py from Phase 1

def sync_ai_results(self, results_dir: Path = Path("data/results")) -> Dict[str, int]:
    """Sync AI result JSON files into database."""
    stats = {"synced": 0, "errors": 0, "skipped": 0}
    
    for json_file in results_dir.glob("*_*.json"):
        try:
            # Parse filename to get issue info
            parts = json_file.stem.split('_')
            if len(parts) < 4:
                continue
            
            org = parts[0]
            repo = parts[1] 
            issue_num = int(parts[3])
            processor = '_'.join(parts[4:])  # Rest is processor name
            
            # Get issue ID from database
            issue_id_result = self.conn.execute(
                'SELECT id FROM issues WHERE org = ? AND repo = ? AND number = ?',
                [org, repo, issue_num]
            ).fetchone()
            
            if not issue_id_result:
                console.print(f"[yellow]Issue not found for {json_file}[/yellow]")
                stats["skipped"] += 1
                continue
            
            issue_id = issue_id_result[0]
            
            # Load result data
            with open(json_file) as f:
                result_data = json.load(f)
            
            # Extract metadata
            processor_info = result_data.get('processor', {})
            analysis = result_data.get('analysis', {})
            
            # Store in database
            self.conn.execute('''
                INSERT OR REPLACE INTO ai_results
                (issue_id, processor, model, confidence, result, created_at, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', [
                issue_id, processor, 
                processor_info.get('model', 'unknown'),
                analysis.get('confidence'),
                json.dumps(result_data),
                processor_info.get('timestamp', datetime.now()),
                str(json_file)
            ])
            
            stats["synced"] += 1
            
        except Exception as e:
            console.print(f"[red]Error syncing {json_file}: {e}[/red]")
            stats["errors"] += 1
    
    return stats

def store_ai_result(self, 
                   issue_id: int,
                   processor: str,
                   model: str,
                   result_data: Dict[str, Any],
                   confidence: Optional[float] = None,
                   processing_time_ms: Optional[int] = None,
                   file_path: Optional[str] = None):
    """Store AI processing result in database."""
    self.conn.execute('''
        INSERT OR REPLACE INTO ai_results
        (issue_id, processor, model, confidence, result, processing_time_ms, created_at, file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        issue_id, processor, model, confidence, 
        json.dumps(result_data), processing_time_ms, 
        datetime.now(), file_path
    ])
    
    # Get result ID for recommendations
    result_id = self.conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    
    # Store recommendations if available
    if 'recommended_labels' in result_data:
        self.conn.execute('DELETE FROM ai_recommendations WHERE result_id = ?', [result_id])
        for rec in result_data['recommended_labels']:
            self.conn.execute('''
                INSERT INTO ai_recommendations
                (result_id, label, confidence, reasoning)
                VALUES (?, ?, ?, ?)
            ''', [
                result_id, rec.get('label', ''), 
                rec.get('confidence', 0), rec.get('reasoning', '')
            ])
```

### **AI Processing Pipeline**
```python
# pipeline.py
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from rich.console import Console
from rich.progress import track

from ..storage.database import DatabaseManager
from ..github_client.models import StoredIssue

console = Console()


class AIProcessingPipeline:
    """SQL-driven AI processing pipeline."""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        self.selected_issues: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
    
    def select_issues(self, query: str, params: List[Any] = None) -> 'AIProcessingPipeline':
        """Select issues using SQL query."""
        self.selected_issues = self.db.query_issues(query, params)
        console.print(f"Selected {len(self.selected_issues)} issues for processing")
        return self
    
    def where_missing_analysis(self, processor: str) -> 'AIProcessingPipeline':
        """Filter to issues missing specific analysis."""
        query = '''
            SELECT i.* FROM issues i
            LEFT JOIN ai_results ar ON i.id = ar.issue_id AND ar.processor = ?
            WHERE ar.id IS NULL
        '''
        return self.select_issues(query, [processor])
    
    def where_low_confidence(self, processor: str, threshold: float = 0.7) -> 'AIProcessingPipeline':
        """Filter to issues with low confidence scores."""
        query = '''
            SELECT i.* FROM issues i
            JOIN ai_results ar ON i.id = ar.issue_id
            WHERE ar.processor = ? AND ar.confidence < ?
        '''
        return self.select_issues(query, [processor, threshold])
    
    def where_state(self, state: str) -> 'AIProcessingPipeline':
        """Filter by issue state."""
        if not self.selected_issues:
            query = 'SELECT * FROM issues WHERE state = ?'
            return self.select_issues(query, [state])
        else:
            # Filter current selection
            self.selected_issues = [
                issue for issue in self.selected_issues 
                if issue['state'] == state
            ]
            console.print(f"Filtered to {len(self.selected_issues)} {state} issues")
            return self
    
    def where_repo(self, org: str, repo: str) -> 'AIProcessingPipeline':
        """Filter by repository."""
        if not self.selected_issues:
            query = 'SELECT * FROM issues WHERE org = ? AND repo = ?'
            return self.select_issues(query, [org, repo])
        else:
            # Filter current selection
            self.selected_issues = [
                issue for issue in self.selected_issues 
                if issue['org'] == org and issue['repo'] == repo
            ]
            console.print(f"Filtered to {len(self.selected_issues)} issues from {org}/{repo}")
            return self
    
    def limit(self, count: int) -> 'AIProcessingPipeline':
        """Limit number of issues."""
        self.selected_issues = self.selected_issues[:count]
        console.print(f"Limited to {len(self.selected_issues)} issues")
        return self
    
    def order_by_created(self, desc: bool = True) -> 'AIProcessingPipeline':
        """Order by creation date."""
        reverse = desc
        self.selected_issues.sort(
            key=lambda x: x['created_at'], 
            reverse=reverse
        )
        return self
    
    async def process_with(self, processor_name: str, **kwargs) -> 'AIProcessingPipeline':
        """Process selected issues with AI."""
        if not self.selected_issues:
            console.print("[yellow]No issues selected for processing[/yellow]")
            return self
        
        # Import processor dynamically based on what's available
        processor = self._get_processor(processor_name, **kwargs)
        
        console.print(f"Processing {len(self.selected_issues)} issues with {processor_name}")
        
        for issue_row in track(self.selected_issues, description="Processing issues"):
            try:
                # Load full issue data from JSON
                issue_data = self._load_issue_data(issue_row)
                if not issue_data:
                    continue
                
                # Process with AI
                start_time = datetime.now()
                result = await processor.analyze_issue(issue_data)
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Store result in database
                self._store_ai_result(
                    issue_row, processor_name, result, 
                    processing_time, **kwargs
                )
                
                self.results.append({
                    'issue_id': issue_row['id'],
                    'processor': processor_name,
                    'result': result
                })
                
            except Exception as e:
                console.print(f"[red]Error processing issue {issue_row['number']}: {e}[/red]")
                continue
        
        console.print(f"✅ Processed {len(self.results)} issues successfully")
        return self
    
    def _get_processor(self, processor_name: str, **kwargs):
        """Get processor instance based on name."""
        # Dynamic import to avoid circular dependencies
        if processor_name == 'product-labeling':
            from ..ai.processors import ProductLabelingProcessor
            return ProductLabelingProcessor(**kwargs)
        else:
            raise ValueError(f"Unknown processor: {processor_name}")
    
    def _load_issue_data(self, issue_row: Dict[str, Any]) -> Dict[str, Any] | None:
        """Load full issue data from JSON file."""
        try:
            file_path = Path(issue_row['file_path'])
            if not file_path.exists():
                console.print(f"[yellow]JSON file not found: {file_path}[/yellow]")
                return None
            
            with open(file_path) as f:
                return json.load(f)
        except Exception as e:
            console.print(f"[red]Error loading {file_path}: {e}[/red]")
            return None
    
    def _store_ai_result(self, issue_row: Dict[str, Any], processor: str, 
                        result: Any, processing_time: float, **kwargs):
        """Store AI result in database."""
        model_name = kwargs.get('model_name', 'unknown')
        confidence = getattr(result, 'confidence', None)
        
        # Convert result to dict for storage
        result_dict = result.model_dump() if hasattr(result, 'model_dump') else result
        
        self.db.store_ai_result(
            issue_row['id'],
            processor,
            model_name,
            result_dict,
            confidence,
            int(processing_time)
        )
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of processing results."""
        if not self.results:
            return {}
        
        total = len(self.results)
        avg_confidence = sum(
            r['result'].confidence for r in self.results 
            if hasattr(r['result'], 'confidence')
        ) / total if total > 0 else 0
        
        return {
            'total_processed': total,
            'average_confidence': round(avg_confidence, 3),
            'processors_used': list(set(r['processor'] for r in self.results))
        }


# Convenience functions
def create_pipeline(db: DatabaseManager = None) -> AIProcessingPipeline:
    """Create a new processing pipeline."""
    return AIProcessingPipeline(db)


def process_missing_analysis(processor: str, limit: int = None) -> AIProcessingPipeline:
    """Quick pipeline for processing issues missing analysis."""
    pipeline = create_pipeline()
    pipeline.where_missing_analysis(processor)
    
    if limit:
        pipeline.limit(limit)
    
    return pipeline


def process_low_confidence(processor: str, threshold: float = 0.7, limit: int = None) -> AIProcessingPipeline:
    """Quick pipeline for reprocessing low confidence results."""
    pipeline = create_pipeline()
    pipeline.where_low_confidence(processor, threshold)
    
    if limit:
        pipeline.limit(limit)
    
    return pipeline
```

### **Enhanced Processing Commands**
```python
# process_query.py
import typer
import asyncio
from typing import Optional

from rich.console import Console
from rich.table import Table

from ..storage.database import DatabaseManager
from ..ai.pipeline import AIProcessingPipeline, create_pipeline

console = Console()
app = typer.Typer(help="AI processing with SQL-based issue selection")


@app.command()
def missing(
    processor: str = typer.Argument(..., help="Processor name (e.g., 'product-labeling')"),
    limit: Optional[int] = typer.Option(None, help="Limit number of issues to process"),
    org: Optional[str] = typer.Option(None, help="Filter by organization"),
    repo: Optional[str] = typer.Option(None, help="Filter by repository"),
    state: Optional[str] = typer.Option("open", help="Filter by issue state")
):
    """Process issues missing AI analysis."""
    pipeline = create_pipeline()
    pipeline.where_missing_analysis(processor)
    
    if state:
        pipeline.where_state(state)
    
    if org and repo:
        pipeline.where_repo(org, repo)
    
    if limit:
        pipeline.limit(limit)
    
    # Show selection summary
    console.print(f"Will process {len(pipeline.selected_issues)} issues missing {processor} analysis")
    
    if not typer.confirm("Continue with processing?"):
        return
    
    # Process
    asyncio.run(pipeline.process_with(processor))
    
    # Show results
    summary = pipeline.get_results_summary()
    if summary:
        console.print(f"✅ Processed {summary['total_processed']} issues")
        console.print(f"📊 Average confidence: {summary['average_confidence']}")


@app.command()
def reprocess(
    processor: str = typer.Argument(..., help="Processor name"),
    threshold: float = typer.Option(0.7, help="Confidence threshold for reprocessing"),
    limit: Optional[int] = typer.Option(None, help="Limit number of issues"),
    days_old: Optional[int] = typer.Option(None, help="Only reprocess results older than N days")
):
    """Reprocess issues with low confidence scores."""
    pipeline = create_pipeline()
    
    if days_old:
        # Custom query with time filter
        query = '''
            SELECT i.* FROM issues i
            JOIN ai_results ar ON i.id = ar.issue_id
            WHERE ar.processor = ? AND ar.confidence < ? 
              AND ar.created_at < datetime('now', ? || ' days')
        '''
        pipeline.select_issues(query, [processor, threshold, f'-{days_old}'])
    else:
        pipeline.where_low_confidence(processor, threshold)
    
    if limit:
        pipeline.limit(limit)
    
    console.print(f"Will reprocess {len(pipeline.selected_issues)} issues with confidence < {threshold}")
    
    if not typer.confirm("Continue with reprocessing?"):
        return
    
    asyncio.run(pipeline.process_with(processor))
    
    summary = pipeline.get_results_summary()
    if summary:
        console.print(f"✅ Reprocessed {summary['total_processed']} issues")


@app.command()
def custom(
    processor: str = typer.Argument(..., help="Processor name"),
    query: str = typer.Argument(..., help="SQL query to select issues"),
    limit: Optional[int] = typer.Option(None, help="Limit results"),
):
    """Process issues selected by custom SQL query."""
    pipeline = create_pipeline()
    
    # Ensure query selects from issues table
    if 'FROM issues' not in query.upper():
        console.print("[red]Query must select from 'issues' table[/red]")
        return
    
    pipeline.select_issues(query)
    
    if limit:
        pipeline.limit(limit)
    
    console.print(f"Selected {len(pipeline.selected_issues)} issues for processing")
    
    if not typer.confirm("Continue with processing?"):
        return
    
    asyncio.run(pipeline.process_with(processor))
    
    summary = pipeline.get_results_summary()
    if summary:
        console.print(f"✅ Processed {summary['total_processed']} issues")


@app.command()
def analytics():
    """Show AI processing analytics."""
    try:
        db = DatabaseManager()
        
        # Processing overview
        overview = db.query_issues('''
            SELECT 
                processor,
                COUNT(*) as total_results,
                AVG(confidence) as avg_confidence,
                MIN(confidence) as min_confidence,
                MAX(confidence) as max_confidence,
                MAX(created_at) as latest_processing
            FROM ai_results
            GROUP BY processor
            ORDER BY total_results DESC
        ''')
        
        if not overview:
            console.print("[yellow]No AI processing results found[/yellow]")
            return
        
        table = Table(title="AI Processing Analytics")
        table.add_column("Processor", style="cyan")
        table.add_column("Total Results", style="white")
        table.add_column("Avg Confidence", style="green")
        table.add_column("Min/Max", style="white")
        table.add_column("Latest Processing", style="dim")
        
        for row in overview:
            table.add_row(
                row['processor'],
                str(row['total_results']),
                f"{row['avg_confidence']:.3f}",
                f"{row['min_confidence']:.2f} / {row['max_confidence']:.2f}",
                row['latest_processing'][:10]  # Just date part
            )
        
        console.print(table)
        
        # Confidence distribution
        console.print("\n[bold]Confidence Distribution[/bold]")
        dist = db.query_issues('''
            SELECT 
                CASE 
                    WHEN confidence >= 0.9 THEN 'Very High (0.9+)'
                    WHEN confidence >= 0.8 THEN 'High (0.8-0.9)'
                    WHEN confidence >= 0.7 THEN 'Medium (0.7-0.8)'
                    WHEN confidence >= 0.6 THEN 'Low (0.6-0.7)'
                    ELSE 'Very Low (<0.6)'
                END as confidence_range,
                COUNT(*) as count
            FROM ai_results
            WHERE confidence IS NOT NULL
            GROUP BY confidence_range
            ORDER BY 
                CASE confidence_range
                    WHEN 'Very High (0.9+)' THEN 1
                    WHEN 'High (0.8-0.9)' THEN 2
                    WHEN 'Medium (0.7-0.8)' THEN 3
                    WHEN 'Low (0.6-0.7)' THEN 4
                    ELSE 5
                END
        ''')
        
        dist_table = Table()
        dist_table.add_column("Confidence Range", style="cyan")
        dist_table.add_column("Count", style="white")
        
        for row in dist:
            dist_table.add_row(row['confidence_range'], str(row['count']))
        
        console.print(dist_table)
        
    except ImportError:
        console.print("[red]Database not available[/red]")
    except Exception as e:
        console.print(f"[red]Analytics error: {e}[/red]")
```

### **CLI Integration**
```python
# Modify cli/main.py to add process-query commands
from .process_query import app as process_query_app

app.add_typer(process_query_app, name="process-query", help="AI processing with SQL selection")

# Enhanced sync command to include AI results
@app.command()
def sync(
    ai_results: bool = typer.Option(False, help="Also sync AI results")
):
    """Sync JSON files to database."""
    try:
        storage = StorageManager()
        if not storage.db:
            console.print("[red]Database not enabled[/red]")
            return
        
        # Sync issues (existing functionality from Phase 1)
        console.print("Syncing JSON files to database...")
        with console.status("[bold green]Syncing..."):
            stats = storage.db.sync_from_json()
        
        table = Table(title="Issue Sync Results")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="white")
        
        table.add_row("✅ Synced", str(stats['synced']))
        table.add_row("⏭️ Skipped", str(stats['skipped']))
        table.add_row("❌ Errors", str(stats['errors']))
        
        console.print(table)
        
        # Sync AI results if requested
        if ai_results:
            console.print("\nSyncing AI results...")
            with console.status("[bold green]Syncing AI results..."):
                ai_stats = storage.db.sync_ai_results()
            
            ai_table = Table(title="AI Results Sync")
            ai_table.add_column("Status", style="cyan")
            ai_table.add_column("Count", style="white")
            
            ai_table.add_row("✅ Synced", str(ai_stats['synced']))
            ai_table.add_row("⏭️ Skipped", str(ai_stats['skipped']))
            ai_table.add_row("❌ Errors", str(ai_stats['errors']))
            
            console.print(ai_table)
        
    except ImportError:
        console.print("[red]DuckDB not available. Install with: uv add duckdb[/red]")
```

## Testing Strategy

```python
# test_pipeline.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from github_issue_analysis.ai.pipeline import AIProcessingPipeline


class TestAIProcessingPipeline:
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.query_issues = MagicMock()
        db.store_ai_result = MagicMock()
        return db
    
    @pytest.fixture
    def mock_pipeline(self, mock_db):
        """Create pipeline with mocked database."""
        return AIProcessingPipeline(mock_db)
    
    def test_where_missing_analysis(self, mock_pipeline, mock_db):
        """Test selecting issues missing analysis."""
        mock_db.query_issues.return_value = [
            {'id': 1, 'org': 'test', 'repo': 'test', 'number': 1}
        ]
        
        result = mock_pipeline.where_missing_analysis('product-labeling')
        
        # Verify correct SQL query was used
        args, kwargs = mock_db.query_issues.call_args
        sql = args[0]
        params = args[1]
        
        assert 'LEFT JOIN ai_results' in sql
        assert 'ar.processor = ?' in sql
        assert params == ['product-labeling']
        assert len(result.selected_issues) == 1
    
    def test_chaining_filters(self, mock_pipeline, mock_db):
        """Test chaining multiple filters."""
        mock_db.query_issues.return_value = [
            {'id': 1, 'org': 'test', 'repo': 'repo1', 'number': 1, 'state': 'open'},
            {'id': 2, 'org': 'test', 'repo': 'repo2', 'number': 2, 'state': 'closed'},
            {'id': 3, 'org': 'other', 'repo': 'repo1', 'number': 3, 'state': 'open'}
        ]
        
        # Chain filters
        result = (mock_pipeline
                 .where_missing_analysis('product-labeling')
                 .where_state('open')
                 .where_repo('test', 'repo1'))
        
        # Should filter down to just one issue
        assert len(result.selected_issues) == 1
        assert result.selected_issues[0]['id'] == 1
    
    @pytest.mark.asyncio
    async def test_process_with(self, mock_pipeline, mock_db):
        """Test AI processing."""
        # Mock selected issues
        mock_pipeline.selected_issues = [
            {
                'id': 1,
                'org': 'test', 
                'repo': 'test',
                'number': 1,
                'file_path': '/path/to/test.json'
            }
        ]
        
        # Mock file loading
        mock_pipeline._load_issue_data = MagicMock(return_value={
            'org': 'test',
            'repo': 'test', 
            'issue': {'title': 'Test Issue'}
        })
        
        # Mock processor
        mock_processor = AsyncMock()
        mock_result = MagicMock()
        mock_result.confidence = 0.85
        mock_processor.analyze_issue.return_value = mock_result
        
        mock_pipeline._get_processor = MagicMock(return_value=mock_processor)
        
        # Process
        await mock_pipeline.process_with('product-labeling')
        
        # Verify processor was called
        mock_processor.analyze_issue.assert_called_once()
        
        # Verify result was stored
        mock_db.store_ai_result.assert_called_once()
        
        # Verify results tracking
        assert len(mock_pipeline.results) == 1
        assert mock_pipeline.results[0]['processor'] == 'product-labeling'
```

## Validation Steps

### **Setup and Data Preparation**
```bash
# 1. Ensure Phase 1 is working
uv run gh-analysis status  # Should show database enabled

# 2. Collect some test data
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 3

# 3. Run some AI processing to have existing results
# (This assumes AI processing is available from previous tasks)
```

### **AI Results Integration**
```bash
# 4. Sync existing AI results to database
uv run gh-analysis sync --ai-results

# 5. Check AI analytics
uv run gh-analysis process-query analytics
```

### **Pipeline Functionality**
```bash
# 6. Test missing analysis processing
uv run gh-analysis process-query missing product-labeling --limit 2

# 7. Test reprocessing low confidence
uv run gh-analysis process-query reprocess product-labeling --threshold 0.8 --limit 1

# 8. Test custom query processing
uv run gh-analysis process-query custom product-labeling "SELECT * FROM issues WHERE state = 'closed'" --limit 1
```

### **Advanced Queries**
```bash
# 9. Query AI results through SQL
uv run gh-analysis query sql "SELECT processor, AVG(confidence), COUNT(*) FROM ai_results GROUP BY processor"

# 10. Find issues needing attention
uv run gh-analysis query sql "SELECT org, repo, number FROM issues i LEFT JOIN ai_results ar ON i.id = ar.issue_id WHERE ar.id IS NULL AND i.state = 'open'"
```

### **Quality Assurance**
```bash
# 11. Run tests
uv run pytest tests/test_ai/test_pipeline.py -v

# 12. Quality checks
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

## Acceptance Criteria
- [ ] AI results schema integrated into existing database from Phase 1
- [ ] AI processing pipeline with SQL-based issue selection
- [ ] Process-query commands for missing analysis, reprocessing, custom queries
- [ ] AI analytics dashboard showing processing statistics
- [ ] Automatic sync of AI results from JSON to database
- [ ] Enhanced processing commands with filtering options
- [ ] Integration with existing AI processing system
- [ ] Comprehensive pipeline tests
- [ ] Performance optimized for large datasets
- [ ] Error handling and progress reporting

**Success Metrics**: 
1. User can run `uv run gh-analysis process-query missing product-labeling --state open --limit 10` to intelligently select and process issues
2. `uv run gh-analysis process-query analytics` shows comprehensive AI processing insights
3. Processing pipeline enables complex workflows like "process open issues from specific repos that don't have product labels"
4. Extended `uv run gh-analysis query alias label_summary` shows current vs AI-recommended label usage with impact analysis

## Agent Notes
[Document your pipeline design decisions, integration approach, and performance optimizations]

## Implementation Notes

**Phase 2 Design:**
- **Builds on Phase 1**: Uses existing database schema and adds AI-specific tables
- **Pipeline Architecture**: Chainable filters using SQL for intelligent issue selection
- **Result Tracking**: Complete audit trail of AI processing with confidence scores
- **Analytics**: Rich insights into processing patterns and model performance

**Integration Points:**
- Extends Phase 1 database with AI-specific tables
- Reuses Phase 1 query infrastructure for issue selection  
- Designed to work with Phase 3 update system (can reprocess changed issues)
- Compatible with existing AI processing systems

This phase transforms the tool from a query interface into an intelligent AI processing platform while building naturally on Phase 1's foundation.