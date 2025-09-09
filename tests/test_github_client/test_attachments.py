"""Tests for GitHub attachment functionality."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from gh_analysis.github_client.attachments import AttachmentDownloader
from gh_analysis.github_client.models import (
    GitHubAttachment,
    GitHubComment,
    GitHubIssue,
    GitHubUser,
)


class TestAttachmentDownloader:
    """Test attachment downloader functionality."""

    @pytest.fixture
    def downloader(self) -> AttachmentDownloader:
        """Create an AttachmentDownloader instance for testing."""
        return AttachmentDownloader("test_token", max_size_mb=5)

    @pytest.fixture
    def sample_issue(self) -> GitHubIssue:
        """Create a sample GitHubIssue for testing."""
        user = GitHubUser(login="testuser", id=123)

        comments = [
            GitHubComment(
                id=456,
                user=user,
                body="Check this file: https://github.com/org/repo/files/123/test.log",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]

        return GitHubIssue(
            number=1,
            title="Test Issue",
            body="See screenshot: https://user-images.githubusercontent.com/123/screenshot.png",
            state="open",
            labels=[],
            user=user,
            comments=comments,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_detect_attachments_github_files(
        self, downloader: AttachmentDownloader
    ) -> None:
        """Test detection of GitHub file URLs."""
        text = (
            "Please check https://github.com/org/repo/files/123456/error.log "
            "for details"
        )
        attachments = downloader.detect_attachments(text, "issue_body")

        assert len(attachments) == 1
        assert (
            attachments[0].original_url
            == "https://github.com/org/repo/files/123456/error.log"
        )
        assert attachments[0].filename == "error.log"
        assert attachments[0].source == "issue_body"
        assert not attachments[0].downloaded

    def test_detect_attachments_user_images(
        self, downloader: AttachmentDownloader
    ) -> None:
        """Test detection of GitHub user image URLs."""
        text = (
            "![Screenshot](https://user-images.githubusercontent.com/12345/image.png)"
        )
        attachments = downloader.detect_attachments(text, "comment_789")

        assert len(attachments) == 1
        assert (
            attachments[0].original_url
            == "https://user-images.githubusercontent.com/12345/image.png"
        )
        assert attachments[0].filename == "image.png"
        assert attachments[0].source == "comment_789"

    def test_detect_attachments_github_assets(
        self, downloader: AttachmentDownloader
    ) -> None:
        """Test detection of GitHub asset URLs."""
        text = "Asset: https://github.com/user-attachments/assets/6f92d22b-1555-4979-8f48-4e530b21382f"
        attachments = downloader.detect_attachments(text, "issue_body")

        assert len(attachments) == 1
        assert (
            attachments[0].original_url
            == "https://github.com/user-attachments/assets/6f92d22b-1555-4979-8f48-4e530b21382f"
        )
        assert attachments[0].source == "issue_body"

    def test_detect_attachments_multiple(
        self, downloader: AttachmentDownloader
    ) -> None:
        """Test detection of multiple attachments in text."""
        text = """
        Check these files:
        - Log: https://github.com/org/repo/files/123/app.log
        - Screenshot: https://user-images.githubusercontent.com/456/screen.png
        - Asset: https://github.com/user-attachments/assets/abc123-def456
        """
        attachments = downloader.detect_attachments(text, "issue_body")

        assert len(attachments) == 3
        urls = [att.original_url for att in attachments]
        assert "https://github.com/org/repo/files/123/app.log" in urls
        assert "https://user-images.githubusercontent.com/456/screen.png" in urls
        assert "https://github.com/user-attachments/assets/abc123-def456" in urls

    def test_detect_attachments_empty_text(
        self, downloader: AttachmentDownloader
    ) -> None:
        """Test detection with empty text."""
        assert downloader.detect_attachments("", "issue_body") == []

    def test_extract_filename(self, downloader: AttachmentDownloader) -> None:
        """Test filename extraction from URLs."""
        # Normal file URL
        assert (
            downloader._extract_filename(
                "https://github.com/org/repo/files/123/test.log"
            )
            == "test.log"
        )

        # URL with query parameters
        assert (
            downloader._extract_filename(
                "https://user-images.githubusercontent.com/123/image.png?raw=true"
            )
            == "image.png"
        )

        # Asset URL (no extension) - returns the last part of the path
        filename = downloader._extract_filename(
            "https://github.com/org/repo/assets/123456"
        )
        assert filename == "123456"

    def test_generate_safe_filename(
        self, downloader: AttachmentDownloader, tmp_path: Path
    ) -> None:
        """Test safe filename generation."""
        # Normal filename
        safe = downloader._generate_safe_filename("test.log", tmp_path)
        assert safe == "test.log"

        # Filename with unsafe characters
        safe = downloader._generate_safe_filename("file with spaces!@#.txt", tmp_path)
        assert safe == "file_with_spaces___.txt"

        # Duplicate filename handling
        (tmp_path / "test.log").touch()
        safe = downloader._generate_safe_filename("test.log", tmp_path)
        assert safe == "test_1.log"

    @pytest.mark.asyncio
    async def test_download_attachment_success(
        self, downloader: AttachmentDownloader, tmp_path: Path
    ) -> None:
        """Test successful attachment download."""
        attachment = GitHubAttachment(
            original_url="https://example.com/file.txt",
            filename="file.txt",
            source="issue_body",
        )

        mock_response = Mock()
        mock_response.content = b"test file content"
        mock_response.headers = {"content-length": "17", "content-type": "text/plain"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.head.return_value = mock_response
            mock_instance.get.return_value = mock_response

            result = await downloader.download_attachment(attachment, tmp_path)

            assert result.downloaded
            assert result.size == 17
            assert result.content_type == "text/plain"
            assert result.local_path == str(tmp_path / "file.txt")

            # Check file was actually created
            assert (tmp_path / "file.txt").exists()
            assert (tmp_path / "file.txt").read_bytes() == b"test file content"

    @pytest.mark.asyncio
    async def test_download_attachment_too_large(
        self, downloader: AttachmentDownloader, tmp_path: Path
    ) -> None:
        """Test attachment download with file too large."""
        attachment = GitHubAttachment(
            original_url="https://example.com/large.zip",
            filename="large.zip",
            source="issue_body",
        )

        mock_response = Mock()
        mock_response.headers = {
            "content-length": str(10 * 1024 * 1024)  # 10MB, larger than 5MB limit
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.head.return_value = mock_response

            result = await downloader.download_attachment(attachment, tmp_path)

            assert not result.downloaded
            assert result.local_path is None

    @pytest.mark.asyncio
    async def test_download_attachment_http_error(
        self, downloader: AttachmentDownloader, tmp_path: Path
    ) -> None:
        """Test attachment download with HTTP error."""
        attachment = GitHubAttachment(
            original_url="https://example.com/notfound.txt",
            filename="notfound.txt",
            source="issue_body",
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.head.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=Mock(status_code=404)
            )

            result = await downloader.download_attachment(attachment, tmp_path)

            assert not result.downloaded
            assert result.local_path is None

    @pytest.mark.asyncio
    async def test_download_attachments_multiple(
        self, downloader: AttachmentDownloader, tmp_path: Path
    ) -> None:
        """Test downloading multiple attachments."""
        attachments = [
            GitHubAttachment(
                original_url="https://example.com/file1.txt",
                filename="file1.txt",
                source="issue_body",
            ),
            GitHubAttachment(
                original_url="https://example.com/file2.txt",
                filename="file2.txt",
                source="comment_123",
            ),
        ]

        mock_response = Mock()
        mock_response.content = b"test content"
        mock_response.headers = {"content-length": "12", "content-type": "text/plain"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.head.return_value = mock_response
            mock_instance.get.return_value = mock_response

            results = await downloader.download_attachments(attachments, tmp_path)

            assert len(results) == 2
            assert all(result.downloaded for result in results)
            assert (tmp_path / "file1.txt").exists()
            assert (tmp_path / "file2.txt").exists()

    def test_process_issue_attachments(
        self, downloader: AttachmentDownloader, sample_issue: GitHubIssue
    ) -> None:
        """Test processing issue to detect all attachments."""
        result = downloader.process_issue_attachments(sample_issue)

        assert len(result.attachments) == 2

        # Check issue body attachment
        body_attachments = [
            att for att in result.attachments if att.source == "issue_body"
        ]
        assert len(body_attachments) == 1
        assert "screenshot.png" in body_attachments[0].filename

        # Check comment attachment
        comment_attachments = [
            att for att in result.attachments if att.source.startswith("comment_")
        ]
        assert len(comment_attachments) == 1
        assert comment_attachments[0].source == "comment_456"

    @pytest.mark.asyncio
    async def test_download_issue_attachments(
        self,
        downloader: AttachmentDownloader,
        sample_issue: GitHubIssue,
        tmp_path: Path,
    ) -> None:
        """Test downloading all attachments for an issue."""
        # First, process issue to detect attachments
        issue_with_attachments = downloader.process_issue_attachments(sample_issue)

        mock_response = Mock()
        mock_response.content = b"mock file content"
        mock_response.headers = {"content-length": "17", "content-type": "image/png"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.head.return_value = mock_response
            mock_instance.get.return_value = mock_response

            result = await downloader.download_issue_attachments(
                issue_with_attachments, tmp_path, "testorg", "testrepo"
            )

            # Check that issue directory was created
            issue_dir = tmp_path / "testorg_testrepo_issue_1"
            assert issue_dir.exists()

            # Check that attachments were downloaded
            downloaded_count = sum(1 for att in result.attachments if att.downloaded)
            assert downloaded_count > 0


class TestAttachmentRegexPatterns:
    """Test attachment detection regex patterns."""

    def test_github_file_pattern(self) -> None:
        """Test GitHub file URL pattern matching."""
        import re

        from gh_analysis.github_client.attachments import GITHUB_FILE_PATTERN

        valid_urls = [
            "https://github.com/test-org/test-repo/files/12345/error.log",
            "https://github.com/org-name/repo-name/files/67890/file.txt",
            "https://github.com/user/repo/files/111/file.with.dots.json",
        ]

        for url in valid_urls:
            assert re.search(GITHUB_FILE_PATTERN, url), f"Should match: {url}"

    def test_github_image_pattern(self) -> None:
        """Test GitHub user images pattern matching."""
        import re

        from gh_analysis.github_client.attachments import GITHUB_IMAGE_PATTERN

        valid_urls = [
            "https://user-images.githubusercontent.com/12345/image.png",
            "https://user-images.githubusercontent.com/67890/screenshot.jpg",
            "https://user-images.githubusercontent.com/111/file.with-dashes.gif",
        ]

        for url in valid_urls:
            assert re.search(GITHUB_IMAGE_PATTERN, url), f"Should match: {url}"

    def test_github_asset_pattern(self) -> None:
        """Test GitHub assets pattern matching."""
        import re

        from gh_analysis.github_client.attachments import GITHUB_ASSET_PATTERN

        valid_urls = [
            "https://github.com/user-attachments/assets/6f92d22b-1555-4979-8f48-4e530b21382f",
            "https://github.com/user-attachments/assets/abc123-def456",
        ]

        for url in valid_urls:
            assert re.search(GITHUB_ASSET_PATTERN, url), f"Should match: {url}"


@pytest.mark.integration
class TestAttachmentIntegration:
    """Integration tests for attachment functionality."""

    def test_attachment_workflow(self, tmp_path: Path) -> None:
        """Test complete attachment workflow."""
        # This would be a more comprehensive integration test
        # that tests the entire flow from detection to storage
        pass  # Placeholder for integration tests
