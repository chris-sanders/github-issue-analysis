# Task: Storage and Querying System

**Status:** not started

**Description:**
Enhance storage capabilities with filtering, querying, and data management utilities. Add CLI commands to list, filter, and manage collected issues and results.

**Prerequisites:**
- `github-issue-collection.md` must be completed first
- Requires existing storage manager foundation

**Files to Create:**
- `github_issue_analysis/storage/query.py` - Issue filtering and querying
- `github_issue_analysis/cli/list.py` - CLI list/query commands
- `github_issue_analysis/cli/clean.py` - Data management commands
- `tests/test_storage/test_query.py` - Query system tests

**Files to Modify:**
- `github_issue_analysis/storage/manager.py` - Add batch loading methods
- `github_issue_analysis/cli/main.py` - Add list and clean commands
- `github_issue_analysis/storage/__init__.py` - Export query functions

**Implementation Details:**

**Query System Design:**
```python
class IssueFilter(BaseModel):
    org: Optional[str] = None
    repo: Optional[str] = None
    labels: Optional[List[str]] = None
    state: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    title_contains: Optional[str] = None
    
class IssueQuery:
    def __init__(self, data_dir: Path = Path("data")):
        self.issues_dir = data_dir / "issues"
        self.results_dir = data_dir / "results"
    
    def find_issues(self, filter: IssueFilter) -> List[StoredIssue]:
        """Load and filter issues based on criteria."""
        
    def count_issues(self, filter: IssueFilter) -> int:
        """Count issues matching filter without loading them."""
        
    def list_orgs_repos(self) -> Dict[str, List[str]]:
        """Get available org/repo combinations."""
        
    def get_issue_stats(self) -> Dict[str, Any]:
        """Get statistics about collected issues."""
```

**Batch Loading:**
```python
class StorageManager:
    def load_issues_batch(self, 
                         filter: IssueFilter, 
                         limit: Optional[int] = None) -> Iterator[StoredIssue]:
        """Memory-efficient batch loading of issues."""
        
    def load_results_for_issues(self, 
                               issues: List[StoredIssue],
                               processor: str) -> Dict[int, Dict]:
        """Load AI results for specific issues."""
```

**CLI Commands:**

**List Command:**
```bash
uv run gh-analysis list --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO
uv run gh-analysis list --labels bug,enhancement --state open
uv run gh-analysis list --created-after 2024-01-01 --count-only
uv run gh-analysis list --title-contains "crash" --limit 10
```

**Stats Command:**
```bash  
uv run gh-analysis stats
uv run gh-analysis stats --org USER_PROVIDED_ORG
```

**Clean Command:**
```bash
uv run gh-analysis clean --dry-run
uv run gh-analysis clean --older-than 30d
uv run gh-analysis clean --repo archived-repo
```

**CLI Implementation:**
```python
# list.py
@app.command()
def list_issues(
    org: Optional[str] = None,
    repo: Optional[str] = None,
    labels: Optional[str] = None,  # comma-separated
    state: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    title_contains: Optional[str] = None,
    count_only: bool = False,
    limit: Optional[int] = None,
):
    """List collected issues with filtering."""

@app.command() 
def stats():
    """Show statistics about collected data."""
```

**Output Formatting:**
Use Rich tables for list output:
```python
from rich.table import Table
from rich.console import Console

def display_issues(issues: List[StoredIssue]):
    table = Table()
    table.add_column("Issue")
    table.add_column("Title")  
    table.add_column("Labels")
    table.add_column("State")
    table.add_column("Created")
    
    for issue in issues:
        table.add_row(
            f"{issue.org}/{issue.repo}#{issue.issue.number}",
            issue.issue.title[:50] + "..." if len(issue.issue.title) > 50 else issue.issue.title,
            ", ".join([l.name for l in issue.issue.labels[:3]]),
            issue.issue.state,
            issue.issue.created_at.strftime("%Y-%m-%d")
        )
```

**Data Validation:**
Add validation for existing data files:
```python
def validate_issue_file(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate issue JSON file format."""
    try:
        with open(file_path) as f:
            data = json.load(f)
        StoredIssue.model_validate(data)
        return True, None
    except Exception as e:
        return False, str(e)

def validate_all_issues() -> Dict[str, List[str]]:
    """Validate all issue files and return errors."""
```

**Performance Considerations:**
- Use file metadata (filename parsing) for basic filtering before loading JSON
- Implement pagination for large result sets
- Cache frequently accessed data (org/repo lists)
- Stream processing for memory efficiency

**Acceptance Criteria:**
- [ ] IssueFilter and IssueQuery classes with comprehensive filtering
- [ ] CLI list command with all filter options and rich output formatting
- [ ] CLI stats command showing data overview and counts
- [ ] CLI clean command with dry-run and selective cleanup
- [ ] Batch loading methods for memory-efficient processing  
- [ ] Data validation utilities for existing files
- [ ] Performance optimization for large datasets (1000+ issues)
- [ ] Comprehensive test coverage with sample data fixtures
- [ ] Code quality checks pass (ruff, black, mypy)

**Agent Notes:**
[Document your query design decisions, performance optimizations, and CLI interface choices]

**Validation:**
- Ensure issues collected first: `uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 10`
- Test listing: `uv run gh-analysis list --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO`
- Test filtering: `uv run gh-analysis list --labels bug --state open --limit 5`
- Test stats: `uv run gh-analysis stats`
- Test count-only: `uv run gh-analysis list --count-only`
- Test clean dry-run: `uv run gh-analysis clean --dry-run`
- Verify performance with larger datasets (100+ issues)
- Ensure all tests pass: `uv run pytest tests/test_storage/ -v`
- Verify code quality: `uv run ruff check && uv run black . && uv run mypy .`