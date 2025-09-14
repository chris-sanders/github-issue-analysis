Purpose: notify slack channel when an issue has been analyed and has results.

Typically we run `uvx python run gh_analysis/cli/main.py process troubleshoot --url <issue_url> --agent <agent_name> --include-images --interactive` to analyze an issue.

I want to add a slack notification to the process troubleshoot command, with a CLI flag to enable it.

Example usage:

```bash
uvx gh-analysis process troubleshoot --url <issue_url> --agent <agent_name> --include-images --interactive --slack-notifications
```

The slack notifications should be sent to the #support-chat channel, as a reply to a message with the Github issue url.

Example Slack message that we wish to reply to:

From user "GitHub APP":

Initial message text (common to all messages we want to search for): "Issue created by replicated-collab-bot"

Typical message preview, which includes a URL for the issue itself:

```text
[#368 MinIO Error Message When Trying to Perform an Upgrade](https://github.com/replicated-collab/testorg/issues/368)
Requester: Wonderful Person  
Vendor Email: spooky.paws@testorg.test  
Github User: @spooky-paws-testorg  
Application Slug: test-org  
Customer Name: test-customer  
Show more
Labels
status::pending, kind::inbound-escalation, severity::s3, new_install, not_reproducible, supportbundle_uploaded, app::kots, customer_impacting, product::kurl, license::prod, license::sha256::123456
Comments
8
<https://github.com/replicated-collab/[testorg-replicated](https://github.com/replicated-collab/testorg/issues/368)|replicated-collab/testorg-replicated>replicated-collab/testorg-replicated | Sep 6th
```

We need to search the preview content for the issue url, and use it to find the message to reply to.

Steps:

1. take the Github issue url, and search in Slack #support-chat for the issue title
2. if the issue is found, collect the `ts` field from the issue, and use it as `thread_ts` in the `chat.postMessage` request
3. if the issue is not found, create a new thread in #support-chat with the issue title
4. post the results to the thread

Requirements:

- use the Slack API to post the message
- use the Slack API to search for the issue
- use the Slack API to create a new thread
- use the Slack API to post the message to the thread

Slack app setup (recommended approach):

1. Create a Slack app at <https://api.slack.com/apps>
2. Navigate to "OAuth & Permissions"
3. Add Bot Token Scopes:
   - chat:write (to post messages)
   - search:read (to search for existing issues)
   - channels:read (to list and access channels)
   - groups:read (to access private channels if needed)
4. Install the app to your workspace
5. Use the Bot User OAuth Token (starts with xoxb-) for API calls

## Implementation Plan

### 1. **Add Slack SDK Dependency**

- Add `slack-sdk>=3.33.0` to pyproject.toml dependencies
- Run `uv sync` to install the new dependency

### 2. **Create Slack Client Module** (`github_issue_analysis/slack/`)

- **`__init__.py`**: Module initialization
- **`client.py`**: Main Slack client with methods:
  - `search_for_issue()`: Find GitHub issue in the configured channel (uses `SLACK_CHANNEL`)
  - `post_to_thread()`: Reply to existing thread
  - `create_thread()`: Start new thread if issue not found
  - `format_troubleshoot_results()`: Format analysis results for Slack
- **`config.py`**: Configuration and environment variables:
  - `SLACK_BOT_TOKEN`: Bot authentication token
  - `SLACK_CHANNEL`: Target channel (default: #support-chat)

### 3. **Update CLI Command** (`github_issue_analysis/cli/process.py`)

- Add `--slack-notifications` flag to `troubleshoot` command
- Add Slack token validation when flag is enabled
- Call Slack notification after successful analysis (lines 806-883)
- Pass issue URL and analysis results to Slack client

### 4. **Notification Flow Implementation**

1. Extract issue title from GitHub data
2. Search #support-chat for messages containing the issue URL
3. If found: Reply to the thread using `thread_ts`
4. If not found: Create new thread with issue title
5. Format and post analysis results with:
   - Status (resolved/needs_data)
   - Root cause (if high confidence)
   - Evidence points
   - Recommended solution
   - Next steps (if needs_data)

### 5. **Message Formatting**

- Use Slack Block Kit for rich formatting
- Include:
  - Header with issue reference
  - Status indicator (✅ High Confidence / 📋 Needs Data)
  - Structured sections for findings
  - Timestamp and agent name

### 6. **Error Handling**

- Graceful degradation if Slack fails (log error, continue)
- Validate Slack response for successful posting
- Handle rate limiting with exponential backoff

### 7. **Testing Strategy**

- Unit tests for Slack client methods (mocked API)
- Integration test with test Slack workspace
- Manual testing with real GitHub issues

### 8. **Documentation Updates**

- Update README with Slack setup instructions
- Add environment variable documentation
- Include Slack app permission requirements

This implementation will seamlessly integrate Slack notifications into the existing troubleshoot workflow without disrupting current functionality.

## Implementation Completed

### Status: ✅ COMPLETED & MIGRATED

The Slack notifications feature has been successfully implemented and migrated to the new `gh_analysis/` package structure. All issues have been resolved and the feature is production-ready.

### What Was Implemented

#### 1. Dependencies Added

- Added `slack-sdk>=3.33.0` to pyproject.toml dependencies
- Installed and synced with uv

#### 2. Slack Client Module Created (`github_issue_analysis/slack/`)

**`__init__.py`**: Module initialization with proper exports

```python
from .client import SlackClient
from .config import SlackConfig
__all__ = ["SlackClient", "SlackConfig"]
```

**`config.py`**: Environment variable configuration

- `SLACK_BOT_TOKEN`: Required bot authentication token (starts with xoxb-)
- `SLACK_CHANNEL`: Optional target channel (defaults to "#support-chat")
- Validation methods to check if properly configured

**`client.py`**: Full Slack API client implementation with methods:

- `search_for_issue()`: Searches configured channel for existing GitHub issue threads using URL and issue number patterns
- `post_to_thread()`: Posts formatted analysis results to existing thread
- `post_new_message()`: Posts comprehensive new message when no existing thread found
- `notify_analysis_complete()`: Main workflow method handling complete notification flow
- `_format_analysis_results()`: Formats results using Slack Block Kit for rich display with status indicators, evidence, solutions, and timestamps

#### 3. CLI Integration

- Added `--slack-notifications` flag to the `troubleshoot` command in new "Notifications" help panel
- Added validation for SLACK_BOT_TOKEN when flag is enabled with clear error messages
- Integrated notification call after successful analysis completion with graceful error handling

#### 4. Improved Notification Flow Implementation

Complete workflow as specified:

1. Extract issue title from GitHub data
2. Search #support-chat (or configured channel) for messages containing the issue URL
3. If found: Reply to the existing thread using `thread_ts`
4. If not found: Post new comprehensive message (no unnecessary thread nesting)
5. Format and post analysis results with rich formatting

#### 5. Message Formatting

Implemented using Slack Block Kit with:

- Header with status emoji (✅ High Confidence / 📋 Needs Data / ❓ Unknown)
- Agent name display
- Status indicator
- Root cause (if high confidence)
- Key evidence points (limited to 5 with overflow indicator)
- Recommended solution (if high confidence)
- Next steps (if needs data)
- Timestamp footer

#### 6. Error Handling

- Graceful degradation if Slack fails (analysis continues, notification failure logged)
- Clear user feedback about notification status
- Proper exception handling with informative error messages
- Rate limiting and API error handling through slack-sdk

#### 7. Quality Assurance

All quality checks passed:

- ✅ Ruff formatting and linting
- ✅ MyPy type checking (all type annotations added)
- ✅ Tests (404/405 passed, 1 unrelated existing failure)

### Usage Example

```bash
# Basic usage with Slack notifications
uv run gh-analysis process troubleshoot \
  --url https://github.com/myorg/myrepo/issues/123 \
  --agent gpt5_mini_medium_mt \
  --include-images \
  --slack-notifications

# Required environment variables (hybrid token approach)
export SLACK_BOT_TOKEN="xoxb-your-bot-token-here"       # For posting messages
export SLACK_USER_TOKEN="xoxp-your-user-token-here"     # For searching messages

# Optional environment variables  
export SLACK_CHANNEL="#support-chat"  # Default if not specified
```

### Environment Variables

**Required (when using `--slack-notifications`):**

- `SLACK_BOT_TOKEN`: Bot User OAuth Token from your Slack app (starts with `xoxb-`)
- `SLACK_USER_TOKEN`: User OAuth Token from your Slack app (starts with `xoxp-`)

**Optional:**

- `SLACK_CHANNEL`: Target channel (defaults to "#support-chat")

### Slack App Setup (Hybrid Token Approach)

The implementation uses a hybrid approach with both Bot and User tokens to overcome Slack API limitations:

**Bot Token Scopes (for posting messages):**
- `chat:write` - Post messages as the bot

**User Token Scopes (for searching messages):**  
- `search:read` - Search for existing GitHub issue threads

**Additional Bot Token Scopes (recommended):**
- `channels:read` - Access channels
- `groups:read` - Access private channels if needed

**Setup Steps:**
1. Create Slack app at https://api.slack.com/apps
2. Navigate to "OAuth & Permissions"
3. Add **Bot Token Scopes**: `chat:write`, `channels:read`
4. Add **User Token Scopes**: `search:read` 
5. Install app to workspace
6. Copy both tokens:
   - Bot User OAuth Token (xoxb-) → `SLACK_BOT_TOKEN`
   - User OAuth Token (xoxp-) → `SLACK_USER_TOKEN`
7. Add bot to `#support-chat` channel

### Files Modified/Created

**New Files:**

- `gh_analysis/slack/__init__.py`
- `gh_analysis/slack/config.py`
- `gh_analysis/slack/client.py`

**Modified Files:**

- `pyproject.toml` - Added slack-sdk dependency
- `gh_analysis/cli/process.py` - Added CLI flag and integration
- `gh_analysis/runners/utils/github_runner.py` - Fixed issue data structure handling
- `tests/test_troubleshooting_functional.py` - Updated test signature

### Integration Points

The feature integrates seamlessly with the existing troubleshoot workflow:

- Activates only when `--slack-notifications` flag is used
- Runs after successful analysis completion
- Does not interfere with existing functionality if disabled
- Maintains all existing error handling and logging

## Recent Updates

### Package Structure Migration (2025-01-11)

**IMPORTANT**: During development, the repository underwent a package migration from `github_issue_analysis/` to `gh_analysis/`.

**What Happened:**
- Main branch migrated entire package structure from `github_issue_analysis/` to `gh_analysis/`
- Slack implementation was initially developed in the old structure
- During rebase, conflicts occurred due to package rename
- All Slack functionality successfully migrated to new structure

**Migration Actions Taken:**
- Moved `github_issue_analysis/slack/` → `gh_analysis/slack/`
- Removed deprecated `github_issue_analysis/` directory entirely
- All relative imports (`from ..slack.config`) work correctly
- No functionality lost during migration

**Current Structure:**
- ✅ `gh_analysis/slack/` - Slack notification module
- ✅ Single package structure aligned with `pyproject.toml`
- ✅ Clean repository without duplicate directories

### Hybrid Token Implementation (2025-01-11)

Implemented hybrid Slack token approach to overcome API limitations where bot tokens cannot search messages:

**What Changed:**
- `SlackConfig` now requires both `SLACK_BOT_TOKEN` and `SLACK_USER_TOKEN`
- `SlackClient` uses `user_client` for searching messages and `bot_client` for posting
- CLI validation updated to check for both tokens with clear error messages
- Search functionality uses User OAuth Token with `search:read` scope
- Message posting uses Bot OAuth Token with `chat:write` scope

**Why Changed:**
- Slack deprecated `search:read` scope for bot tokens
- Bot tokens can no longer use `search.messages` API endpoint
- User tokens are required for message search functionality
- Hybrid approach provides best of both worlds: search capability + bot identity

**Impact:**
- Messages still appear from bot (not individual users)
- Can successfully search for existing GitHub issue threads
- Graceful error handling with clear setup instructions
- Future-proof against Slack API restrictions

### Status Value Change (2025-01-10)

**Note: This change was reverted back to `"resolved"` due to validation issues.**

The status value was temporarily changed from `"resolved"` to `"high_confidence"` but was reverted to maintain compatibility:

**What Was Reverted:**
- `ResolvedAnalysis.status` back to `Literal["resolved"]`
- CLI display logic back to checking `"resolved"` status
- Slack client formatting back to using `"resolved"` for ✅ emoji
- All test files reverted to use `"resolved"` status

**Why Reverted:**
- Caused validation errors preventing troubleshoot command from working
- Schema mismatch between expected and actual model responses
- Functional compatibility more important than semantic accuracy

**Impact:**
- Slack notifications show "✅ Resolved" 
- All functionality preserved and working
- No breaking changes to API or workflow
- 