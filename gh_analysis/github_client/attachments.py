"""GitHub attachment detection and download functionality."""

import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from rich.console import Console

from .models import GitHubAttachment, GitHubIssue

console = Console()

# Regex patterns for GitHub attachment URLs
GITHUB_FILE_PATTERN = r"https://github\.com/[\w-]+/[\w-]+/files/\d+/[\w.-]+\??[\w=&]*"
GITHUB_IMAGE_PATTERN = (
    r"https://user-images\.githubusercontent\.com/\d+/[\w.-]+\??[\w=&]*"
)
GITHUB_ASSET_PATTERN = r"https://github\.com/user-attachments/assets/[\w-]+"


class AttachmentDownloader:
    """Downloads and manages GitHub issue attachments."""

    def __init__(self, github_token: str, max_size_mb: int = 10):
        """Initialize attachment downloader.

        Args:
            github_token: GitHub personal access token
            max_size_mb: Maximum file size to download in MB
        """
        self.github_token = github_token
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.headers = {
            "Authorization": f"Bearer {github_token}",
            "User-Agent": "github-issue-analysis/0.1.0",
            "Accept": "application/vnd.github.full+json",
        }

    def detect_attachments(self, text: str, source: str) -> list[GitHubAttachment]:
        """Detect GitHub attachments in text content.

        Args:
            text: Text content to search for attachments
            source: Source identifier (e.g., "issue_body", "comment_123")

        Returns:
            List of detected GitHubAttachment objects
        """
        if not text:
            return []

        attachments = []

        # Find all GitHub file URLs
        file_urls = re.findall(GITHUB_FILE_PATTERN, text)
        for url in file_urls:
            filename = self._extract_filename(url)
            attachments.append(
                GitHubAttachment(original_url=url, filename=filename, source=source)
            )

        # Find all GitHub image URLs
        image_urls = re.findall(GITHUB_IMAGE_PATTERN, text)
        for url in image_urls:
            filename = self._extract_filename(url)
            attachments.append(
                GitHubAttachment(original_url=url, filename=filename, source=source)
            )

        # Find all GitHub asset URLs
        asset_urls = re.findall(GITHUB_ASSET_PATTERN, text)
        for url in asset_urls:
            filename = self._extract_filename(url)
            attachments.append(
                GitHubAttachment(original_url=url, filename=filename, source=source)
            )

        return attachments

    def _extract_filename(self, url: str) -> str:
        """Extract filename from URL.

        Args:
            url: URL to extract filename from

        Returns:
            Extracted filename or generated name
        """
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")

        # For GitHub files, filename is usually the last part
        if path_parts:
            filename = path_parts[-1]
            # Remove query parameters
            if "?" in filename:
                filename = filename.split("?")[0]
            if filename and filename != "/":
                return filename

        # Generate filename from URL if extraction fails
        return f"attachment_{hash(url) % 10000}"

    def _generate_safe_filename(self, filename: str, download_dir: Path) -> str:
        """Generate a safe filename, handling duplicates.

        Args:
            filename: Original filename
            download_dir: Directory where file will be saved

        Returns:
            Safe filename that doesn't conflict with existing files
        """
        # Remove or replace unsafe characters
        safe_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        )
        safe_filename = "".join(c if c in safe_chars else "_" for c in filename)

        # Ensure filename is not empty
        if not safe_filename:
            safe_filename = "attachment"

        # Handle duplicate filenames
        counter = 1
        original_name = safe_filename
        while (download_dir / safe_filename).exists():
            name_parts = original_name.rsplit(".", 1)
            if len(name_parts) == 2:
                safe_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
            else:
                safe_filename = f"{original_name}_{counter}"
            counter += 1

        return safe_filename

    async def _get_working_asset_urls(
        self, org: str, repo: str, issue_number: int, comment_id: str | None = None
    ) -> dict[str, str]:
        """Get working JWT URLs for GitHub assets by fetching HTML from API.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number
            comment_id: Comment ID if fetching comment, None for issue body

        Returns:
            Dict mapping asset IDs to working JWT URLs
        """
        try:
            async with httpx.AsyncClient() as client:
                if comment_id:
                    # Fetch comment HTML
                    url = f"https://api.github.com/repos/{org}/{repo}/issues/comments/{comment_id}"
                else:
                    # Fetch issue HTML
                    url = f"https://api.github.com/repos/{org}/{repo}/issues/{issue_number}"

                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()

                html_content = data.get("body_html", "")
                if not html_content:
                    return {}

                # Extract JWT URLs from HTML
                asset_mapping = {}
                # Look for private-user-images URLs with JWT tokens
                jwt_pattern = r'https://private-user-images\.githubusercontent\.com/[^"]+\?jwt=[^"]+'
                jwt_urls = re.findall(jwt_pattern, html_content)

                for jwt_url in jwt_urls:
                    # Extract asset ID from the URL pattern
                    # URLs look like: .../456579721-{uuid}.png?jwt=...
                    # We want the UUID part: 5559e3a4-ea5f-4cd7-a0a0-a302b0b62612
                    uuid_pat = (
                        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
                    )
                    asset_pattern = rf"/\d+-({uuid_pat})\."
                    asset_match = re.search(asset_pattern, jwt_url)
                    if asset_match:
                        asset_id = asset_match.group(1)
                        asset_mapping[asset_id] = jwt_url

                return asset_mapping

        except Exception as e:
            console.print(f"⚠️  Failed to fetch working asset URLs: {e}")
            return {}

    async def download_attachment(
        self, attachment: GitHubAttachment, download_dir: Path
    ) -> GitHubAttachment:
        """Download a single attachment.

        Args:
            attachment: GitHubAttachment object to download
            download_dir: Directory to save the attachment

        Returns:
            Updated GitHubAttachment object with download status
        """
        try:
            async with httpx.AsyncClient() as client:
                # Determine headers - don't use Authorization for JWT-signed URLs
                request_headers = {}
                if "jwt=" not in attachment.original_url:
                    # Only use Authorization header for non-JWT URLs
                    request_headers = self.headers
                else:
                    # For JWT-signed URLs, use only basic headers
                    request_headers = {
                        "User-Agent": "github-issue-analysis/0.1.0",
                        "Accept": "application/vnd.github.full+json",
                    }

                # First, get file info with HEAD request
                head_response = await client.head(
                    attachment.original_url,
                    headers=request_headers,
                    follow_redirects=True,
                )

                # Check file size
                content_length = head_response.headers.get("content-length")
                if content_length:
                    size = int(content_length)
                    if size > self.max_size_bytes:
                        console.print(
                            f"⚠️  Skipping {attachment.filename}: "
                            f"File too large ({size / 1024 / 1024:.1f} MB > "
                            f"{self.max_size_bytes / 1024 / 1024} MB)"
                        )
                        return attachment
                    attachment.size = size

                # Get content type
                content_type = head_response.headers.get("content-type")
                if content_type:
                    attachment.content_type = content_type

                # Download the file
                response = await client.get(
                    attachment.original_url,
                    headers=request_headers,
                    follow_redirects=True,
                )
                response.raise_for_status()

                # Generate safe filename
                safe_filename = self._generate_safe_filename(
                    attachment.filename, download_dir
                )
                file_path = download_dir / safe_filename

                # Save file
                with open(file_path, "wb") as f:
                    f.write(response.content)

                # Update attachment info
                attachment.local_path = str(file_path)
                attachment.downloaded = True
                attachment.size = len(response.content)

                console.print(f"✅ Downloaded: {safe_filename}")
                return attachment

        except httpx.HTTPStatusError as e:
            console.print(
                f"❌ HTTP error downloading {attachment.filename}: "
                f"{e.response.status_code} {e.response.reason_phrase}"
            )
            console.print(f"   URL: {attachment.original_url}")
            console.print(f"   Response: {e.response.text}")
            try:
                console.print(f"   Headers: {dict(e.response.headers)}")
            except (TypeError, AttributeError):
                console.print(f"   Headers: {e.response.headers}")
        except Exception as e:
            console.print(f"❌ Error downloading {attachment.filename}: {e}")

        return attachment

    async def download_attachments(
        self, attachments: list[GitHubAttachment], download_dir: Path
    ) -> list[GitHubAttachment]:
        """Download multiple attachments concurrently.

        Args:
            attachments: List of GitHubAttachment objects to download
            download_dir: Directory to save attachments

        Returns:
            List of updated GitHubAttachment objects
        """
        if not attachments:
            return []

        # Create download directory
        download_dir.mkdir(parents=True, exist_ok=True)

        # Download attachments concurrently
        tasks = [
            self.download_attachment(attachment, download_dir)
            for attachment in attachments
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return successful downloads
        updated_attachments = []
        for result in results:
            if isinstance(result, GitHubAttachment):
                updated_attachments.append(result)
            else:
                console.print(f"❌ Download task failed: {result}")

        return updated_attachments

    def process_issue_attachments(self, issue: GitHubIssue) -> GitHubIssue:
        """Process and detect all attachments in an issue.

        Args:
            issue: GitHubIssue object to process

        Returns:
            Updated GitHubIssue object with detected attachments
        """
        all_attachments = []

        # Process issue body
        if issue.body:
            body_attachments = self.detect_attachments(issue.body, "issue_body")
            all_attachments.extend(body_attachments)

        # Process comments
        for comment in issue.comments:
            if comment.body:
                comment_attachments = self.detect_attachments(
                    comment.body, f"comment_{comment.id}"
                )
                all_attachments.extend(comment_attachments)

        # Update issue with attachments
        issue.attachments = all_attachments
        return issue

    async def download_issue_attachments(
        self, issue: GitHubIssue, base_dir: Path, org: str, repo: str
    ) -> GitHubIssue:
        """Download all attachments for an issue.

        Args:
            issue: GitHubIssue object with detected attachments
            base_dir: Base directory for attachments
            org: Organization name
            repo: Repository name

        Returns:
            Updated GitHubIssue object with downloaded attachments
        """
        if not issue.attachments:
            return issue

        # Create issue-specific directory
        issue_dir = base_dir / f"{org}_{repo}_issue_{issue.number}"

        console.print(
            f"📥 Downloading {len(issue.attachments)} attachments for "
            f"issue #{issue.number}"
        )

        # Get working JWT URLs for GitHub user-attachments assets
        # First collect all unique comment IDs that have attachments
        comment_ids_with_attachments = set()
        has_issue_body_attachments = False

        for attachment in issue.attachments:
            if attachment.source == "issue_body":
                has_issue_body_attachments = True
            elif attachment.source.startswith("comment_"):
                comment_id = attachment.source.replace("comment_", "")
                comment_ids_with_attachments.add(comment_id)

        # Fetch JWT URLs for issue and all comments with attachments
        jwt_url_mappings = {}

        if has_issue_body_attachments:
            issue_jwt_urls = await self._get_working_asset_urls(org, repo, issue.number)
            jwt_url_mappings.update(issue_jwt_urls)

        for comment_id in comment_ids_with_attachments:
            comment_jwt_urls = await self._get_working_asset_urls(
                org, repo, issue.number, comment_id
            )
            jwt_url_mappings.update(comment_jwt_urls)

        # Replace user-attachments asset URLs with working JWT URLs
        for attachment in issue.attachments:
            if "user-attachments/assets/" in attachment.original_url:
                # Extract asset ID from the original URL
                asset_id = attachment.original_url.split("/")[-1]
                if asset_id in jwt_url_mappings:
                    # Replace the broken URL with the working JWT URL
                    attachment.original_url = jwt_url_mappings[asset_id]

        # Download attachments
        updated_attachments = await self.download_attachments(
            issue.attachments, issue_dir
        )

        # Update issue with downloaded attachments
        issue.attachments = updated_attachments

        # Count successful downloads
        downloaded_count = sum(1 for att in updated_attachments if att.downloaded)
        console.print(
            f"✅ Downloaded {downloaded_count}/{len(updated_attachments)} attachments"
        )

        return issue
