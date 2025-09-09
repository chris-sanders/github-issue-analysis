"""Tests for storage manager."""

import json
import tempfile
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gh_analysis.github_client.models import (
    GitHubIssue,
    GitHubUser,
    StoredIssue,
)
from gh_analysis.storage.manager import StorageManager


class TestStorageManager:
    """Test StorageManager class."""

    @pytest.fixture
    def temp_storage(self) -> Generator[StorageManager]:
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield StorageManager(base_path=temp_dir)

    @pytest.fixture
    def sample_issue(self) -> GitHubIssue:
        """Create a sample GitHub issue."""
        user = GitHubUser(login="testuser", id=12345)
        return GitHubIssue(
            number=42,
            title="Test Issue",
            body="Test body",
            state="open",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 0, 0),
        )

    def test_init_creates_directory(self) -> None:
        """Test that initialization creates the storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_storage"
            StorageManager(base_path=str(storage_path))

            assert storage_path.exists()
            assert storage_path.is_dir()

    def test_generate_filename(self, temp_storage: StorageManager) -> None:
        """Test filename generation."""
        filename = temp_storage._generate_filename("test-org", "test-repo", 123)
        expected = "test-org_test-repo_issue_123.json"
        assert filename == expected

    def test_get_file_path(self, temp_storage: StorageManager) -> None:
        """Test file path generation."""
        file_path = temp_storage._get_file_path("test-org", "test-repo", 123)
        expected_name = "test-org_test-repo_issue_123.json"
        assert file_path.name == expected_name
        assert file_path.parent == temp_storage.base_path

    def test_save_issue(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test saving a single issue."""
        metadata = {"test": "value"}

        file_path = temp_storage.save_issue(
            "testorg", "testrepo", sample_issue, metadata
        )

        assert file_path.exists()
        assert file_path.name == "testorg_testrepo_issue_42.json"

        # Verify file contents
        with open(file_path) as f:
            data = json.load(f)

        assert data["org"] == "testorg"
        assert data["repo"] == "testrepo"
        assert data["issue"]["number"] == 42
        assert data["issue"]["title"] == "Test Issue"
        assert data["metadata"]["test"] == "value"
        assert "collection_timestamp" in data["metadata"]
        assert data["metadata"]["api_version"] == "v4"

    def test_save_issue_without_metadata(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test saving issue without explicit metadata."""
        file_path = temp_storage.save_issue("testorg", "testrepo", sample_issue)

        assert file_path.exists()

        # Verify default metadata is added
        with open(file_path) as f:
            data = json.load(f)

        assert "collection_timestamp" in data["metadata"]
        assert data["metadata"]["api_version"] == "v4"
        assert data["metadata"]["tool_version"] == "0.1.0"

    def test_save_multiple_issues(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test saving multiple issues."""
        # Create a second issue
        user = GitHubUser(login="testuser2", id=54321)
        issue2 = GitHubIssue(
            number=43,
            title="Test Issue 2",
            body="Test body 2",
            state="closed",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime(2024, 1, 2, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0),
        )

        issues = [sample_issue, issue2]
        saved_paths = temp_storage.save_issues("testorg", "testrepo", issues)

        assert len(saved_paths) == 2
        assert all(path.exists() for path in saved_paths)

        # Verify both files were created
        expected_files = [
            "testorg_testrepo_issue_42.json",
            "testorg_testrepo_issue_43.json",
        ]
        for filename in expected_files:
            file_path = temp_storage.base_path / filename
            assert file_path.exists()

    def test_load_issue(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test loading an issue."""
        # First save an issue
        temp_storage.save_issue("testorg", "testrepo", sample_issue)

        # Then load it
        loaded_issue = temp_storage.load_issue("testorg", "testrepo", 42)

        assert loaded_issue is not None
        assert isinstance(loaded_issue, StoredIssue)
        assert loaded_issue.org == "testorg"
        assert loaded_issue.repo == "testrepo"
        assert loaded_issue.issue.number == 42
        assert loaded_issue.issue.title == "Test Issue"

    def test_load_nonexistent_issue(self, temp_storage: StorageManager) -> None:
        """Test loading an issue that doesn't exist."""
        loaded_issue = temp_storage.load_issue("testorg", "testrepo", 999)
        assert loaded_issue is None

    def test_load_corrupted_issue(self, temp_storage: StorageManager) -> None:
        """Test loading a corrupted issue file."""
        # Create a corrupted file
        file_path = temp_storage._get_file_path("testorg", "testrepo", 42)
        with open(file_path, "w") as f:
            f.write("invalid json")

        loaded_issue = temp_storage.load_issue("testorg", "testrepo", 42)
        assert loaded_issue is None

    def test_list_stored_issues(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test listing stored issues."""
        # Save some issues
        temp_storage.save_issue("org1", "repo1", sample_issue)

        # Create another issue with different number
        user = GitHubUser(login="testuser2", id=54321)
        issue2 = GitHubIssue(
            number=43,
            title="Test Issue 2",
            body="Test body 2",
            state="closed",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime(2024, 1, 2, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0),
        )
        temp_storage.save_issue("org2", "repo2", issue2)

        # Test listing all issues
        all_issues = temp_storage.list_stored_issues()
        assert len(all_issues) == 2
        assert "org1_repo1_issue_42.json" in all_issues
        assert "org2_repo2_issue_43.json" in all_issues

        # Test filtering by org and repo
        org1_issues = temp_storage.list_stored_issues(org="org1", repo="repo1")
        assert len(org1_issues) == 1
        assert "org1_repo1_issue_42.json" in org1_issues

        # Test filtering by org only
        org1_all = temp_storage.list_stored_issues(org="org1")
        assert len(org1_all) == 1
        assert "org1_repo1_issue_42.json" in org1_all

    def test_get_storage_stats(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test getting storage statistics."""
        # Save some issues
        temp_storage.save_issue("org1", "repo1", sample_issue)

        user = GitHubUser(login="testuser2", id=54321)
        issue2 = GitHubIssue(
            number=43,
            title="Test Issue 2",
            body="Test body 2",
            state="closed",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime(2024, 1, 2, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0),
        )
        temp_storage.save_issue("org1", "repo2", issue2)

        stats = temp_storage.get_storage_stats()

        assert stats["total_issues"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["total_size_mb"] >= 0
        assert "org1/repo1" in stats["repositories"]
        assert "org1/repo2" in stats["repositories"]
        assert stats["repositories"]["org1/repo1"] == 1
        assert stats["repositories"]["org1/repo2"] == 1
        assert stats["storage_path"] == str(temp_storage.base_path.absolute())

    def test_get_storage_stats_empty(self, temp_storage: StorageManager) -> None:
        """Test getting storage statistics when no issues exist."""
        stats = temp_storage.get_storage_stats()

        assert stats["total_issues"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["repositories"] == {}

    @patch("gh_analysis.storage.manager.console")
    def test_save_issue_file_error(
        self,
        mock_console: Mock,
        temp_storage: StorageManager,
        sample_issue: GitHubIssue,
    ) -> None:
        """Test handling file save errors."""
        # Mock file operations to raise an exception
        original_open = open

        def mock_open(*args, **kwargs):
            if "w" in str(args[1]):
                raise OSError("Disk full")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open):
            with pytest.raises(IOError):
                temp_storage.save_issue("testorg", "testrepo", sample_issue)

    def test_save_issues_partial_failure(
        self, temp_storage: StorageManager, sample_issue: GitHubIssue
    ) -> None:
        """Test saving multiple issues with partial failures."""
        # Create a second issue
        user = GitHubUser(login="testuser2", id=54321)
        issue2 = GitHubIssue(
            number=43,
            title="Test Issue 2",
            body="Test body 2",
            state="closed",
            labels=[],
            user=user,
            comments=[],
            created_at=datetime(2024, 1, 2, 12, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 0, 0),
        )

        issues = [sample_issue, issue2]

        # Mock save_issue to fail for the second issue
        original_save = temp_storage.save_issue

        def mock_save_issue(
            org: str,
            repo: str,
            issue: GitHubIssue,
            metadata: dict[str, str] | None = None,
        ) -> Path:
            if issue.number == 43:
                raise OSError("Disk full")
            return original_save(org, repo, issue, metadata)

        with patch.object(temp_storage, "save_issue", side_effect=mock_save_issue):
            saved_paths = temp_storage.save_issues("testorg", "testrepo", issues)

        # Should only save the first issue
        assert len(saved_paths) == 1
