"""Pydantic models for GitHub data structures.

These models map directly to GitHub's REST API v3/v4 response structures.
API Reference: https://docs.github.com/en/rest/issues
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    """GitHub user model representing a user account.

    Maps to GitHub REST API User object.
    API Reference: https://docs.github.com/en/rest/users/users
    """

    login: str = Field(..., description="GitHub username/login (string)")
    id: int = Field(..., description="Unique user identifier (integer)")


class GitHubLabel(BaseModel):
    """GitHub label model representing repository labels.

    Maps to GitHub REST API Label object.
    API Reference: https://docs.github.com/en/rest/issues/labels
    """

    name: str = Field(..., description="Name of the label (string)")
    color: str = Field(
        ..., description="Hexadecimal color code without leading # (string)"
    )
    description: str | None = Field(
        None, description="Short description of the label (string, max 100 characters)"
    )


class GitHubComment(BaseModel):
    """GitHub comment model representing issue/PR comments.

    Maps to GitHub REST API Issue Comment object.
    API Reference: https://docs.github.com/en/rest/issues/comments
    """

    id: int = Field(..., description="Unique comment identifier (integer)")
    user: GitHubUser = Field(..., description="Comment author details")
    body: str = Field(..., description="Text content of the comment (string)")
    created_at: datetime = Field(
        ..., description="Timestamp of comment creation (ISO 8601)"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp of last comment update (ISO 8601)"
    )


class GitHubAttachment(BaseModel):
    """GitHub attachment model for issue and comment attachments.

    This is a custom model not directly mapped to GitHub API, used for
    tracking downloaded binary attachments referenced in issue bodies and comments.
    """

    original_url: str = Field(
        ..., description="Original URL of the attachment from GitHub"
    )
    filename: str = Field(
        ..., description="Filename extracted from URL or content-disposition"
    )
    local_path: str | None = Field(
        None, description="Local filesystem path where attachment is stored"
    )
    content_type: str | None = Field(None, description="MIME type of the attachment")
    size: int | None = Field(None, description="Size in bytes of the attachment")
    downloaded: bool = Field(
        False, description="Whether the attachment has been successfully downloaded"
    )
    source: str = Field(
        ..., description="Source location: 'issue_body' or 'comment_{id}'"
    )


class GitHubIssue(BaseModel):
    """GitHub issue model representing repository issues.

    Maps to GitHub REST API Issue object with additional fields for attachments.
    API Reference: https://docs.github.com/en/rest/issues/issues
    """

    number: int = Field(..., description="Issue number within the repository (integer)")
    title: str = Field(..., description="Short description/title of the issue (string)")
    body: str | None = Field(
        None, description="Detailed description of the issue in markdown (string)"
    )
    state: str = Field(..., description="Current state: 'open', 'closed' (string)")
    labels: list[GitHubLabel] = Field(
        default_factory=list, description="Array of labels attached to the issue"
    )
    user: GitHubUser = Field(..., description="Creator/author of the issue")
    comments: list[GitHubComment] = Field(
        default_factory=list, description="All comments on the issue"
    )
    created_at: datetime = Field(
        ..., description="Timestamp of issue creation (ISO 8601)"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp of last issue update (ISO 8601)"
    )
    repository_name: str | None = Field(
        None, description="Repository name for organization-wide searches"
    )
    attachments: list[GitHubAttachment] = Field(
        default_factory=list,
        description="Downloaded attachments from issue and comments",
    )


class AttachmentMetadata(BaseModel):
    """Metadata for downloaded attachments.

    Custom model for tracking attachment download information and linking
    attachments back to their source issues.
    """

    issue_reference: dict[str, Any] = Field(
        ..., description="Reference to the source issue (org, repo, number)"
    )
    downloaded_at: datetime = Field(
        ..., description="Timestamp when attachments were downloaded"
    )
    attachments: list[GitHubAttachment] = Field(
        ..., description="List of attachments for this issue"
    )


class StoredIssue(BaseModel):
    """Model for issues as stored in JSON files.

    Wrapper model that includes organizational context and metadata
    for issues stored in the local filesystem.
    """

    org: str = Field(..., description="GitHub organization name")
    repo: str = Field(..., description="GitHub repository name")
    issue: GitHubIssue = Field(..., description="Complete GitHub issue data")
    metadata: dict[str, Any] = Field(
        ...,
        description="Storage metadata (timestamp, api_version, tool_version)",
    )
