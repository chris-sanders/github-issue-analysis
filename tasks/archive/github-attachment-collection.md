# Task: GitHub Issue Attachment Collection

**Status:** complete

**Description:**
Extend the basic issue collection to detect, download, and store GitHub issue attachments (images, files, etc.) from issue bodies and comments.

**Prerequisites:**
- `github-issue-collection.md` must be completed first
- Requires working GitHub API client and storage manager

**Files to Create:**
- `github_issue_analysis/github_client/attachments.py` - Attachment detection and download
- `tests/test_github_client/test_attachments.py` - Attachment tests

**Files to Modify:**
- `github_issue_analysis/github_client/models.py` - Add attachment models
- `github_issue_analysis/github_client/client.py` - Add attachment download methods
- `github_issue_analysis/storage/manager.py` - Add attachment storage methods
- `github_issue_analysis/cli/collect.py` - Add --download-attachments option

**Implementation Details:**

**Attachment Detection:**
Parse issue body and comment text for:
- GitHub-hosted files: `https://github.com/{org}/{repo}/files/{id}/{filename}`
- GitHub user content: `https://user-images.githubusercontent.com/{user_id}/{filename}`
- GitHub assets: `https://github.com/{org}/{repo}/assets/{asset_id}`

**Regex Patterns:**
```python
GITHUB_FILE_PATTERN = r'https://github\.com/[\w-]+/[\w-]+/files/\d+/[\w.-]+\??[\w=&]*'
GITHUB_IMAGE_PATTERN = r'https://user-images\.githubusercontent\.com/\d+/[\w.-]+\??[\w=&]*'  
GITHUB_ASSET_PATTERN = r'https://github\.com/[\w-]+/[\w-]+/assets/\d+'
```

**Pydantic Models to Add:**
```python
class GitHubAttachment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID to prevent conflicts
    original_url: str
    filename: str
    local_path: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None
    downloaded: bool = False
    source: str  # "issue_body" or "comment_{id}"

class AttachmentMetadata(BaseModel):
    issue_reference: Dict[str, Any]
    downloaded_at: datetime
    attachments: List[GitHubAttachment]
```

**Storage Structure:**
```
data/attachments/ORG_REPO_issue_NUMBER/
├── screenshot.png
├── error_log.txt  
└── attachment_metadata.json
```

**Download Strategy:**
- Use httpx to download files with proper headers (include GitHub token for authentication)
- Detect content-type from response headers
- Handle redirects and authentication
- Respect file size limits (default 10MB max)
- Generate safe local filenames

**Authentication Example:**
```python
headers = {
    "Authorization": f"token {github_token}",
    "User-Agent": "github-issue-analysis/0.1.0"
}
async with httpx.AsyncClient() as client:
    response = await client.get(attachment_url, headers=headers)
```

**CLI Integration:**
Add options to collect command:
- `--download-attachments / --no-download-attachments` (default: true)
- `--max-attachment-size MB` (default: 10)

**Acceptance Criteria:**
- [x] Detect attachments in issue bodies and comments using regex patterns
- [x] Download attachments to organized directory structure
- [x] Store attachment metadata as JSON
- [x] Update issue JSON to include attachment references
- [x] Handle download failures gracefully (log and continue)
- [x] Respect file size limits and content-type restrictions
- [x] Comprehensive test coverage with mocked downloads
- [x] CLI option to disable attachment downloading
- [x] Code quality checks pass (ruff, black, mypy)

**Agent Notes:**
**Completed Implementation (Claude Agent)**

**Attachment Detection Strategy:**
- Implemented regex-based detection for three GitHub attachment types:
  - GitHub files: `https://github.com/{org}/{repo}/files/{id}/{filename}`
  - User images: `https://user-images.githubusercontent.com/{user_id}/{filename}`
  - GitHub assets: `https://github.com/{org}/{repo}/assets/{asset_id}`
- Detection processes both issue body and all comments
- Each attachment tagged with source ("issue_body" or "comment_{id}")

**Download Implementation:**
- Built async AttachmentDownloader class with proper authentication
- Uses httpx for HTTP requests with GitHub token in headers
- Implements HEAD requests for size checking before download
- Concurrent downloading with asyncio.gather for performance
- Safe filename generation handling duplicates and unsafe characters
- Respects configurable file size limits (default 10MB)

**Error Handling:**
- Graceful handling of HTTP errors (404, 403, etc.)
- File size limit enforcement with user feedback
- Network error recovery with proper logging
- Invalid filename sanitization
- Continues processing if individual downloads fail

**Storage Organization:**
- Attachments stored in `data/attachments/{org}_{repo}_issue_{number}/`
- Metadata saved as JSON with download timestamps and file info
- Integration with existing StorageManager for consistent handling

**CLI Integration:**
- Added `--download-attachments/--no-download-attachments` (default: true)
- Added `--max-attachment-size` option (default: 10MB)
- Token validation for attachment processing
- Progress feedback during download operations

**Testing:**
- Comprehensive test suite with 17 test cases
- Mocked HTTP responses for reliable testing
- Tests for regex patterns, file handling, error conditions
- Async test coverage for download functionality
- All tests passing with proper type annotations

**Code Quality:**
- All linting checks passing (ruff, black, mypy, pytest)
- Strict type annotations throughout
- Follows existing code patterns and conventions
- Proper error messages and user feedback

**NEXT STEPS FOR FUTURE AGENT:**
1. **Wait for single-issue-collection feature branch to merge** - This feature depends on the `--issue-number` functionality
2. **Manual Testing Required** - Run real validation tests with GitHub issue #71:
   ```bash
   # After single-issue collection merges, test with:
   # Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER --download-attachments
   ```
3. **Validation Checklist** (once single-issue collection is available):
   - [ ] Test with USER_PROVIDED_ORG/USER_PROVIDED_REPO issue #71 (has all attachment types)
   - [ ] Verify attachment directories created in `data/attachments/`
   - [ ] Check attachment metadata JSON files exist and are valid  
   - [ ] Test with `--no-download-attachments` flag
   - [ ] Verify issue JSON includes attachment references
   - [ ] Test with various attachment types (images, text files, archives)
   - [ ] Test authentication with private repos
   - [ ] Ensure no regressions in existing functionality

**IMPLEMENTATION STATUS:**
- ✅ Core attachment functionality complete
- ✅ All automated tests passing (17/17) 
- ✅ Code quality checks passing (ruff, black, mypy, pytest)
- ✅ Feature committed to `feature/github-attachment-collection` branch
- ✅ **COMPLETED**: Manual testing with single-issue collection functionality
- ✅ **COMPLETED**: Pull request created - https://github.com/chris-sanders/github-issue-analysis/pull/3
- ✅ **COMPLETED**: All linting issues fixed and pushed

**FILES MODIFIED/CREATED:**
- `github_client/attachments.py` (new) - Core attachment detection/download
- `github_client/models.py` - Added GitHubAttachment & AttachmentMetadata models  
- `github_client/client.py` - Added attachment processing integration
- `storage/manager.py` - Added attachment metadata storage methods
- `cli/collect.py` - Added CLI options and attachment processing flow
- `tests/test_github_client/test_attachments.py` (new) - Comprehensive test suite
- `tasks/github-attachment-collection.md` - Updated with completion status

**Critical Implementation Notes:**
- **PyGithub does NOT support downloading issue attachments** - only release assets and repo files
- **Issue attachments require manual HTTP requests** with GitHub token authentication
- **All attachment URLs need GitHub token in Authorization header** for private repos
- **Handle HTTP errors gracefully** (404, 403, rate limits) - log and continue

**Test with Real Data:**
```bash
# Test with issue #71 which has multiple attachment types
# Ask user to provide test organization, repository, and issue number for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER --download-attachments

# Expected attachments in issue #71:
# - Images: ![Image](https://github.com/user-attachments/assets/...)
# - Files: [output.log](https://github.com/user-attachments/files/...)  
# - Archives: [supportbundle-2025-06-18T14_56_49.tar.gz](...)
# - Inline images: <img src="https://github.com/user-attachments/assets/..."/>
```

**Validation:**
- Test with USER_PROVIDED_ORG/USER_PROVIDED_REPO issue #71 (has all attachment types)
- Verify attachment directories created in `data/attachments/`
- Check attachment metadata JSON files exist and are valid
- Test with --no-download-attachments flag
- Verify issue JSON includes attachment references
- Test with various attachment types (images, text files, archives)
- Test authentication with private repos
- Ensure all tests pass: `uv run pytest tests/test_github_client/test_attachments.py -v`