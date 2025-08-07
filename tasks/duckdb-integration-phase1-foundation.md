# Task: DuckDB Integration - Phase 1: Database Foundation + Query Interface

**Status:** not started  
**Priority:** high  
**Estimated Time:** 4-5 hours

## Description
Add DuckDB as a query layer while maintaining existing JSON storage as source of truth. Implement database sync and rich SQL query capabilities with CLI interface.

## Prerequisites
- `github-issue-collection.md` must be completed
- Existing JSON storage must be functional

## Files to Create
- `github_issue_analysis/storage/database.py` - DuckDB integration
- `github_issue_analysis/storage/schema.sql` - Database schema
- `github_issue_analysis/storage/queries.py` - Pre-built query templates
- `github_issue_analysis/cli/query.py` - SQL query commands
- `tests/test_storage/test_database.py` - Database tests
- `tests/test_cli/test_query.py` - Query command tests
- `tests/fixtures/sample_issues.py` - Test data fixtures

## Files to Modify
- `github_issue_analysis/storage/manager.py` - Add optional database sync
- `github_issue_analysis/storage/__init__.py` - Export database classes
- `github_issue_analysis/cli/main.py` - Add query commands
- `pyproject.toml` - Add duckdb dependency

## Implementation Details

### **Core Design Principle: Completely Optional**
```python
# Database is optional - existing functionality unchanged
class StorageManager:
    def __init__(self, base_path: str = "data/issues", enable_db: bool = None):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Auto-enable if duckdb available and not explicitly disabled
        if enable_db is None:
            try:
                import duckdb
                enable_db = True
            except ImportError:
                enable_db = False
        
        self.db = DatabaseManager() if enable_db else None
    
    def save_issue(self, org: str, repo: str, issue: GitHubIssue, 
                   metadata: dict[str, Any] | None = None) -> Path:
        """Save issue to JSON and optionally sync to database."""
        # Existing JSON save logic (unchanged)
        file_path = self._get_file_path(org, repo, issue.number)
        # ... existing save code ...
        
        # Optional database sync
        if self.db:
            try:
                stored_issue = StoredIssue(org=org, repo=repo, issue=issue, metadata=metadata)
                self.db.upsert_issue(stored_issue, file_path)
            except Exception as e:
                console.print(f"[yellow]Database sync failed: {e}[/yellow]")
                # Continue - JSON save succeeded, database is bonus
        
        return file_path
```

### **Database Schema**
```sql
-- schema.sql
CREATE TABLE IF NOT EXISTS issues (
    id INTEGER PRIMARY KEY,
    org VARCHAR NOT NULL,
    repo VARCHAR NOT NULL,
    number INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    body TEXT,
    state VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    user_login VARCHAR NOT NULL,
    user_id INTEGER NOT NULL,
    file_path VARCHAR NOT NULL,
    collection_timestamp TIMESTAMP NOT NULL,
    UNIQUE(org, repo, number)
);

CREATE TABLE IF NOT EXISTS labels (
    issue_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    color VARCHAR NOT NULL,
    description TEXT,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE,
    PRIMARY KEY (issue_id, name)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    github_id INTEGER NOT NULL UNIQUE,
    user_login VARCHAR NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    original_url VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    local_path VARCHAR,
    content_type VARCHAR,
    size INTEGER,
    downloaded BOOLEAN DEFAULT FALSE,
    source VARCHAR NOT NULL,
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_issues_org_repo ON issues(org, repo);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS idx_issues_created_at ON issues(created_at);
CREATE INDEX IF NOT EXISTS idx_issues_updated_at ON issues(updated_at);
CREATE INDEX IF NOT EXISTS idx_labels_name ON labels(name);
CREATE INDEX IF NOT EXISTS idx_comments_created_at ON comments(created_at);
```

### **Database Manager**
```python
# database.py
import json
import duckdb
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime

from rich.console import Console
from ..github_client.models import StoredIssue

console = Console()


class DatabaseManager:
    """DuckDB integration for GitHub issues storage."""
    
    def __init__(self, db_path: str = "data/issues.duckdb"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._setup_schema()
    
    def _setup_schema(self):
        """Initialize database schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        with open(schema_path) as f:
            self.conn.execute(f.read())
    
    def sync_from_json(self, issues_dir: Path = Path("data/issues"), 
                       force: bool = False) -> Dict[str, int]:
        """Sync JSON files into database."""
        stats = {"synced": 0, "errors": 0, "skipped": 0}
        
        for json_file in issues_dir.glob("*_issue_*.json"):
            try:
                # Check if already synced (unless forced)
                if not force and self._is_file_synced(json_file):
                    stats["skipped"] += 1
                    continue
                
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                stored_issue = StoredIssue.model_validate(data)
                self.upsert_issue(stored_issue, json_file)
                stats["synced"] += 1
                
            except Exception as e:
                console.print(f"[red]Error syncing {json_file}: {e}[/red]")
                stats["errors"] += 1
        
        return stats
    
    def _is_file_synced(self, file_path: Path) -> bool:
        """Check if JSON file is already synced to database."""
        result = self.conn.execute(
            'SELECT collection_timestamp FROM issues WHERE file_path = ?',
            [str(file_path)]
        ).fetchone()
        
        if not result:
            return False
        
        # Compare file modification time with database timestamp
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        db_timestamp = datetime.fromisoformat(result[0])
        return file_mtime <= db_timestamp
    
    def upsert_issue(self, stored_issue: StoredIssue, file_path: Path):
        """Insert or update issue in database."""
        issue = stored_issue.issue
        
        # Begin transaction
        self.conn.begin()
        
        try:
            # Insert/update main issue
            self.conn.execute('''
                INSERT OR REPLACE INTO issues 
                (org, repo, number, title, body, state, created_at, updated_at,
                 user_login, user_id, file_path, collection_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', [
                stored_issue.org, stored_issue.repo, issue.number,
                issue.title, issue.body, issue.state,
                issue.created_at, issue.updated_at,
                issue.user.login, issue.user.id,
                str(file_path), stored_issue.metadata.get('collection_timestamp')
            ])
            
            # Get issue ID
            issue_id = self.conn.execute(
                'SELECT id FROM issues WHERE org = ? AND repo = ? AND number = ?',
                [stored_issue.org, stored_issue.repo, issue.number]
            ).fetchone()[0]
            
            # Clear and insert labels
            self.conn.execute('DELETE FROM labels WHERE issue_id = ?', [issue_id])
            for label in issue.labels:
                self.conn.execute('''
                    INSERT INTO labels (issue_id, name, color, description)
                    VALUES (?, ?, ?, ?)
                ''', [issue_id, label.name, label.color, label.description])
            
            # Clear and insert comments
            self.conn.execute('DELETE FROM comments WHERE issue_id = ?', [issue_id])
            for comment in issue.comments:
                self.conn.execute('''
                    INSERT INTO comments 
                    (issue_id, github_id, user_login, user_id, body, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', [
                    issue_id, comment.id, comment.user.login, comment.user.id,
                    comment.body, comment.created_at, comment.updated_at
                ])
            
            # Clear and insert attachments
            self.conn.execute('DELETE FROM attachments WHERE issue_id = ?', [issue_id])
            for attachment in issue.attachments:
                self.conn.execute('''
                    INSERT INTO attachments 
                    (issue_id, original_url, filename, local_path, content_type, 
                     size, downloaded, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', [
                    issue_id, attachment.original_url, attachment.filename,
                    attachment.local_path, attachment.content_type,
                    attachment.size, attachment.downloaded, attachment.source
                ])
            
            self.conn.commit()
            
        except Exception:
            self.conn.rollback()
            raise
    
    def query_issues(self, query: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """Execute SQL query and return results."""
        if params is None:
            params = []
        try:
            return self.conn.execute(query, params).fetchdf().to_dict('records')
        except Exception as e:
            console.print(f"[red]Query error: {e}[/red]")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics."""
        stats = {}
        
        # Basic counts
        stats['total_issues'] = self.conn.execute('SELECT COUNT(*) FROM issues').fetchone()[0]
        stats['total_comments'] = self.conn.execute('SELECT COUNT(*) FROM comments').fetchone()[0]
        stats['total_attachments'] = self.conn.execute('SELECT COUNT(*) FROM attachments').fetchone()[0]
        
        # Repository breakdown
        repo_stats = self.conn.execute('''
            SELECT 
                org || '/' || repo as repository, 
                COUNT(*) as issue_count,
                SUM(CASE WHEN state = 'open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN state = 'closed' THEN 1 ELSE 0 END) as closed_count
            FROM issues 
            GROUP BY org, repo 
            ORDER BY issue_count DESC
        ''').fetchdf()
        stats['repositories'] = repo_stats.to_dict('records')
        
        # State distribution
        state_stats = self.conn.execute('''
            SELECT state, COUNT(*) as count FROM issues GROUP BY state
        ''').fetchdf()
        stats['states'] = state_stats.to_dict('records')
        
        # Top labels
        label_stats = self.conn.execute('''
            SELECT l.name, COUNT(*) as usage_count
            FROM labels l
            GROUP BY l.name
            ORDER BY usage_count DESC
            LIMIT 10
        ''').fetchdf()
        stats['top_labels'] = label_stats.to_dict('records')
        
        # Recent activity
        recent_stats = self.conn.execute('''
            SELECT COUNT(*) as count
            FROM issues 
            WHERE updated_at > datetime('now', '-7 days')
        ''').fetchone()[0]
        stats['recent_activity'] = recent_stats
        
        return stats
    
    def close(self):
        """Close database connection."""
        self.conn.close()
```

### **Query Templates**
```python
# queries.py
"""Pre-built query templates for common operations."""

QUERY_ALIASES = {
    'open_issues': {
        'sql': '''
            SELECT 
                org || '/' || repo as repository,
                number,
                title,
                created_at,
                COUNT(c.id) as comment_count
            FROM issues i
            LEFT JOIN comments c ON i.id = c.issue_id
            WHERE state = 'open'
            GROUP BY i.id, org, repo, number, title, created_at
            ORDER BY created_at DESC
        ''',
        'description': 'List all open issues with comment counts'
    },
    
    'label_summary': {
        'sql': '''
            SELECT 
                org || '/' || repo as repository,
                l.name as label,
                COUNT(*) as issue_count,
                ROUND(COUNT(*) * 100.0 / 
                    (SELECT COUNT(*) FROM issues i2 WHERE i2.org = i.org AND i2.repo = i.repo), 1
                ) as percentage
            FROM labels l
            JOIN issues i ON l.issue_id = i.id
            GROUP BY org, repo, l.name
            ORDER BY org, repo, percentage DESC
        ''',
        'description': 'Label usage percentages per repository'
    }
}

def get_query(name: str) -> str:
    """Get SQL for a named query alias."""
    if name not in QUERY_ALIASES:
        available = ', '.join(QUERY_ALIASES.keys())
        raise ValueError(f"Unknown query alias '{name}'. Available: {available}")
    return QUERY_ALIASES[name]['sql']

def list_queries() -> Dict[str, str]:
    """List available query aliases with descriptions."""
    return {name: info['description'] for name, info in QUERY_ALIASES.items()}
```

### **CLI Query Commands**
```python
# query.py
import typer
from typing import Optional
from rich.table import Table
from rich.console import Console
from rich import print_json

from ..storage.database import DatabaseManager
from ..storage.queries import get_query, list_queries, QUERY_ALIASES


console = Console()
app = typer.Typer(help="Query GitHub issues using SQL")


@app.command()
def sql(
    query: str = typer.Argument(..., help="SQL query to execute"),
    format: str = typer.Option("table", help="Output format: table, json, csv"),
    limit: Optional[int] = typer.Option(None, help="Limit number of results")
):
    """Execute custom SQL query against issues database."""
    try:
        db = DatabaseManager()
        
        # Add LIMIT if specified
        if limit:
            query = f"SELECT * FROM ({query}) LIMIT {limit}"
        
        results = db.query_issues(query)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        _output_results(results, format)
        
    except ImportError:
        console.print("[red]DuckDB not available. Install with: uv add duckdb[/red]")
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")


@app.command()
def alias(
    name: str = typer.Argument(..., help="Query alias name"),
    format: str = typer.Option("table", help="Output format: table, json, csv"),
    limit: Optional[int] = typer.Option(None, help="Limit number of results")
):
    """Execute pre-built query aliases."""
    try:
        query = get_query(name)
        
        if limit:
            query = f"SELECT * FROM ({query}) LIMIT {limit}"
        
        db = DatabaseManager()
        results = db.query_issues(query)
        
        if not results:
            console.print("[yellow]No results found[/yellow]")
            return
        
        console.print(f"[blue]Query: {QUERY_ALIASES[name]['description']}[/blue]")
        _output_results(results, format)
        
    except ImportError:
        console.print("[red]DuckDB not available. Install with: uv add duckdb[/red]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
    except Exception as e:
        console.print(f"[red]Query failed: {e}[/red]")


@app.command()
def list():
    """List available query aliases."""
    queries = list_queries()
    
    table = Table(title="Available Query Aliases")
    table.add_column("Alias", style="cyan")
    table.add_column("Description", style="white")
    
    for name, description in queries.items():
        table.add_row(name, description)
    
    console.print(table)


def _output_results(results: List[Dict], format: str):
    """Output results in specified format."""
    if format == "json":
        print_json(data=results)
    elif format == "csv":
        if not results:
            return
        
        # Print CSV headers
        headers = results[0].keys()
        print(",".join(headers))
        
        # Print CSV rows
        for row in results:
            values = [str(row.get(h, "")) for h in headers]
            print(",".join(f'"{v}"' for v in values))
    
    else:  # table format
        if not results:
            return
        
        table = Table()
        
        # Add columns
        for key in results[0].keys():
            table.add_column(str(key), style="white")
        
        # Add rows
        for row in results:
            values = [str(v) if v is not None else "" for v in row.values()]
            table.add_row(*values)
        
        console.print(table)
        console.print(f"\n[dim]{len(results)} results[/dim]")
```

### **Enhanced Status Command**
```python
# Modify cli/main.py
@app.command()
def status():
    """Show storage statistics including database status."""
    storage = StorageManager()
    
    # JSON stats
    json_stats = storage.get_storage_stats()
    
    table = Table(title="Storage Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("JSON Issues", str(json_stats['total_issues']))
    table.add_row("Storage Size", f"{json_stats['total_size_mb']} MB")
    table.add_row("Storage Path", json_stats['storage_path'])
    
    # Database stats if available
    if storage.db:
        try:
            db_stats = storage.db.get_stats()
            table.add_row("", "")  # Separator
            table.add_row("Database Issues", str(db_stats['total_issues']))
            table.add_row("Database Comments", str(db_stats['total_comments']))
            table.add_row("Database Attachments", str(db_stats['total_attachments']))
            table.add_row("Recent Activity (7d)", str(db_stats['recent_activity']))
            
            # Sync status
            json_count = json_stats['total_issues']
            db_count = db_stats['total_issues']
            if json_count == db_count:
                table.add_row("Sync Status", "✅ Synchronized")
            else:
                table.add_row("Sync Status", f"⚠️ Out of sync ({json_count} JSON, {db_count} DB)")
        except Exception as e:
            table.add_row("Database Status", f"❌ Error: {e}")
    else:
        table.add_row("Database Status", "📴 Disabled")
    
    console.print(table)
    
    # Repository breakdown
    if json_stats['repositories']:
        repo_table = Table(title="Repository Breakdown")
        repo_table.add_column("Repository", style="cyan")
        repo_table.add_column("Issues", style="white")
        
        for repo, count in json_stats['repositories'].items():
            repo_table.add_row(repo, str(count))
        
        console.print(repo_table)


@app.command()
def sync():
    """Sync JSON files to database."""
    try:
        storage = StorageManager()
        if not storage.db:
            console.print("[red]Database not enabled[/red]")
            return
        
        console.print("Syncing JSON files to database...")
        with console.status("[bold green]Syncing..."):
            stats = storage.db.sync_from_json()
        
        table = Table(title="Sync Results")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="white")
        
        table.add_row("✅ Synced", str(stats['synced']))
        table.add_row("⏭️ Skipped", str(stats['skipped']))
        table.add_row("❌ Errors", str(stats['errors']))
        
        console.print(table)
        
    except ImportError:
        console.print("[red]DuckDB not available. Install with: uv add duckdb[/red]")
```

### **Main CLI Integration**
```python
# Modify cli/main.py
from .query import app as query_app

# Add query commands
app.add_typer(query_app, name="query", help="Query issues using SQL")
```

## Testing Strategy

```python
# test_database.py
import pytest
from pathlib import Path
import tempfile
import json
from datetime import datetime

from github_issue_analysis.storage.database import DatabaseManager
from github_issue_analysis.github_client.models import StoredIssue, GitHubIssue, GitHubUser, GitHubLabel


class TestDatabaseManager:
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as f:
            db_path = f.name
        
        db = DatabaseManager(db_path)
        yield db
        db.close()
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def sample_issue(self):
        """Sample issue for testing."""
        return StoredIssue(
            org="testorg",
            repo="testrepo", 
            issue=GitHubIssue(
                number=123,
                title="Test Issue",
                body="Test body",
                state="open",
                labels=[GitHubLabel(name="bug", color="red")],
                user=GitHubUser(login="testuser", id=456),
                created_at=datetime.now(),
                updated_at=datetime.now(),
                comments=[]
            ),
            metadata={"collection_timestamp": datetime.now().isoformat()}
        )
    
    def test_schema_creation(self, temp_db):
        """Test database schema is created correctly."""
        # Check tables exist
        tables = temp_db.conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        
        assert "issues" in table_names
        assert "labels" in table_names
        assert "comments" in table_names
        assert "attachments" in table_names
    
    def test_upsert_issue(self, temp_db, sample_issue):
        """Test issue insertion and updates."""
        # Insert issue
        temp_db.upsert_issue(sample_issue, Path("test.json"))
        
        # Verify insertion
        issues = temp_db.query_issues("SELECT * FROM issues")
        assert len(issues) == 1
        assert issues[0]['title'] == "Test Issue"
        
        # Update issue
        sample_issue.issue.title = "Updated Title"
        temp_db.upsert_issue(sample_issue, Path("test.json"))
        
        # Verify update
        issues = temp_db.query_issues("SELECT * FROM issues")
        assert len(issues) == 1
        assert issues[0]['title'] == "Updated Title"
    
    def test_sync_from_json(self, temp_db, sample_issue, tmp_path):
        """Test JSON to database synchronization."""
        # Create JSON file
        json_file = tmp_path / "testorg_testrepo_issue_123.json"
        with open(json_file, 'w') as f:
            json.dump(sample_issue.model_dump(), f)
        
        # Sync from JSON
        stats = temp_db.sync_from_json(tmp_path)
        
        assert stats['synced'] == 1
        assert stats['errors'] == 0
        
        # Verify data
        issues = temp_db.query_issues("SELECT * FROM issues")
        assert len(issues) == 1
    
    def test_query_issues(self, temp_db, sample_issue):
        """Test SQL queries."""
        temp_db.upsert_issue(sample_issue, Path("test.json"))
        
        # Test basic query
        results = temp_db.query_issues("SELECT title FROM issues WHERE state = ?", ["open"])
        assert len(results) == 1
        assert results[0]['title'] == "Test Issue"
    
    def test_get_stats(self, temp_db, sample_issue):
        """Test statistics generation."""
        temp_db.upsert_issue(sample_issue, Path("test.json"))
        
        stats = temp_db.get_stats()
        assert stats['total_issues'] == 1
        assert len(stats['repositories']) == 1
        assert stats['repositories'][0]['repository'] == "testorg/testrepo"


# test_query.py
class TestQueryCommands:
    def test_query_aliases(self):
        """Test query alias templates."""
        from github_issue_analysis.storage.queries import get_query, list_queries
        
        # Test listing query aliases
        queries = list_queries()
        assert 'open_issues' in queries
        assert isinstance(queries['open_issues'], str)
        
        # Test getting query SQL
        sql = get_query('open_issues')
        assert 'SELECT' in sql.upper()
        assert 'issues' in sql.lower()
    
    def test_invalid_query_alias(self):
        """Test handling of invalid query alias names."""
        from github_issue_analysis.storage.queries import get_query
        
        with pytest.raises(ValueError, match="Unknown query alias"):
            get_query('nonexistent_query')
```

## Validation Steps

### **Setup and Installation**
```bash
# 1. Add DuckDB dependency
uv add duckdb

# 2. Verify existing data
uv run gh-analysis status

# 3. Collect some sample data if needed
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 5
```

### **Database Functionality**
```bash
# 4. Check database auto-creation
uv run gh-analysis status
# Should show: "Database Issues: X" and sync status

# 5. Manual sync test
uv run gh-analysis sync
# Should show sync results

# 6. Verify database file exists
ls -la data/issues.duckdb
```

### **Query Interface**
```bash
# 7. List available queries
uv run gh-analysis query list

# 8. Test query aliases
uv run gh-analysis query alias open_issues
uv run gh-analysis query alias label_summary

# 9. Test custom SQL
uv run gh-analysis query sql "SELECT COUNT(*) as total FROM issues"
uv run gh-analysis query sql "SELECT org, repo, COUNT(*) FROM issues GROUP BY org, repo" --format json

# 10. Test output formats
uv run gh-analysis query alias open_issues --format csv --limit 3
```

### **Error Handling**
```bash
# 11. Test without DuckDB (temporarily uninstall)
uv remove duckdb
uv run gh-analysis status  # Should work, show "Database: Disabled"
uv run gh-analysis query sql "SELECT 1"  # Should show error message
uv add duckdb  # Restore

# 12. Test invalid queries
uv run gh-analysis query sql "INVALID SQL"  # Should show error
uv run gh-analysis query alias invalid_query  # Should show error
```

### **Quality Assurance**
```bash
# 13. Run tests
uv run pytest tests/test_storage/test_database.py -v
uv run pytest tests/test_cli/test_query.py -v

# 14. Linting and type checking
uv run ruff check --fix && uv run black . && uv run mypy .

# 15. Integration test
# Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER
# Example: uv run gh-analysis query sql "SELECT title, state FROM issues WHERE repo = 'USER_PROVIDED_REPO'"
```

## Acceptance Criteria
- [ ] DuckDB dependency added to pyproject.toml
- [ ] DatabaseManager with full CRUD operations
- [ ] Automatic database sync on issue collection (optional, graceful failure)
- [ ] Manual sync command with progress reporting
- [ ] SQL query interface with custom queries and pre-built aliases
- [ ] Multiple output formats (table, JSON, CSV)
- [ ] Enhanced status command with database statistics
- [ ] Comprehensive error handling and user feedback
- [ ] Database schema with proper indexes and constraints
- [ ] Zero impact on existing JSON functionality
- [ ] Comprehensive test coverage (>85%)
- [ ] All quality checks pass (ruff, black, mypy)
- [ ] Clear documentation of query capabilities

**Success Metric**: User can collect issues normally (unchanged workflow) and then use `uv run gh-analysis query alias open_issues` to get rich insights not possible with JSON alone.

## Agent Notes
[Document your implementation approach, database design decisions, and query interface choices]

## Implementation Notes

**Phase 1 Value:**
- **Immediate**: Rich database statistics and insights
- **Safe**: Completely optional, no existing functionality changes
- **Foundation**: Enables all future DuckDB-based features

**Design Principles:**
- **JSON remains source of truth**: Database is sync'd copy
- **Graceful degradation**: Works without DuckDB installed
- **Automatic sync**: No user workflow changes required
- **Performance focused**: Proper indexes and efficient queries

This phase delivers immediate query value while building the foundation for Phase 2 (AI integration) and Phase 3 (synchronization).