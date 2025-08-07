# Enhanced Issue Collection Feature

**Status:** pending  
**Assigned to:** Claude Agent  
**Priority:** high  
**Estimated completion:** 2-3 hours  

## Overview

Enhance the existing `collect` command to support flexible issue collection patterns including single issues and organization-wide searches, with closed issues as the default state. This addresses the need for targeted issue collection during development and analysis phases.

## Requirements

### Functional Requirements

1. **Enhanced CLI Command Parameters**
   - Add `--issue-number` parameter to existing `collect` command
   - Make `--repo` parameter optional when `--org` is provided
   - Change default `--state` from "open" to "closed" 
   - Support multiple collection modes based on provided parameters

2. **Command Syntax Patterns**
   ```bash
   # Single issue collection (new)
   # Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER
   
   # Organization-wide search (new) - search all repos in org
   # Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --limit 20
   
   # Repository-specific bulk collection (existing, enhanced)
   # Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 10
   ```

3. **Collection Mode Logic**
   - **Single Issue Mode**: When `--issue-number` is provided (requires both `--org` and `--repo`)
   - **Organization Mode**: When only `--org` is provided (searches across all repos in org)
   - **Repository Mode**: When both `--org` and `--repo` are provided (existing behavior)
   - Default `--state` should be "closed" for all modes

### Technical Requirements

1. **API Integration**
   - **Single Issue**: Use GitHub REST API `/repos/{owner}/{repo}/issues/{issue_number}` endpoint
   - **Organization Search**: Use GitHub Search API with `org:` qualifier to search across all repos
   - **Repository Search**: Maintain existing search API for repository-specific collection
   - Ensure proper error handling for non-existent issues and private repositories

2. **Data Consistency**
   - All collection modes should produce identical JSON structure
   - Maintain same storage location and naming convention
   - Preserve all metadata fields across all modes

3. **Parameter Validation**
   - Single issue mode requires both `--org` and `--repo` parameters
   - Organization mode requires only `--org` parameter
   - Repository mode requires both `--org` and `--repo` parameters
   - Clear error messages for invalid parameter combinations

4. **Error Handling**
   - Handle non-existent issues, repositories, and organizations
   - Proper handling of private repositories and permission issues
   - Rate limit handling for all API endpoints

## Implementation Plan

### Phase 1: CLI Interface Updates (`cli/collect.py`)
1. Add `--issue-number` parameter (Optional[int])
2. Make `--repo` parameter optional (change from `...` to `None`) 
3. Change default `--state` from "open" to "closed"
4. Add parameter validation function to determine collection mode:
   - Validate `--issue-number` requires both `--org` and `--repo`
   - Validate organization mode requires only `--org`
   - Update help text and examples for new functionality

### Phase 2: GitHub Client Updates
1. **`github_client/client.py`**: Add `get_single_issue(org: str, repo: str, issue_number: int)` method
2. **`github_client/search.py`**: Add `search_organization_issues(org: str, ...)` method using `org:` qualifier
3. Update existing `search_repository_issues` to use new default state
4. Ensure all methods return consistent `GitHubIssue` models

### Phase 3: Storage Integration (`storage/manager.py`)
1. Verify `save_issues()` method handles cross-repository issues correctly
2. Ensure filename generation works for issues from different repos in same org
3. Update storage stats to handle organization-wide collections

### Phase 4: Testing & Validation
1. **Unit tests**: Mock all GitHub API calls, test parameter validation
2. **Integration tests**: Test with mocked responses, verify storage consistency  
3. **Manual validation**: Test real API calls with USER_PROVIDED_ORG repo using GITHUB_TOKEN

### Current CLI Structure Analysis
- Line 18: `repo` parameter currently required (`...`) - needs to be optional
- Line 26: `state` default is "open" - needs to change to "closed"
- Lines 32-37: Help text needs updating for new functionality
- Lines 61-63: Only handles repository search - needs org search and single issue modes

## Testing Specification

### Automated Tests (pytest)
**Note: These tests use mocked GitHub API responses since the USER_PROVIDED_ORG repo is only accessible on dev machine**

#### Unit Tests
- [ ] Test CLI parameter parsing with `--issue-number`
- [ ] Test default state change to "closed"
- [ ] Test parameter validation for three collection modes
- [ ] Test error handling for invalid parameter combinations

#### Integration Tests  
- [ ] Test GitHub API client methods with mocked responses
- [ ] Test storage consistency between collection modes
- [ ] Test rate limiting behavior with mocked API
- [ ] Mock tests for non-existent issues/repos/orgs

### Manual Validation (dev machine only)
**Note: These tests require actual GitHub API access to USER_PROVIDED_ORG repo via GITHUB_TOKEN**

**Test Case 1: Single Issue Collection**
```bash
# Test with the specific issue mentioned
# Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER

# Expected: Successfully collect issue #71 "Weird Behavior with RunPods"
# Verify: File created at data/issues/ORG_REPO_issue_NUMBER.json
# Verify: Issue has 20 comments and "closed" state
# Verify: Collection completes in <10 seconds
```

**Test Case 2: Organization-Wide Collection**
```bash
# Test organization-wide search
# Ask user to provide test organization for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --limit 10

# Expected: Collects 10 closed issues from any repo in USER_PROVIDED_ORG org
# Verify: Issues from multiple repositories are collected
# Verify: All collected issues have "state": "closed" by default
# Verify: File names include different repository names
```

**Test Case 3: Repository-Specific Collection (Enhanced)**
```bash
# Test repository collection uses closed by default
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 5

# Expected: Collects 5 closed issues from provided repo only
# Verify: All collected issues have "state": "closed"
# Verify: All issues are from provided repository
```

**Test Case 4: Error Handling**
```bash
# Test non-existent issue
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number 99999

# Expected: Clear error message about issue not found
# Verify: No file created, proper exit code

# Test invalid parameter combinations
uv run gh-analysis collect --issue-number 71

# Expected: Error message requiring both --org and --repo for single issue mode
```

**Test Case 5: Backward Compatibility**
```bash
# Test existing bulk collection still works with explicit state
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --state open --limit 3

# Expected: Collects 3 open issues (overriding new default)
# Verify: All collected issues have "state": "open"
```

### Validation Criteria

#### Automated Test Validation (pytest)
1. **Unit Test Coverage**
   - All CLI parameter combinations tested with mocks
   - Parameter validation logic fully covered
   - Error handling paths tested with appropriate exceptions

2. **Integration Test Coverage**
   - GitHub API client methods tested with mocked responses
   - Storage operations tested with temporary directories
   - Rate limiting behavior verified with mock scenarios

#### Manual Validation Criteria (dev machine)
1. **Functionality**
   - Single issue collection retrieves exact issue #71 with all 20 comments
   - Organization-wide search returns issues from multiple repos in USER_PROVIDED_ORG
   - Repository-specific search works with new closed default
   - Default state change to "closed" works across all modes

2. **Performance**
   - Single issue collection completes in <10 seconds
   - Organization search completes in <30 seconds for 10 issues
   - No unnecessary API calls or data processing

3. **Data Integrity**
   - All collection modes produce identical JSON structure
   - All comments, labels, and metadata preserved
   - Storage location and naming convention consistent across modes

4. **Error Handling**
   - Graceful handling of non-existent issues, repos, and orgs
   - Clear error messages for invalid parameter combinations
   - Proper exit codes for scripting integration

## Acceptance Criteria

### Automated Testing (pytest)
- [ ] All existing pytest tests continue to pass
- [ ] New unit tests added for CLI parameter validation logic
- [ ] New integration tests added with mocked GitHub API responses
- [ ] All tests use mocks/fixtures (no real API calls in pytest)
- [ ] Code coverage maintained or improved

### Manual Validation (dev machine with GITHUB_TOKEN)
- [ ] Can collect single issue by number: `--issue-number 71` (requires --org and --repo)
- [ ] Can collect organization-wide issues: `--org USER_PROVIDED_ORG` (without --repo)
- [ ] Can collect repository-specific issues: `--org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO`
- [ ] Default state is "closed" for all collection modes
- [ ] Issue #71 successfully collected with all 20 comments
- [ ] Organization-wide search returns issues from multiple repositories
- [ ] Parameter validation prevents invalid combinations
- [ ] Manual testing completed successfully for all test cases

### Documentation & Polish
- [ ] CLI help text updated to reflect new functionality
- [ ] Error messages are clear and actionable

## Notes

### Testing Approach
- **pytest**: Uses mocked responses only (no real GitHub API calls)
- **Manual validation**: Uses real GitHub API with GITHUB_TOKEN on dev machine
- **Target repo**: USER_PROVIDED_ORG/USER_PROVIDED_REPO (only accessible on dev machine)
- **Primary test issue**: #71 "Weird Behavior with RunPods" (20 comments, closed state)

### Development Guidelines
- Maintain strict type checking with mypy
- Follow existing code patterns and conventions
- Ensure proper error messages help users troubleshoot issues
- All quality checks must pass: `uv run black . && uv run ruff check --fix && uv run mypy . && uv run pytest`

## Dependencies

- Existing GitHub client and API integration
- Current storage system and JSON schema
- Typer CLI framework
- Existing test infrastructure with mocking capabilities