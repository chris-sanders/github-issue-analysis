# Data Schemas

This document describes the JSON schemas used for storing GitHub issues, AI analysis results, and related metadata. All schemas are implemented as Pydantic models with full type validation.

## GitHub API Mapping

Our data models map directly to GitHub's REST API v3/v4 response structures:

- **Issues**: [GitHub Issues API](https://docs.github.com/en/rest/issues/issues)
- **Comments**: [GitHub Issue Comments API](https://docs.github.com/en/rest/issues/comments)
- **Labels**: [GitHub Labels API](https://docs.github.com/en/rest/issues/labels)
- **Users**: [GitHub Users API](https://docs.github.com/en/rest/users/users)

## Issue Storage Schema

Issues are stored as JSON files in `data/issues/` with filename format: `{org}_{repo}_issue_{number}.json`

The root object follows the `StoredIssue` model, which wraps the GitHub issue data with organizational context and metadata.

```json
{
  "org": "example-org",
  "repo": "example-repo",
  "issue": {
    "number": 12345,
    "title": "Editor fails to highlight syntax",
    "body": "Full issue description in markdown...",
    "state": "open",
    "labels": [
      {
        "name": "bug",
        "color": "d73a4a",
        "description": "Something isn't working"
      },
      {
        "name": "editor",
        "color": "0075ca", 
        "description": "Editor related issues"
      }
    ],
    "user": {
      "login": "username",
      "id": 12345
    },
    "comments": [
      {
        "id": 123456789,
        "user": {
          "login": "commenter",
          "id": 67890
        },
        "body": "Comment text...",
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
      }
    ],
    "created_at": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T15:00:00Z",
    "repository_name": "example-repo",
    "attachments": [
      {
        "original_url": "https://github.com/example-org/example-repo/files/123456/error.log",
        "filename": "error.log",
        "local_path": "data/attachments/example-org_example-repo_issue_12345/error.log",
        "content_type": "text/plain",
        "size": 2048,
        "downloaded": true,
        "source": "issue_body"
      },
      {
        "original_url": "https://user-images.githubusercontent.com/123/screenshot.png",
        "filename": "screenshot.png", 
        "local_path": "data/attachments/example-org_example-repo_issue_12345/screenshot.png",
        "content_type": "image/png",
        "size": 51200,
        "downloaded": true,
        "source": "comment_123456789"
      }
    ]
  },
  "metadata": {
    "collection_timestamp": "2024-01-01T20:00:00Z",
    "api_version": "v4",
    "tool_version": "0.1.0"
  }
}
```

### Schema Field Mappings

| Our Field | GitHub API Field | Description |
|-----------|------------------|-------------|
| `org` | N/A | Organization name (added by our system) |
| `repo` | N/A | Repository name (added by our system) |
| `issue.number` | `number` | Issue number within repository |
| `issue.title` | `title` | Issue title/summary |
| `issue.body` | `body` | Issue description (markdown) |
| `issue.state` | `state` | Issue state ("open", "closed") |
| `issue.labels` | `labels` | Array of label objects |
| `issue.user` | `user` | Issue creator |
| `issue.comments` | N/A | Comments (fetched separately) |
| `issue.created_at` | `created_at` | Issue creation timestamp |
| `issue.updated_at` | `updated_at` | Last update timestamp |
| `issue.attachments` | N/A | Downloaded attachments (custom) |
| `metadata` | N/A | Storage metadata (added by our system) |

### Pydantic Models

The schema is implemented using these Pydantic models in `github_issue_analysis/github_client/models.py`:

- `StoredIssue`: Root storage wrapper
- `GitHubIssue`: Main issue object
- `GitHubUser`: User/creator information
- `GitHubLabel`: Label information
- `GitHubComment`: Comment information
- `GitHubAttachment`: Attachment metadata (custom)
```

## AI Analysis Results Schema

Results are stored in `data/results/` with filename format: `org_repo_issue_<number>_<processor_name>.json`

```json
{
  "issue_reference": {
    "org": "example-org",
    "repo": "example-repo", 
    "issue_number": 12345,
    "file_path": "data/issues/example-org_example-repo_issue_12345.json"
  },
  "processor": {
    "name": "product-labeling",
    "version": "1.0.0",
    "model": "o4-mini",
    "timestamp": "2024-01-01T21:00:00Z"
  },
  "analysis": {
    "confidence": 0.85,
    "recommended_labels": [
      {
        "label": "product/editor",
        "confidence": 0.9,
        "reasoning": "Issue specifically mentions editor syntax highlighting functionality"
      }
    ],
    "current_labels_assessment": [
      {
        "label": "bug",
        "correct": true,
        "reasoning": "Correctly identifies this as a defect"
      },
      {
        "label": "editor", 
        "correct": true,
        "reasoning": "Appropriate component label"
      }
    ],
    "summary": "Issue is correctly labeled. Editor component tag is appropriate.",
    "raw_response": "Full AI model response..."
  }
}
```

## Task Schema

Tasks are markdown files in `tasks/` folder:

```markdown
# Task: Implement GitHub Issue Collection

**Status:** planning | ready | active | complete

**Description:**
Implement the core functionality to collect GitHub issues using the advanced search API.

**Acceptance Criteria:**
- [ ] CLI command `collect` with org, repo, date range, label filters
- [ ] Rate limiting and pagination handling
- [ ] Issues stored as JSON files in correct format
- [ ] Comprehensive test coverage
- [ ] Error handling for API failures

**Agent Notes:**
[Agent documents progress, decisions, and validation steps here]

**Validation:**
- Run `uv run gh-analysis collect --org test --repo test`
- Verify JSON files created in `data/issues/`
- Check rate limiting works with large result sets
- Ensure all tests pass
```

## Attachment Metadata Schema

Attachment metadata stored in each issue's attachment directory as `attachment_metadata.json`:

```json
{
  "issue_reference": {
    "org": "example-org",
    "repo": "example-repo",
    "issue_number": 12345
  },
  "downloaded_at": "2024-01-01T20:30:00Z",
  "attachments": [
    {
      "original_url": "https://github.com/example-org/example-repo/files/123456/error.log",
      "filename": "error.log",
      "local_filename": "error.log",
      "content_type": "text/plain",
      "size": 2048,
      "downloaded": true,
      "source": "issue_body"
    },
    {
      "original_url": "https://user-images.githubusercontent.com/123/screenshot.png",
      "filename": "screenshot.png",
      "local_filename": "screenshot.png", 
      "content_type": "image/png",
      "size": 51200,
      "downloaded": true,
      "source": "comment_456"
    }
  ]
}
```

## Configuration Schema

Environment variables in `.env`:

```
# Required
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Optional
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
GITHUB_API_BASE_URL=https://api.github.com
LOG_LEVEL=INFO
```