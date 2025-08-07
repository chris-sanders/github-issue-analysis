"""Tests for GitHub client models."""

from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from github_issue_analysis.github_client.models import (
    GitHubComment,
    GitHubIssue,
    GitHubLabel,
    GitHubUser,
    StoredIssue,
)


class TestGitHubUser:
    """Test GitHubUser model."""

    def test_valid_user(self) -> None:
        """Test creating a valid user."""
        user = GitHubUser(login="testuser", id=12345)
        assert user.login == "testuser"
        assert user.id == 12345

    def test_missing_fields(self) -> None:
        """Test validation with missing fields."""
        with pytest.raises(ValidationError):
            GitHubUser(login="testuser")  # type: ignore[call-arg]

        with pytest.raises(ValidationError):
            GitHubUser(id=12345)  # type: ignore[call-arg]


class TestGitHubLabel:
    """Test GitHubLabel model."""

    def test_valid_label(self) -> None:
        """Test creating a valid label."""
        label = GitHubLabel(name="bug", color="ff0000", description="Bug reports")
        assert label.name == "bug"
        assert label.color == "ff0000"
        assert label.description == "Bug reports"

    def test_label_without_description(self) -> None:
        """Test label without description."""
        label = GitHubLabel(name="enhancement", color="00ff00", description=None)
        assert label.name == "enhancement"
        assert label.color == "00ff00"
        assert label.description is None

    def test_missing_required_fields(self) -> None:
        """Test validation with missing required fields."""
        with pytest.raises(ValidationError):
            GitHubLabel(name="bug")  # type: ignore[call-arg]


class TestGitHubComment:
    """Test GitHubComment model."""

    def test_valid_comment(self) -> None:
        """Test creating a valid comment."""
        user = GitHubUser(login="commenter", id=54321)
        created = updated = datetime.now()

        comment = GitHubComment(
            id=98765,
            user=user,
            body="This is a comment",
            created_at=created,
            updated_at=updated,
        )

        assert comment.id == 98765
        assert comment.user == user
        assert comment.body == "This is a comment"
        assert comment.created_at == created
        assert comment.updated_at == updated


class TestGitHubIssue:
    """Test GitHubIssue model."""

    def create_sample_issue(self) -> GitHubIssue:
        """Create a sample issue for testing."""
        user = GitHubUser(login="issueuser", id=11111)
        label = GitHubLabel(name="bug", color="ff0000", description="Bug reports")
        comment_user = GitHubUser(login="commenter", id=22222)
        comment = GitHubComment(
            id=33333,
            user=comment_user,
            body="Test comment",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        return GitHubIssue(
            number=42,
            title="Test Issue",
            body="This is a test issue",
            state="open",
            labels=[label],
            user=user,
            comments=[comment],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            repository_name=None,
        )

    def test_valid_issue(self) -> None:
        """Test creating a valid issue."""
        issue = self.create_sample_issue()

        assert issue.number == 42
        assert issue.title == "Test Issue"
        assert issue.body == "This is a test issue"
        assert issue.state == "open"
        assert len(issue.labels) == 1
        assert issue.labels[0].name == "bug"
        assert len(issue.comments) == 1
        assert issue.comments[0].body == "Test comment"

    def test_issue_without_body(self) -> None:
        """Test issue without body."""
        user = GitHubUser(login="issueuser", id=11111)

        issue = GitHubIssue(
            number=42,
            title="Test Issue",
            body=None,
            state="open",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            repository_name=None,
        )

        assert issue.body is None

    def test_issue_without_comments(self) -> None:
        """Test issue without comments."""
        user = GitHubUser(login="issueuser", id=11111)

        issue = GitHubIssue(
            number=42,
            title="Test Issue",
            body="Test body",
            state="open",
            labels=[],
            user=user,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            repository_name=None,
        )

        assert issue.comments == []


class TestStoredIssue:
    """Test StoredIssue model."""

    def test_valid_stored_issue(self) -> None:
        """Test creating a valid stored issue."""
        user = GitHubUser(login="issueuser", id=11111)
        issue = GitHubIssue(
            number=42,
            title="Test Issue",
            body="Test body",
            state="open",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            repository_name=None,
        )

        metadata: dict[str, Any] = {
            "collection_timestamp": datetime.now().isoformat(),
            "api_version": "v4",
        }

        stored_issue = StoredIssue(
            org="testorg", repo="testrepo", issue=issue, metadata=metadata
        )

        assert stored_issue.org == "testorg"
        assert stored_issue.repo == "testrepo"
        assert stored_issue.issue == issue
        assert stored_issue.metadata == metadata

    def test_stored_issue_serialization(self) -> None:
        """Test that stored issue can be serialized to dict."""
        user = GitHubUser(login="issueuser", id=11111)
        issue = GitHubIssue(
            number=42,
            title="Test Issue",
            body="Test body",
            state="open",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            repository_name=None,
        )

        stored_issue = StoredIssue(
            org="testorg", repo="testrepo", issue=issue, metadata={"test": "value"}
        )

        # Should be able to convert to dict without errors
        data = stored_issue.model_dump()
        assert isinstance(data, dict)
        assert data["org"] == "testorg"
        assert data["repo"] == "testrepo"
        assert "issue" in data
        assert "metadata" in data
