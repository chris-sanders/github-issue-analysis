# Task: Repository Exclusion for Organization-Wide Collection

**Status:** complete  
**Priority:** medium  
**Estimated Time:** 4-6 hours  
**Dependencies:** Existing GitHub issue collection system

## Description
Add repository exclusion functionality to allow users to exclude specific repositories when collecting issues from an entire organization. This addresses the common use case where users want to collect issues from most repositories in an organization but need to exclude a few they don't have access to or don't want to process.

## Problem Statement
Currently, organization-wide collection (`--org orgname`) includes all repositories in the organization. Users need the ability to:
1. **Exclude specific repositories** they don't have access to (permissions, private repos)
2. **Exclude repositories** they don't want to analyze (test repos, archived repos, etc.)
3. **Exclude multiple repositories** using a simple list format
4. **Maintain existing functionality** for users who don't need exclusions

## Current System Analysis

### Collection Modes
- **Single issue**: `--org ORG --repo REPO --issue-number NUM`
- **Repository-specific**: `--org ORG --repo REPO`
- **Organization-wide**: `--org ORG` (targets all repos in org)

### Implementation Details
- **CLI**: `cli/collect.py:114-118` calls `search_organization_issues()`
- **GitHub Client**: `github_client/client.py:194-254` implements org search
- **Search Query**: Uses `org:ORGNAME is:issue` GitHub search syntax
- **No exclusion mechanism** currently exists

## Solution Design

### 1. CLI Interface Enhancement

**New Parameters:**
```bash
--exclude-repo, -x TEXT     # Single repository to exclude (can be used multiple times)
--exclude-repos TEXT        # Comma-separated list of repositories to exclude
```

**Usage Examples:**
```bash
# Exclude single repository
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo private-repo

# Exclude multiple repositories (multiple flags)
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo private-repo --exclude-repo test-repo

# Exclude multiple repositories (comma-separated)
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repos "private-repo,test-repo,archived-repo"

# Mix both approaches
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo private-repo --exclude-repos "test-repo,archived-repo"
```

### 2. GitHub Search Query Modification

**Current Query:**
```
org:USER_PROVIDED_ORG is:issue state:closed
```

**New Query with Exclusions:**
```
org:USER_PROVIDED_ORG is:issue state:closed -repo:USER_PROVIDED_ORG/private-repo -repo:USER_PROVIDED_ORG/test-repo
```

**GitHub Search Syntax:**
- Use `-repo:org/reponame` to exclude specific repositories
- Multiple exclusions are combined with additional `-repo:` terms
- Maintains compatibility with all existing search parameters

### 3. Implementation Architecture

**Files to Modify:**

1. **`github_issue_analysis/cli/collect.py`** (Lines 18-48)
   - Add new CLI parameters for exclusions
   - Process and validate exclusion lists
   - Pass exclusions to search methods

2. **`github_issue_analysis/github_client/search.py`** (Lines 55-75)
   - Add `excluded_repos` parameter to `search_organization_issues()`
   - Pass exclusions to client method

3. **`github_issue_analysis/github_client/client.py`** (Lines 194-254)
   - Add `excluded_repos` parameter to `search_organization_issues()`
   - Modify query building to include `-repo:` exclusions
   - Validate exclusion format

4. **`docs/api-reference.md`** (Lines 13-38)
   - Document new CLI parameters
   - Add usage examples for exclusions

### 4. Parameter Processing Logic

**Exclusion List Building:**
```python
def build_exclusion_list(
    exclude_repo: list[str] | None,
    exclude_repos: str | None
) -> list[str]:
    """Build combined list of repositories to exclude."""
    exclusions = []
    
    # Add individual exclusions
    if exclude_repo:
        exclusions.extend(exclude_repo)
    
    # Add comma-separated exclusions
    if exclude_repos:
        exclusions.extend([repo.strip() for repo in exclude_repos.split(',')])
    
    # Remove duplicates and empty strings
    return list(set(filter(None, exclusions)))
```

**Query Building Enhancement:**
```python
def build_organization_query(
    org: str,
    labels: list[str] | None = None,
    state: str = "open",
    excluded_repos: list[str] | None = None
) -> str:
    """Build GitHub search query for organization with exclusions."""
    query_parts = [f"org:{org}", "is:issue"]
    
    if state != "all":
        query_parts.append(f"state:{state}")
    
    if labels:
        for label in labels:
            query_parts.append(f"label:{label}")
    
    # Add repository exclusions
    if excluded_repos:
        for repo in excluded_repos:
            query_parts.append(f"-repo:{org}/{repo}")
    
    return " ".join(query_parts)
```

### 5. Validation and Error Handling

**Repository Name Validation:**
- Ensure exclusion names are valid repository names (no spaces, special chars)
- Validate format but don't verify existence (permissions may prevent access)
- Provide helpful error messages for malformed names

**Edge Cases:**
- Empty exclusion lists (no effect on query)
- Duplicate exclusions (deduplicate automatically)
- Exclusions with organization prefix (strip if present)
- Invalid repository names (warning but continue)

### 6. User Experience Enhancements

**Console Output:**
```
🔍 Collecting issues from organization USER_PROVIDED_ORG
📋 Excluding repositories: private-repo, test-repo, archived-repo
🔑 Initializing GitHub client...
🔎 Searching for issues...
Search query: org:USER_PROVIDED_ORG is:issue state:closed -repo:USER_PROVIDED_ORG/private-repo -repo:USER_PROVIDED_ORG/test-repo -repo:USER_PROVIDED_ORG/archived-repo
✅ Found 25 issues
```

**Parameter Table:**
Add exclusions to the existing collection parameters table shown to users.

### 7. Compatibility Considerations

**Backward Compatibility:**
- All existing commands work unchanged
- New parameters are optional with default `None` values
- No breaking changes to existing functionality

**Integration Points:**
- Works with all existing filters (labels, state, limit)
- Compatible with organization-wide and repository-specific modes
- Exclusions only apply to organization-wide collection mode

## Acceptance Criteria

### Core Functionality
- [x] CLI accepts `--exclude-repo` parameter (multiple uses supported)
- [x] CLI accepts `--exclude-repos` parameter (comma-separated list)
- [x] Both parameters can be combined in single command
- [x] GitHub search query includes `-repo:` exclusions for each excluded repository
- [x] Organization-wide collection respects exclusions
- [x] Repository-specific and single-issue modes unaffected by exclusion parameters

### User Experience
- [x] Console output shows excluded repositories in collection summary
- [x] Parameter validation provides helpful error messages
- [x] Collection parameters table includes exclusion information
- [x] Exclusions deduplicated automatically

### Data Integrity
- [x] Collected issues only come from non-excluded repositories
- [x] Issue metadata correctly identifies source repositories
- [x] Storage and processing work normally with excluded collections

### Compatibility
- [x] All existing CLI commands work unchanged
- [x] Backward compatibility maintained for existing users
- [x] Integration with batch processing works correctly

### Testing
- [x] Unit tests for exclusion list building logic (using mocks, no API keys)
- [x] Unit tests for query building with exclusions (using mocks, no API keys)
- [x] Integration tests with mocked GitHub API responses (no API keys)
- [x] CLI parameter validation tests (using mocks, no API keys)
- [x] Manual verification with real organization data (uses GITHUB_TOKEN)

### Documentation
- [x] API reference updated with new parameters
- [x] Usage examples include exclusion scenarios
- [x] Help text accurately describes new functionality

## Implementation Plan

### Phase 1: Core Logic (2 hours)
1. Implement exclusion list building function
2. Modify GitHub search query building
3. Add parameters to method signatures
4. Basic validation logic

### Phase 2: CLI Integration (1.5 hours)
1. Add new CLI parameters to collect command
2. Process exclusion parameters
3. Update console output and parameter display
4. Integrate with existing collection flow

### Phase 3: Testing & Validation (1.5 hours)
1. Write unit tests using mocks (no API keys required)
2. Test edge cases and error handling with mocked responses
3. Manual validation with real GitHub API (using GITHUB_TOKEN)
4. Verify automated tests pass in CI environment (no API keys)

### Phase 4: Documentation (1 hour)
1. Update API reference documentation
2. Add usage examples
3. Update help text and command descriptions

## Test Cases

### Unit Tests (No API Keys Required - Use Mocks)
- `test_build_exclusion_list()` - Various input combinations with mock data
- `test_build_organization_query_with_exclusions()` - Query building with mock parameters
- `test_exclusion_parameter_processing()` - CLI parameter handling with mocked CLI runner
- `test_github_client_search_with_exclusions()` - Mock GitHub client responses
- `test_searcher_organization_exclusions()` - Mock GitHubSearcher behavior

### Manual Integration Tests (Uses GITHUB_TOKEN)
- Test with real GitHub organization (manual testing only)
- Verify exclusions actually exclude repositories (manual verification)
- Test with various combinations of parameters (manual testing)

### Edge Case Tests (No API Keys - Use Mocks)
- Empty exclusion lists with mocked responses
- Invalid repository names with mocked validation
- Duplicate exclusions with mock data
- Mixed parameter formats with mocked CLI input

### Test Implementation Guidelines
Follow existing test patterns in the codebase:
- Use `@patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"})` for environment mocking
- Use `@patch("github_issue_analysis.github_client.client.Github")` for GitHub API mocking
- Use `typer.testing.CliRunner` for CLI command testing
- Create structured mock data that mirrors real GitHub API responses
- Use pytest fixtures for reusable test data

## Manual Validation Commands (Require GITHUB_TOKEN)

**Note**: These commands are for manual testing only and require a valid GITHUB_TOKEN environment variable. Automated tests use mocks instead.

```bash
# Test basic exclusion functionality
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo private-repo --limit 5

# Test multiple exclusions
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repos "repo1,repo2,repo3" --limit 5

# Test with existing filters
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo private-repo --labels bug --state closed --limit 10

# Verify query building in logs
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repos "test-repo,archived-repo" --limit 1

# Test error handling
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --exclude-repo "invalid repo name" --limit 1
```

## Automated Test Commands (No API Keys Required)

```bash
# Run all tests (these use mocks, no API keys needed)
uv run pytest

# Run specific exclusion tests
uv run pytest tests/test_exclusions.py -v

# Run CLI tests with mocked responses
uv run pytest tests/cli/test_collect_exclusions.py -v

# Check test coverage
uv run pytest --cov=github_issue_analysis tests/
```

## Dependencies and Risks

### Dependencies
- Existing GitHub client and search functionality
- GitHub API search syntax compatibility
- Typer CLI framework for parameter handling

### Risks
- **GitHub API Limitations**: Complex queries may hit rate limits or length limits
- **Query Syntax Changes**: GitHub could modify search syntax
- **User Confusion**: Users might not understand exclusion vs inclusion logic

### Mitigation
- Keep exclusion lists reasonable (< 10 repositories)
- Provide clear error messages for API failures
- Include helpful examples in documentation

## Future Enhancements

### Potential Improvements
- Repository pattern matching (glob-style exclusions)
- Exclusion of private/archived repositories automatically
- Configuration file support for common exclusion lists
- Integration with GitHub repository metadata for smarter exclusions

### Related Tasks
- Could integrate with future caching mechanisms
- Might benefit from repository metadata collection
- Could support inclusion lists as alternative approach

## Agent Notes
[This section will be populated during implementation with progress updates, technical decisions, and validation results]

## Validation Steps
[This section will document the testing and validation process during implementation]