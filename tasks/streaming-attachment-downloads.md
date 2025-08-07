# Task: Fix GitHub Attachment Download 400 Errors

## Status
- **Status**: Complete
- **Priority**: High
- **Estimated Effort**: 3-4 hours (Actual: 1 hour)
- **Dependencies**: None

## Problem Statement

GitHub attachment downloads are failing with HTTP 400 Bad Request errors during batch collection, but the timing suggests this is NOT a simple JWT token expiration issue.

**Observed Evidence:**
- 20 issue collection completed in ~30 seconds (much faster than 5-minute JWT expiration)
- Multiple attachments failed with `❌ HTTP error downloading {uuid}: 400 Bad Request`
- Pattern shows certain issues consistently fail (463, 462, 459, 458) while others succeed
- Some attachments from the same timeframe work (467, 471, 461, 446)

## How to Reproduce the 400 Errors

**Exact Command That Triggered the Failures:**
```bash
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 20
```

**System Context:**
- Date/Time: 2025-07-03 18:32:xx (CST)
- GitHub API rate limit: 4065 requests remaining
- Repository: Ask user to provide test organization/repository at runtime
- Issues collected: #471, #470, #468, #467, #464, #463, #462, #461, #459, #458, #456, #455, #454, #453, #452, #450, #449, #448, #447, #446

**Expected Reproduction Steps:**
1. Ensure GitHub token is set: `export GITHUB_TOKEN=your_token`
2. Run the exact command above
3. Observe the "Processed issue #XXX" messages appear first (showing batch collection)
4. Then observe "Processing attachments for issue #XXX" messages
5. Look for multiple `❌ HTTP error downloading {uuid}: 400 Bad Request` failures

**Specific Failed Downloads to Investigate:**
```
Issue #463: 
  - ❌ 50c76887-edc3-45f1-a586-f76a69c17281: 400 Bad Request
  - ❌ 77a138f6-50e7-43a4-abfb-89c384e381bd: 400 Bad Request

Issue #462:
  - ❌ 8a0c02ae-6dd6-4a05-9fd5-f4f51d1916e2: 400 Bad Request  
  - ❌ 2bb34cc6-cffd-43fd-a802-8a4729517348: 400 Bad Request
  - ❌ c7d6f65c-8e63-4aaa-8ffd-6256a5119e38: 400 Bad Request

Issue #459:
  - ❌ 9142e70b-7570-4f36-9f30-61d780c2293f: 400 Bad Request
  - ❌ f9140844-1430-41d9-acb2-2819efd0ec0d: 400 Bad Request

Issue #458:
  - ❌ acf05fc0-dccd-4d1f-9767-90dd59783009: 400 Bad Request
  - ❌ abfb3fce-1c7b-4db0-89ff-45a84feb1e94: 400 Bad Request
```

**Successful Downloads for Comparison:**
```
Issue #471: ✅ c1490631-9028-46aa-8bd8-790cb4277886 (PNG, 38KB)
Issue #467: ✅ 9afd91e8-72b8-4a7f-9043-c7b35f7e5f95 (PNG, 57KB) 
Issue #467: ✅ c4c382b2-2bac-4aa6-8257-8c4130d2f6a8 (PNG, 97KB)
Issue #461: ✅ 796161dd-65d8-4f55-bbd2-2842380c0bb7 (size unknown)
Issue #446: ✅ ad609c2e-8336-4a3b-a737-66ca5643567d (size unknown)
```

**Key Observation for Investigation:**
ALL attachments from issues #463, #462, #459, #458 failed, while ALL attachments from issues #471, #467, #461, #446 succeeded. This suggests the issue is **per-issue/per-timeframe**, not per individual attachment.

**Key Questions to Investigate:**
1. What exactly causes the 400 Bad Request errors?
2. Why do some attachments work while others fail in the same collection?
3. Is this related to JWT token format differences, URL structure, or GitHub API changes?
4. Does the attachment age, size, or source comment affect success rates?

## Required Investigation Steps

### 1. Deep Dive Analysis of 400 Errors

**Immediate Actions:**
1. **Examine failed attachment URLs** - Compare working vs failing attachment original URLs
2. **Check JWT token structure** - Decode and compare JWT tokens from working vs failing attachments  
3. **Add detailed error logging** - Capture full HTTP response bodies, not just status codes
4. **Test individual attachment downloads** - Try downloading failed attachments manually/via curl

**Files to Examine:**
- `github_issue_analysis/github_client/attachments.py` - Download logic and error handling
- Recent test output showing specific failed attachment IDs
- GitHub issue data to compare attachment sources and timestamps

### 2. Compare Working vs Failing Attachment Patterns

**Analysis needed:**
```
Working attachments (from test):
- Issue #471: c1490631-9028-46aa-8bd8-790cb4277886 ✅
- Issue #467: 9afd91e8-72b8-4a7f-9043-c7b35f7e5f95 ✅  
- Issue #467: c4c382b2-2bac-4aa6-8257-8c4130d2f6a8 ✅
- Issue #461: 796161dd-65d8-4f55-bbd2-2842380c0bb7 ✅
- Issue #446: ad609c2e-8336-4a3b-a737-66ca5643567d ✅

Failing attachments (from test):
- Issue #463: 50c76887-edc3-45f1-a586-f76a69c17281 ❌
- Issue #463: 77a138f6-50e7-43a4-abfb-89c384e381bd ❌
- Issue #462: 8a0c02ae-6dd6-4a05-9fd5-f4f51d1916e2 ❌
- Issue #462: 2bb34cc6-cffd-43fd-a802-8a4729517348 ❌
- Issue #462: c7d6f65c-8e63-4aaa-8ffd-6256a5119e38 ❌
- Issue #459: 9142e70b-7570-4f36-9f30-61d780c2293f ❌
- Issue #459: f9140844-1430-41d9-acb2-2819efd0ec0d ❌
- Issue #458: acf05fc0-dccd-4d1f-9767-90dd59783009 ❌
- Issue #458: abfb3fce-1c7b-4db0-89ff-45a84feb1e94 ❌
```

**Questions:**
- Do failing attachments share common URL patterns?
- Are failing attachments older than working ones?
- Do failing attachments come from different comment sources?
- Are there differences in attachment detection vs JWT URL fetching?

### 3. Enhance Error Logging and Debugging

**Code Changes Needed:**
```python
# In attachments.py download_attachment method
try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    # ADD: Log full response details
    console.print(f"❌ HTTP {e.response.status_code} downloading {filename}")
    console.print(f"   URL: {url}")
    console.print(f"   Response: {e.response.text}")
    console.print(f"   Headers: {dict(e.response.headers)}")
    return attachment.model_copy(update={"downloaded": False})
```

### 4. Test JWT Token Theory vs Alternative Theories

**JWT Token Investigation:**
- Decode JWT tokens from both working and failing attachments
- Compare expiration times, audience, issuer, and payload
- Check if JWT token format changed between working/failing attachments

**Alternative Theories to Test:**
1. **Attachment age** - Are older attachments inaccessible regardless of JWT tokens?
2. **GitHub API rate limiting** - Are we hitting attachment-specific rate limits?
3. **URL format differences** - Do failing attachments use different URL patterns?
4. **Permission issues** - Do some attachments require different authentication?
5. **GitHub repository access** - Have some attachments been moved/deleted?

## Secondary: Consider Streaming Architecture (If Timing is the Issue)

**Only pursue this if investigation shows timing IS the root cause:**

Convert search methods from returning complete lists to streaming individual issues for immediate processing.

**Files to Modify:**
- `github_issue_analysis/github_client/client.py`
- `github_issue_analysis/github_client/search.py`  
- `github_issue_analysis/cli/collect.py`

## Required Architecture Changes

### 1. Convert Search Methods to Generators/Async Iterators

**Files to Modify:**
- `github_issue_analysis/github_client/client.py`
- `github_issue_analysis/github_client/search.py`

**Change Required:**
Convert these methods from returning `list[GitHubIssue]` to yielding issues one at a time:
- `GitHubClient.search_issues()`
- `GitHubSearcher.search_repository_issues()`  
- `GitHubSearcher.search_organization_issues()`

**Example Implementation:**
```python
def search_issues_streaming(
    self,
    org: str,
    repo: str,
    # ... other params
) -> Iterator[GitHubIssue]:
    """Stream issues one at a time instead of collecting all first."""
    issues = self.github.search_issues(query)
    
    for i, github_issue in enumerate(issues):
        if i >= limit:
            break
            
        try:
            yield self._convert_issue(github_issue)
        except Exception as e:
            console.print(f"Error processing issue #{github_issue.number}: {e}")
            continue
```

### 2. Update Collection Logic for Streaming

**File to Modify:**
- `github_issue_analysis/cli/collect.py`

**Change Required:**
Modify the collection logic to process each issue as it's yielded, not after getting a complete batch.

**Example Implementation:**
```python
# Current (broken):
all_issues = searcher.search_repository_issues(...)
for issue in all_issues:
    process_attachments(issue)

# New (streaming):
issues = []
for issue in searcher.search_repository_issues_streaming(...):
    if download_attachments and downloader:
        issue = _process_issue_attachments(issue, downloader, org, repo)
    issues.append(issue)
    console.print(f"✅ Collected and processed issue #{issue.number}")
```

### 3. Maintain Backward Compatibility

Keep existing non-streaming methods for any code that depends on getting complete lists:
- Add new `*_streaming()` methods alongside existing ones
- Update CLI to use streaming versions
- Keep original methods for any batch processing needs

## Implementation Steps

1. **Add streaming search methods** in `client.py` and `search.py`
2. **Update collect.py** to use streaming methods and process attachments immediately
3. **Test with various collection sizes** (1, 10, 50, 200+ issues)
4. **Verify JWT token expiration is resolved** 
5. **Add tests** for streaming functionality
6. **Update documentation** if needed

## Expected Outcome

**New Flow (Fixed):**
1. Issue 1 collected → Attachments downloaded immediately → Issue 1 complete
2. Issue 2 collected → Attachments downloaded immediately → Issue 2 complete  
3. Continue for all issues...

**Benefits:**
- ✅ Eliminates JWT token expiration (attachments downloaded within seconds of collection)
- ✅ Better user feedback (progress shown per issue)
- ✅ Lower memory usage (don't hold all issues in memory)
- ✅ Better error isolation (one failed issue doesn't affect others)

## Testing Requirements

1. **Single issue collection** - Should continue working
2. **Small batch (5-10 issues)** - Should show immediate processing per issue
3. **Large batch (50+ issues)** - Should eliminate HTTP 400 attachment download errors
4. **Organization-wide collection** - Should work with streaming approach
5. **Error handling** - Failed attachment downloads shouldn't break entire collection

## Notes

- This is a **breaking change** to internal APIs but not to CLI interface
- JWT tokens have `exp` field showing 5-minute expiration from GitHub
- Current attachment downloader already fetches fresh JWT tokens, but only if called within the expiration window
- The `_get_working_asset_urls()` method works correctly - the issue is timing of when it's called

## Reference

- Original issue identified in SwaggerHub issue 467 investigation
- JWT token structure: `{"exp": 1751584898, "nbf": 1751584598}` (300 second validity)
- Error manifests as: `❌ HTTP error downloading {uuid}: 400 Bad Request`
