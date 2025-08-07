# Task: Enable Collection Based on Date Ranges

**Status:** complete

**Description:**
Enable GitHub issue collection based on date ranges (e.g., "collect all issues in the last 6 months") by extending the existing collect command with date filtering capabilities.

**Current State Analysis:**
- ✅ `build_github_query()` already supports `created_after` parameter (search.py:93)
- ✅ GitHub search API supports comprehensive date filtering 
- ❌ CLI collect command doesn't expose date parameters
- ❌ No date parsing/validation utilities
- ❌ Limited to created_after, needs created_before and updated date support

**Acceptance Criteria:**
- [ ] Add `--created-after`, `--created-before`, `--updated-after`, `--updated-before` CLI options
- [ ] Add `--last-days`, `--last-weeks`, `--last-months` convenience options  
- [ ] Support flexible date formats: ISO dates, relative dates, human-readable formats
- [ ] Extend GitHubClient methods to accept date parameters
- [ ] Update search query building for all date filter combinations
- [ ] Add comprehensive date validation with clear error messages
- [ ] Update help text and examples with date filtering usage
- [ ] **Update documentation files with date filtering examples and usage**
- [ ] Tests for date parsing, validation, and API integration
- [ ] All existing functionality remains unchanged
- [ ] Quality checks pass: `uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`

**Implementation Plan:**

### Phase 1: CLI Interface Enhancement
**Files to modify:**
- `github_issue_analysis/cli/collect.py` - Add date range parameters

**New CLI Options:**
```bash
# Absolute date filtering
--created-after YYYY-MM-DD     # Issues created after date
--created-before YYYY-MM-DD    # Issues created before date  
--updated-after YYYY-MM-DD     # Issues updated after date
--updated-before YYYY-MM-DD    # Issues updated before date

# Relative date convenience options
--last-days INTEGER             # Issues from last N days
--last-weeks INTEGER            # Issues from last N weeks  
--last-months INTEGER           # Issues from last N months
```

**Usage Examples:**
```bash
# Absolute date ranges
uv run gh-analysis collect --org myorg --created-after 2024-01-01 --created-before 2024-06-30

# Last 6 months (convenience option)
uv run gh-analysis collect --org myorg --last-months 6

# Combined with existing filters
uv run gh-analysis collect --org myorg --repo myrepo --labels bug --last-weeks 2

# Updated date filtering
uv run gh-analysis collect --org myorg --updated-after 2024-01-01
```

### Phase 2: Date Parsing and Validation
**New file:**
- `github_issue_analysis/utils/date_parser.py` - Date parsing and validation utilities

**Functionality:**
```python
def parse_date_input(date_str: str) -> datetime:
    """Parse various date formats into datetime objects."""
    
def validate_date_range(start: datetime | None, end: datetime | None) -> None:
    """Validate date range logic."""
    
def relative_date_to_absolute(days: int = None, weeks: int = None, months: int = None) -> datetime:
    """Convert relative dates to absolute dates."""
```

**Supported Formats:**
- ISO dates: `2024-01-01`, `2024-01-01T10:00:00Z`
- Human readable: `January 1, 2024`, `Jan 1 2024`
- Relative: `--last-days 30`, `--last-months 6`

### Phase 3: Search Query Enhancement  
**Files to modify:**
- `github_issue_analysis/github_client/search.py` - Extend query building
- `github_issue_analysis/github_client/client.py` - Pass date parameters through API calls

**Enhanced Query Building:**
```python
def build_github_query(
    org: str,
    repo: str,
    labels: list[str] | None = None,
    state: str = "open", 
    created_after: str | None = None,
    created_before: str | None = None,    # NEW
    updated_after: str | None = None,     # NEW  
    updated_before: str | None = None,    # NEW
) -> str:
```

**GitHub API Date Query Examples:**
```
created:>2024-01-01                    # After date
created:<2024-12-31                    # Before date  
created:2024-01-01..2024-12-31        # Date range
updated:>2024-01-01                    # Updated after
is:issue created:>2024-01-01 updated:<2024-12-31  # Combined filters
```

### Phase 4: Documentation Updates
**Files to modify:**
- `docs/api-reference.md` - Add date filtering options to collect command documentation
- `CLAUDE.md` - Update CLI usage examples with date filtering
- CLI help text in `collect.py` - Comprehensive help for new date options

**Documentation Requirements:**
- Update collect command examples with date filtering use cases
- Add date format specification and validation rules
- Include common use case examples (last N months, specific date ranges)
- Update CLI reference with all new date-related parameters
- Add troubleshooting section for date parsing errors

### Phase 5: Integration and Testing
**Files to modify:**
- `github_issue_analysis/github_client/client.py` - Update all search methods
- `github_issue_analysis/github_client/models.py` - Add date fields if needed

**New test files:**
- `tests/test_utils/test_date_parser.py` - Date parsing tests
- `tests/test_cli/test_collect_dates.py` - CLI date integration tests  
- `tests/test_github_client/test_search_dates.py` - Search query tests

**Test Coverage:**
- Valid and invalid date format parsing
- Date range validation (start before end, not future dates, etc.)
- Relative date calculations  
- GitHub query building with various date combinations
- CLI parameter combinations and edge cases
- Integration with existing filters (labels, state, etc.)

**Error Handling:**
- Invalid date formats → clear error messages with examples
- Invalid date ranges → specific validation errors
- Future dates → warnings or rejections
- Conflicting parameters → clear precedence rules

**Validation Steps:**

### Setup and Basic Testing
```bash
# 1. Test absolute date filtering
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --created-after 2024-01-01 --limit 5

# 2. Test relative dates
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --last-months 3 --limit 5

# 3. Test date ranges
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --created-after 2024-01-01 --created-before 2024-06-30 --limit 5

# 4. Test updated date filtering
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --updated-after 2024-01-01 --limit 5

# 5. Combine with existing filters
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --labels bug --last-weeks 4 --limit 5
```

### Edge Case Testing
```bash
# 6. Test invalid date formats
uv run gh-analysis collect --org test --created-after "invalid-date"

# 7. Test invalid date ranges  
uv run gh-analysis collect --org test --created-after 2024-12-31 --created-before 2024-01-01

# 8. Test parameter conflicts
uv run gh-analysis collect --org test --created-after 2024-01-01 --last-months 6

# 9. Test organization-wide with dates
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --last-months 1 --limit 10

# 10. Verify existing functionality unchanged
# Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER
```

### Quality Assurance
```bash
# 11. Run all quality checks
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest

# 12. Test help documentation
uv run gh-analysis collect --help

# 13. Verify documentation is updated and accurate
grep -r "created-after\|last-months" docs/
grep -r "date.*filter" docs/

# 14. Verify storage and results format unchanged
uv run gh-analysis status
```

**Dependencies:**
- No external dependencies required
- Uses existing GitHub search API capabilities
- Builds on current CLI and search infrastructure

**Architecture Considerations:**
- **Backwards Compatibility**: All existing CLI usage patterns remain unchanged
- **Parameter Precedence**: Clear rules when multiple date options provided
- **Performance**: Date filtering happens at GitHub API level (efficient)
- **User Experience**: Helpful error messages and intuitive parameter names
- **Testing**: Comprehensive coverage without requiring live API calls for basic tests

**Success Metrics:**
- Users can collect issues from specific date ranges using intuitive CLI commands
- All existing functionality works unchanged  
- Clear, helpful error messages for invalid date inputs
- Performance is equivalent to existing collection (filtering at API level)
- Documentation and help text clearly explain date filtering options

**Agent Notes:**
[Document implementation progress, API integration details, date parsing decisions, and validation approaches]