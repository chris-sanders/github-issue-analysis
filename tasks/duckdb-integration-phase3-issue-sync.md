# Task: DuckDB Integration - Phase 3: Issue Synchronization & Updates

**Status:** not started  
**Priority:** medium  
**Estimated Time:** 4-5 hours  
**Prerequisites:** DuckDB Phase 1 completed (database foundation)

## Description
Implement intelligent issue synchronization to keep local data fresh and current. Focus on updating previously collected issues that were not 'closed' when last seen, with smart prioritization and change tracking.

## Prerequisites
- DuckDB Phase 1 integration completed (database foundation + query interface)
- Existing GitHub issue collection functionality
- Database with collected issues

## Files to Create
- `github_issue_analysis/sync/updater.py` - Core issue update logic
- `github_issue_analysis/sync/strategy.py` - Update prioritization strategies
- `github_issue_analysis/sync/changes.py` - Change tracking and reporting
- `github_issue_analysis/cli/update.py` - Update commands
- `tests/test_sync/test_updater.py` - Update functionality tests
- `tests/test_sync/test_strategy.py` - Prioritization tests

## Files to Modify
- `github_issue_analysis/storage/database.py` - Add change tracking methods
- `github_issue_analysis/storage/schema.sql` - Add update tracking tables
- `github_issue_analysis/cli/main.py` - Add update commands
- `github_issue_analysis/storage/__init__.py` - Export sync classes

## Implementation Details

### **VERIFIED FEATURE: Update Non-Closed Issues**
The core requirement is to update all issues that were not 'closed' when last collected to check if they have since been closed or had other changes.

### **Change Tracking Schema**
```sql
-- Add to schema.sql
CREATE TABLE IF NOT EXISTS issue_updates (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    update_type VARCHAR NOT NULL, -- 'field_change', 'new_comment', 'label_change', 'state_change'
    field_name VARCHAR,           -- 'state', 'title', 'body', 'labels', etc.
    old_value TEXT,
    new_value TEXT,
    updated_at TIMESTAMP NOT NULL,
    update_source VARCHAR DEFAULT 'sync', -- 'sync', 'manual', 'api'
    FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sync_history (
    id INTEGER PRIMARY KEY,
    sync_type VARCHAR NOT NULL,   -- 'open_issues', 'stale_issues', 'repository', 'manual'
    issues_checked INTEGER NOT NULL,
    issues_updated INTEGER NOT NULL,
    issues_unchanged INTEGER NOT NULL,
    errors_count INTEGER DEFAULT 0,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    filter_criteria JSON,        -- Store query parameters used
    error_details TEXT
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_issue_updates_issue_id ON issue_updates(issue_id);
CREATE INDEX IF NOT EXISTS idx_issue_updates_type ON issue_updates(update_type);
CREATE INDEX IF NOT EXISTS idx_issue_updates_updated_at ON issue_updates(updated_at);
CREATE INDEX IF NOT EXISTS idx_sync_history_started_at ON sync_history(started_at);
```

### **Update Strategy Engine**
```python
# strategy.py
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from ..storage.database import DatabaseManager


class UpdatePriority(Enum):
    """Priority levels for issue updates."""
    CRITICAL = 1   # Open issues that might be closed
    HIGH = 2       # Recently active issues
    MEDIUM = 3     # Stale issues (>7 days)
    LOW = 4        # Very old issues (>30 days)


class UpdateStrategy:
    """Strategies for selecting issues to update."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def get_non_closed_issues(self, max_age_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all issues that were not 'closed' when last collected.
        
        This is the core verified feature - find issues that might have changed state.
        """
        query = """
            SELECT 
                i.*,
                CASE 
                    WHEN i.state != 'closed' THEN 1  -- Critical: might be closed now
                    ELSE 4                           -- Low: was already closed
                END as update_priority,
                julianday('now') - julianday(i.collection_timestamp) as days_since_collection
            FROM issues i
            WHERE i.state != 'closed'
        """
        
        params = []
        
        if max_age_days:
            query += " AND julianday('now') - julianday(i.collection_timestamp) <= ?"
            params.append(max_age_days)
        
        query += """
            ORDER BY update_priority ASC, i.updated_at DESC
        """
        
        return self.db.query_issues(query, params)
    
    def get_stale_issues(self, days_threshold: int = 7) -> List[Dict[str, Any]]:
        """Get issues not updated in X days, prioritized by staleness."""
        query = """
            SELECT 
                i.*,
                julianday('now') - julianday(i.collection_timestamp) as days_stale,
                CASE 
                    WHEN i.state = 'open' THEN 1
                    WHEN julianday('now') - julianday(i.collection_timestamp) > 30 THEN 4
                    ELSE 3
                END as update_priority
            FROM issues i
            WHERE julianday('now') - julianday(i.collection_timestamp) >= ?
            ORDER BY update_priority ASC, days_stale DESC
        """
        
        return self.db.query_issues(query, [days_threshold])
    
    def get_recently_active_issues(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get issues that were recently active and should be monitored."""
        query = """
            SELECT i.*
            FROM issues i
            WHERE julianday('now') - julianday(i.updated_at) <= ?
              AND i.state != 'closed'
            ORDER BY i.updated_at DESC
        """
        
        return self.db.query_issues(query, [days_back])
    
    def get_repository_issues(self, org: str, repo: str) -> List[Dict[str, Any]]:
        """Get all issues from a specific repository for update."""
        query = """
            SELECT i.*
            FROM issues i
            WHERE i.org = ? AND i.repo = ?
            ORDER BY 
                CASE WHEN i.state != 'closed' THEN 1 ELSE 2 END,
                i.updated_at DESC
        """
        
        return self.db.query_issues(query, [org, repo])
    
    def get_smart_update_candidates(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Intelligent selection combining multiple strategies."""
        query = """
            SELECT 
                i.*,
                CASE 
                    WHEN i.state = 'open' AND julianday('now') - julianday(i.updated_at) <= 1 THEN 1
                    WHEN i.state = 'open' AND julianday('now') - julianday(i.collection_timestamp) >= 3 THEN 2
                    WHEN i.state != 'closed' THEN 3
                    WHEN julianday('now') - julianday(i.collection_timestamp) >= 14 THEN 4
                    ELSE 5
                END as update_priority,
                julianday('now') - julianday(i.collection_timestamp) as days_since_collection
            FROM issues i
            WHERE update_priority <= 4  -- Exclude lowest priority
            ORDER BY update_priority ASC, days_since_collection DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.db.query_issues(query)
```

### **Issue Updater**
```python
# updater.py
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json

from rich.console import Console
from rich.progress import track, Progress, TaskID

from ..github_client.client import GitHubClient
from ..storage.manager import StorageManager
from ..storage.database import DatabaseManager
from .changes import ChangeTracker
from .strategy import UpdateStrategy

console = Console()


class IssueUpdater:
    """Handles updating previously collected GitHub issues."""
    
    def __init__(self, 
                 github_client: GitHubClient = None,
                 storage: StorageManager = None,
                 db: DatabaseManager = None):
        self.github_client = github_client or GitHubClient()
        self.storage = storage or StorageManager()
        self.db = db or DatabaseManager()
        self.strategy = UpdateStrategy(self.db)
        self.change_tracker = ChangeTracker(self.db)
    
    async def update_non_closed_issues(self, 
                                     limit: Optional[int] = None,
                                     max_age_days: Optional[int] = None,
                                     dry_run: bool = False) -> Dict[str, int]:
        """Update all issues that were not 'closed' when last seen.
        
        This is the core verified feature.
        """
        console.print("[blue]Finding non-closed issues to update...[/blue]")
        
        candidates = self.strategy.get_non_closed_issues(max_age_days)
        
        if limit:
            candidates = candidates[:limit]
        
        if not candidates:
            console.print("[yellow]No non-closed issues found to update[/yellow]")
            return {"checked": 0, "updated": 0, "unchanged": 0, "errors": 0}
        
        console.print(f"[blue]Found {len(candidates)} non-closed issues to check[/blue]")
        
        if dry_run:
            console.print("[yellow]Dry run - showing what would be updated:[/yellow]")
            for issue in candidates[:10]:  # Show first 10
                days_old = (datetime.now() - datetime.fromisoformat(issue['collection_timestamp'])).days
                console.print(f"  {issue['org']}/{issue['repo']}#{issue['number']} - {issue['state']} ({days_old}d old)")
            if len(candidates) > 10:
                console.print(f"  ... and {len(candidates) - 10} more")
            return {"checked": len(candidates), "updated": 0, "unchanged": 0, "errors": 0}
        
        return await self._update_issues_batch(candidates, "non_closed_issues")
    
    async def update_stale_issues(self, 
                                days_threshold: int = 7,
                                limit: Optional[int] = None,
                                dry_run: bool = False) -> Dict[str, int]:
        """Update issues that haven't been refreshed in X days."""
        console.print(f"[blue]Finding issues stale for >{days_threshold} days...[/blue]")
        
        candidates = self.strategy.get_stale_issues(days_threshold)
        
        if limit:
            candidates = candidates[:limit]
        
        if not candidates:
            console.print(f"[yellow]No issues found stale for >{days_threshold} days[/yellow]")
            return {"checked": 0, "updated": 0, "unchanged": 0, "errors": 0}
        
        console.print(f"[blue]Found {len(candidates)} stale issues[/blue]")
        
        if dry_run:
            return {"checked": len(candidates), "updated": 0, "unchanged": 0, "errors": 0}
        
        return await self._update_issues_batch(candidates, "stale_issues")
    
    async def update_repository(self, 
                              org: str, 
                              repo: str,
                              limit: Optional[int] = None,
                              dry_run: bool = False) -> Dict[str, int]:
        """Update all issues from a specific repository."""
        console.print(f"[blue]Finding issues from {org}/{repo}...[/blue]")
        
        candidates = self.strategy.get_repository_issues(org, repo)
        
        if limit:
            candidates = candidates[:limit]
        
        if not candidates:
            console.print(f"[yellow]No issues found for {org}/{repo}[/yellow]")
            return {"checked": 0, "updated": 0, "unchanged": 0, "errors": 0}
        
        console.print(f"[blue]Found {len(candidates)} issues from {org}/{repo}[/blue]")
        
        if dry_run:
            return {"checked": len(candidates), "updated": 0, "unchanged": 0, "errors": 0}
        
        return await self._update_issues_batch(candidates, "repository", {"org": org, "repo": repo})
    
    async def smart_update(self, 
                          limit: Optional[int] = 50,
                          dry_run: bool = False) -> Dict[str, int]:
        """Intelligent update using combined strategies."""
        console.print("[blue]Running smart update strategy...[/blue]")
        
        candidates = self.strategy.get_smart_update_candidates(limit)
        
        if not candidates:
            console.print("[yellow]No update candidates found[/yellow]")
            return {"checked": 0, "updated": 0, "unchanged": 0, "errors": 0}
        
        console.print(f"[blue]Selected {len(candidates)} issues for smart update[/blue]")
        
        if dry_run:
            return {"checked": len(candidates), "updated": 0, "unchanged": 0, "errors": 0}
        
        return await self._update_issues_batch(candidates, "smart_update")
    
    async def _update_issues_batch(self, 
                                 issues: List[Dict[str, Any]], 
                                 sync_type: str,
                                 filter_criteria: Dict[str, Any] = None) -> Dict[str, int]:
        """Update a batch of issues with progress tracking."""
        stats = {"checked": 0, "updated": 0, "unchanged": 0, "errors": 0}
        
        # Start sync history record
        sync_id = self._start_sync_history(sync_type, len(issues), filter_criteria)
        
        with Progress() as progress:
            task = progress.add_task("Updating issues...", total=len(issues))
            
            for issue_row in issues:
                try:
                    stats["checked"] += 1
                    
                    # Fetch current issue from GitHub
                    current_issue = await self.github_client.get_issue(
                        issue_row['org'], 
                        issue_row['repo'], 
                        issue_row['number']
                    )
                    
                    if not current_issue:
                        stats["errors"] += 1
                        continue
                    
                    # Compare and detect changes
                    changes = self.change_tracker.detect_changes(issue_row, current_issue)
                    
                    if changes:
                        # Save updated issue
                        await self._save_updated_issue(issue_row, current_issue, changes)
                        stats["updated"] += 1
                        
                        console.print(f"[green]✓ Updated {issue_row['org']}/{issue_row['repo']}#{issue_row['number']} - {len(changes)} changes[/green]")
                    else:
                        stats["unchanged"] += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)  # 100ms between requests
                    
                except Exception as e:
                    console.print(f"[red]✗ Failed to update {issue_row['org']}/{issue_row['repo']}#{issue_row['number']}: {e}[/red]")
                    stats["errors"] += 1
                
                finally:
                    progress.update(task, advance=1)
        
        # Complete sync history record
        self._complete_sync_history(sync_id, stats)
        
        return stats
    
    async def _save_updated_issue(self, 
                                old_issue_row: Dict[str, Any], 
                                new_issue: Any,
                                changes: List[Dict[str, Any]]):
        """Save updated issue and track changes."""
        # Save to JSON storage (updates database automatically)
        self.storage.save_issue(
            old_issue_row['org'],
            old_issue_row['repo'], 
            new_issue,
            metadata={"update_timestamp": datetime.now().isoformat()}
        )
        
        # Record changes
        for change in changes:
            self.change_tracker.record_change(
                old_issue_row['id'],
                change['type'],
                change.get('field'),
                change.get('old_value'),
                change.get('new_value')
            )
    
    def _start_sync_history(self, 
                          sync_type: str, 
                          issue_count: int, 
                          filter_criteria: Dict[str, Any] = None) -> int:
        """Start a sync history record."""
        return self.db.conn.execute('''
            INSERT INTO sync_history 
            (sync_type, issues_checked, issues_updated, issues_unchanged, started_at, filter_criteria)
            VALUES (?, ?, 0, 0, ?, ?)
            RETURNING id
        ''', [
            sync_type, issue_count, datetime.now(), 
            json.dumps(filter_criteria) if filter_criteria else None
        ]).fetchone()[0]
    
    def _complete_sync_history(self, sync_id: int, stats: Dict[str, int]):
        """Complete a sync history record."""
        self.db.conn.execute('''
            UPDATE sync_history
            SET issues_updated = ?, issues_unchanged = ?, errors_count = ?, completed_at = ?
            WHERE id = ?
        ''', [
            stats['updated'], stats['unchanged'], stats['errors'], 
            datetime.now(), sync_id
        ])
```

### **Change Tracking**
```python
# changes.py
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from ..storage.database import DatabaseManager


class ChangeTracker:
    """Tracks and analyzes changes between issue versions."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def detect_changes(self, 
                      old_issue_row: Dict[str, Any], 
                      new_issue: Any) -> List[Dict[str, Any]]:
        """Detect changes between old and new issue versions."""
        changes = []
        
        # State change (most important)
        if old_issue_row['state'] != new_issue.state:
            changes.append({
                'type': 'state_change',
                'field': 'state',
                'old_value': old_issue_row['state'],
                'new_value': new_issue.state,
                'significance': 'high'  # State changes are always significant
            })
        
        # Title change
        if old_issue_row['title'] != new_issue.title:
            changes.append({
                'type': 'field_change',
                'field': 'title',
                'old_value': old_issue_row['title'],
                'new_value': new_issue.title,
                'significance': 'medium'
            })
        
        # Body change (check for substantial changes)
        old_body = old_issue_row.get('body', '') or ''
        new_body = new_issue.body or ''
        if old_body != new_body:
            # Only record if change is substantial (>10% difference)
            if abs(len(old_body) - len(new_body)) > max(len(old_body), len(new_body)) * 0.1:
                changes.append({
                    'type': 'field_change',
                    'field': 'body',
                    'old_value': old_body[:200] + '...' if len(old_body) > 200 else old_body,
                    'new_value': new_body[:200] + '...' if len(new_body) > 200 else new_body,
                    'significance': 'medium'
                })
        
        # Updated timestamp change
        old_updated = old_issue_row['updated_at']
        new_updated = new_issue.updated_at.isoformat()
        if old_updated != new_updated:
            changes.append({
                'type': 'field_change',
                'field': 'updated_at',
                'old_value': old_updated,
                'new_value': new_updated,
                'significance': 'low'
            })
        
        # Label changes (would require loading and comparing labels)
        # TODO: Implement label change detection
        
        # Comment count changes (would require loading comments)
        # TODO: Implement comment change detection
        
        return changes
    
    def record_change(self, 
                     issue_id: int,
                     update_type: str,
                     field_name: Optional[str] = None,
                     old_value: Optional[str] = None,
                     new_value: Optional[str] = None):
        """Record a change in the database."""
        self.db.conn.execute('''
            INSERT INTO issue_updates 
            (issue_id, update_type, field_name, old_value, new_value, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', [
            issue_id, update_type, field_name, old_value, new_value, datetime.now()
        ])
    
    def get_issue_changes(self, issue_id: int) -> List[Dict[str, Any]]:
        """Get all changes for a specific issue."""
        return self.db.query_issues('''
            SELECT * FROM issue_updates 
            WHERE issue_id = ?
            ORDER BY updated_at DESC
        ''', [issue_id])
    
    def get_recent_changes(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get all changes in the last N days."""
        return self.db.query_issues('''
            SELECT 
                iu.*,
                i.org,
                i.repo,
                i.number,
                i.title
            FROM issue_updates iu
            JOIN issues i ON iu.issue_id = i.id
            WHERE julianday('now') - julianday(iu.updated_at) <= ?
            ORDER BY iu.updated_at DESC
        ''', [days])
```

### **CLI Update Commands**
```python
# update.py
import typer
import asyncio
from typing import Optional

from rich.console import Console
from rich.table import Table

from ..sync.updater import IssueUpdater
from ..storage.database import DatabaseManager

console = Console()
app = typer.Typer(help="Update previously collected GitHub issues")


@app.command()
def open_issues(
    limit: Optional[int] = typer.Option(None, help="Maximum number of issues to update"),
    max_age_days: Optional[int] = typer.Option(None, help="Only update issues collected within N days"),
    dry_run: bool = typer.Option(False, help="Show what would be updated without making changes")
):
    """Update all issues that were not 'closed' when last collected.
    
    This checks if any previously open/pending issues have been closed.
    """
    asyncio.run(_update_open_issues(limit, max_age_days, dry_run))


@app.command()
def stale(
    days: int = typer.Option(7, help="Update issues not refreshed in N days"),
    limit: Optional[int] = typer.Option(None, help="Maximum number of issues to update"),
    dry_run: bool = typer.Option(False, help="Show what would be updated")
):
    """Update issues that haven't been refreshed recently."""
    asyncio.run(_update_stale_issues(days, limit, dry_run))


@app.command()
def repo(
    org: str = typer.Argument(..., help="Organization name"),
    repo: str = typer.Argument(..., help="Repository name"),
    limit: Optional[int] = typer.Option(None, help="Maximum number of issues to update"),
    dry_run: bool = typer.Option(False, help="Show what would be updated")
):
    """Update all issues from a specific repository."""
    asyncio.run(_update_repository(org, repo, limit, dry_run))


@app.command()
def smart(
    limit: int = typer.Option(50, help="Maximum number of issues to update"),
    dry_run: bool = typer.Option(False, help="Show what would be updated")
):
    """Intelligent update using prioritization strategy."""
    asyncio.run(_update_smart(limit, dry_run))


@app.command()
def history(
    days: int = typer.Option(7, help="Show sync history for last N days"),
    detailed: bool = typer.Option(False, help="Show detailed change information")
):
    """Show update history and statistics."""
    _show_update_history(days, detailed)


@app.command()
def changes(
    days: int = typer.Option(7, help="Show changes detected in last N days"),
    org: Optional[str] = typer.Option(None, help="Filter by organization"),
    repo: Optional[str] = typer.Option(None, help="Filter by repository")
):
    """Show recent changes detected during updates."""
    _show_recent_changes(days, org, repo)


async def _update_open_issues(limit: Optional[int], max_age_days: Optional[int], dry_run: bool):
    """Update non-closed issues."""
    updater = IssueUpdater()
    
    console.print("[bold blue]Updating Non-Closed Issues[/bold blue]")
    console.print("This will check if any previously open/pending issues have been closed.")
    
    if not dry_run and not typer.confirm("Continue with update?"):
        return
    
    stats = await updater.update_non_closed_issues(limit, max_age_days, dry_run)
    _show_update_stats(stats)


async def _update_stale_issues(days: int, limit: Optional[int], dry_run: bool):
    """Update stale issues."""
    updater = IssueUpdater()
    
    console.print(f"[bold blue]Updating Stale Issues (>{days} days)[/bold blue]")
    
    if not dry_run and not typer.confirm("Continue with update?"):
        return
    
    stats = await updater.update_stale_issues(days, limit, dry_run)
    _show_update_stats(stats)


async def _update_repository(org: str, repo: str, limit: Optional[int], dry_run: bool):
    """Update repository issues."""
    updater = IssueUpdater()
    
    console.print(f"[bold blue]Updating {org}/{repo} Issues[/bold blue]")
    
    if not dry_run and not typer.confirm("Continue with update?"):
        return
    
    stats = await updater.update_repository(org, repo, limit, dry_run)
    _show_update_stats(stats)


async def _update_smart(limit: int, dry_run: bool):
    """Smart update."""
    updater = IssueUpdater()
    
    console.print("[bold blue]Smart Update Strategy[/bold blue]")
    console.print("Prioritizes recently active and non-closed issues.")
    
    if not dry_run and not typer.confirm("Continue with update?"):
        return
    
    stats = await updater.smart_update(limit, dry_run)
    _show_update_stats(stats)


def _show_update_stats(stats: Dict[str, int]):
    """Display update statistics."""
    table = Table(title="Update Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="white")
    
    table.add_row("Issues Checked", str(stats['checked']))
    table.add_row("Issues Updated", str(stats['updated']))
    table.add_row("Issues Unchanged", str(stats['unchanged']))
    table.add_row("Errors", str(stats['errors']))
    
    console.print(table)
    
    if stats['updated'] > 0:
        console.print(f"[green]✅ Successfully updated {stats['updated']} issues[/green]")
    if stats['errors'] > 0:
        console.print(f"[red]⚠️ {stats['errors']} errors occurred[/red]")


def _show_update_history(days: int, detailed: bool):
    """Show sync history."""
    try:
        db = DatabaseManager()
        
        history = db.query_issues('''
            SELECT * FROM sync_history
            WHERE julianday('now') - julianday(started_at) <= ?
            ORDER BY started_at DESC
        ''', [days])
        
        if not history:
            console.print(f"[yellow]No sync history found for last {days} days[/yellow]")
            return
        
        table = Table(title=f"Sync History - Last {days} Days")
        table.add_column("Date", style="cyan")
        table.add_column("Type", style="white")
        table.add_column("Checked", style="blue")
        table.add_column("Updated", style="green")
        table.add_column("Errors", style="red")
        table.add_column("Duration", style="dim")
        
        for record in history:
            duration = "In progress"
            if record['completed_at']:
                start = datetime.fromisoformat(record['started_at'])
                end = datetime.fromisoformat(record['completed_at'])
                duration = f"{(end - start).total_seconds():.1f}s"
            
            table.add_row(
                record['started_at'][:10],
                record['sync_type'],
                str(record['issues_checked']),
                str(record['issues_updated']),
                str(record['errors_count']),
                duration
            )
        
        console.print(table)
        
    except ImportError:
        console.print("[red]Database not available[/red]")


def _show_recent_changes(days: int, org: Optional[str], repo: Optional[str]):
    """Show recent changes."""
    try:
        from ..sync.changes import ChangeTracker
        
        db = DatabaseManager()
        tracker = ChangeTracker(db)
        
        changes = tracker.get_recent_changes(days)
        
        # Filter by org/repo if specified
        if org or repo:
            changes = [
                c for c in changes 
                if (not org or c['org'] == org) and (not repo or c['repo'] == repo)
            ]
        
        if not changes:
            console.print(f"[yellow]No changes found for last {days} days[/yellow]")
            return
        
        table = Table(title=f"Recent Changes - Last {days} Days")
        table.add_column("Date", style="cyan")
        table.add_column("Issue", style="white")
        table.add_column("Change Type", style="blue")
        table.add_column("Field", style="dim")
        table.add_column("Change", style="green")
        
        for change in changes[:20]:  # Show first 20
            issue_ref = f"{change['org']}/{change['repo']}#{change['number']}"
            
            change_desc = ""
            if change['field_name'] and change['old_value'] and change['new_value']:
                old_val = change['old_value'][:20] + "..." if len(change['old_value']) > 20 else change['old_value']
                new_val = change['new_value'][:20] + "..." if len(change['new_value']) > 20 else change['new_value']
                change_desc = f"{old_val} → {new_val}"
            
            table.add_row(
                change['updated_at'][:10],
                issue_ref,
                change['update_type'],
                change['field_name'] or "",
                change_desc
            )
        
        console.print(table)
        
        if len(changes) > 20:
            console.print(f"[dim]... and {len(changes) - 20} more changes[/dim]")
        
    except ImportError:
        console.print("[red]Database not available[/red]")
```

### **CLI Integration**
```python
# Modify cli/main.py
from .update import app as update_app

app.add_typer(update_app, name="update", help="Update previously collected issues")

# Enhanced status command to show update info
@app.command()
def status():
    """Show storage statistics including update status."""
    # ... existing status code ...
    
    # Add update history summary
    if storage.db:
        try:
            recent_syncs = storage.db.query_issues('''
                SELECT COUNT(*) as sync_count, 
                       SUM(issues_updated) as total_updated,
                       MAX(started_at) as last_sync
                FROM sync_history
                WHERE julianday('now') - julianday(started_at) <= 7
            ''')
            
            if recent_syncs and recent_syncs[0]['sync_count'] > 0:
                sync_info = recent_syncs[0]
                table.add_row("", "")  # Separator
                table.add_row("Recent Syncs (7d)", str(sync_info['sync_count']))
                table.add_row("Issues Updated (7d)", str(sync_info['total_updated'] or 0))
                table.add_row("Last Sync", sync_info['last_sync'][:10] if sync_info['last_sync'] else "Never")
        except Exception:
            pass  # Ignore if sync tables don't exist yet
```

## Testing Strategy

```python
# test_updater.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from github_issue_analysis.sync.updater import IssueUpdater
from github_issue_analysis.sync.strategy import UpdateStrategy


class TestIssueUpdater:
    @pytest.fixture
    def mock_updater(self):
        """Create updater with mocked dependencies."""
        github_client = AsyncMock()
        storage = MagicMock()
        db = MagicMock()
        
        updater = IssueUpdater(github_client, storage, db)
        return updater, github_client, storage, db
    
    @pytest.mark.asyncio
    async def test_update_non_closed_issues(self, mock_updater):
        """Test core feature: updating non-closed issues."""
        updater, github_client, storage, db = mock_updater
        
        # Mock strategy to return non-closed issues
        updater.strategy.get_non_closed_issues = MagicMock(return_value=[
            {
                'id': 1,
                'org': 'test-org',
                'repo': 'test-repo',
                'number': 123,
                'state': 'open',
                'collection_timestamp': '2024-01-01T00:00:00'
            }
        ])
        
        # Mock GitHub API response
        github_client.get_issue.return_value = MagicMock(
            state='closed',  # Issue was closed since last collection
            title='Test Issue',
            body='Test body',
            updated_at=datetime.now()
        )
        
        # Mock change detection
        updater.change_tracker.detect_changes = MagicMock(return_value=[
            {
                'type': 'state_change',
                'field': 'state',
                'old_value': 'open',
                'new_value': 'closed'
            }
        ])
        
        # Run update
        stats = await updater.update_non_closed_issues(limit=1)
        
        # Verify results
        assert stats['checked'] == 1
        assert stats['updated'] == 1
        assert stats['unchanged'] == 0
        assert stats['errors'] == 0
        
        # Verify GitHub API was called
        github_client.get_issue.assert_called_once_with('test-org', 'test-repo', 123)
        
        # Verify issue was saved
        storage.save_issue.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dry_run_no_api_calls(self, mock_updater):
        """Test dry run doesn't make API calls."""
        updater, github_client, storage, db = mock_updater
        
        updater.strategy.get_non_closed_issues = MagicMock(return_value=[
            {'id': 1, 'org': 'test', 'repo': 'test', 'number': 1, 'state': 'open'}
        ])
        
        stats = await updater.update_non_closed_issues(dry_run=True)
        
        # Verify no API calls made
        github_client.get_issue.assert_not_called()
        storage.save_issue.assert_not_called()
        
        # But should return what would be checked
        assert stats['checked'] == 1


# test_strategy.py  
class TestUpdateStrategy:
    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.query_issues = MagicMock()
        return db
    
    def test_get_non_closed_issues(self, mock_db):
        """Test non-closed issue selection."""
        strategy = UpdateStrategy(mock_db)
        
        mock_db.query_issues.return_value = [
            {'id': 1, 'state': 'open', 'number': 1},
            {'id': 2, 'state': 'pending', 'number': 2}
        ]
        
        result = strategy.get_non_closed_issues()
        
        # Verify correct SQL query was called
        args, kwargs = mock_db.query_issues.call_args
        sql = args[0]
        assert "WHERE i.state != 'closed'" in sql
        assert "ORDER BY update_priority ASC" in sql
        
        assert len(result) == 2
    
    def test_get_non_closed_issues_with_age_limit(self, mock_db):
        """Test non-closed issue selection with age limit."""
        strategy = UpdateStrategy(mock_db)
        
        strategy.get_non_closed_issues(max_age_days=30)
        
        # Verify age filter was added to query
        args, kwargs = mock_db.query_issues.call_args
        sql = args[0]
        params = args[1]
        
        assert "julianday('now') - julianday(i.collection_timestamp) <= ?" in sql
        assert params == [30]
```

## Validation Steps

### **Setup and Preparation**
```bash
# 1. Ensure DuckDB Phase 1 is working with some data
uv run gh-analysis status

# 2. Collect some test issues (mix of open/closed)
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 5
```

### **Core Feature Testing: Non-Closed Issues**
```bash
# 3. Test the verified feature - update non-closed issues (dry run first)
uv run gh-analysis update open-issues --dry-run
uv run gh-analysis update open-issues --limit 3

# 4. Verify changes detected
uv run gh-analysis update changes --days 1

# 5. Check sync history
uv run gh-analysis update history --days 1
```

### **Additional Update Strategies**
```bash
# 6. Test stale issue updates
uv run gh-analysis update stale --days 1 --limit 2 --dry-run
uv run gh-analysis update stale --days 1 --limit 2

# 7. Test repository updates
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis update repo USER_PROVIDED_ORG USER_PROVIDED_REPO --limit 2 --dry-run

# 8. Test smart update strategy
uv run gh-analysis update smart --limit 5 --dry-run
```

### **Data Verification**
```bash
# 9. Query updated issues
uv run gh-analysis query sql "SELECT org, repo, number, state, collection_timestamp FROM issues ORDER BY collection_timestamp DESC LIMIT 5"

# 10. Check for state changes
uv run gh-analysis query sql "SELECT COUNT(*) FROM issue_updates WHERE update_type = 'state_change'"

# 11. Verify sync tracking
uv run gh-analysis query sql "SELECT sync_type, COUNT(*) FROM sync_history GROUP BY sync_type"
```

### **Quality Assurance**
```bash
# 12. Run tests
uv run pytest tests/test_sync/ -v

# 13. Quality checks
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

## Acceptance Criteria
- [ ] Update strategy engine with prioritization algorithms
- [ ] **Verified Feature**: Update issues that were not 'closed' when last seen
- [ ] Issue updater with batch processing and rate limiting  
- [ ] Change detection and tracking system
- [ ] Update history and sync statistics
- [ ] CLI commands for all update strategies (open-issues, stale, repo, smart)
- [ ] Dry run support for all update operations
- [ ] Progress tracking and error handling
- [ ] Database schema for change tracking and sync history
- [ ] Integration with existing storage and database systems
- [ ] Comprehensive test coverage for update logic
- [ ] Performance optimization for large update batches

**Success Metrics**:
1. `uv run gh-analysis update open-issues` successfully finds and updates previously non-closed issues
2. Change detection accurately identifies state changes (open→closed, etc.)
3. Update history shows clear audit trail of sync operations
4. Smart update strategy efficiently prioritizes most important issues
5. Rate limiting prevents GitHub API abuse during large updates

**Core Verified Feature**: The system must successfully identify and update issues that were 'open', 'pending', or any non-'closed' state when last collected, checking if they have since been closed or had other changes.

## Agent Notes
[Document your implementation approach, design decisions, and any challenges encountered during development]

## Implementation Notes

**Focus Areas:**
1. **Core Feature**: Non-closed issue updates with state change detection
2. **Performance**: Efficient batch processing with rate limiting
3. **Tracking**: Comprehensive change detection and audit trail
4. **User Experience**: Clear progress reporting and dry-run capabilities

**Integration Points:**
- Builds on DuckDB Phase 1 database foundation
- Works with existing GitHub client and storage systems
- Designed for future AI processing integration

This completes the DuckDB integration trilogy with powerful synchronization capabilities for keeping issue data fresh and current.