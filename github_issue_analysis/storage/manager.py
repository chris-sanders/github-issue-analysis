"""Storage manager for GitHub issues."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from ..github_client.models import AttachmentMetadata, GitHubIssue, StoredIssue

console = Console()


class StorageManager:
    """Manages storage of GitHub issues as JSON files."""

    def __init__(self, base_path: str = "data/issues"):
        """Initialize storage manager.

        Args:
            base_path: Base directory for storing issue files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, org: str, repo: str, issue_number: int) -> str:
        """Generate filename for an issue.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number

        Returns:
            Filename string
        """
        return f"{org}_{repo}_issue_{issue_number}.json"

    def _get_file_path(self, org: str, repo: str, issue_number: int) -> Path:
        """Get full file path for an issue.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number

        Returns:
            Path object for the issue file
        """
        filename = self._generate_filename(org, repo, issue_number)
        return self.base_path / filename

    def save_issue(
        self,
        org: str,
        repo: str,
        issue: GitHubIssue,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Save an issue to JSON file.

        Args:
            org: Organization name
            repo: Repository name
            issue: GitHubIssue object to save
            metadata: Additional metadata to include

        Returns:
            Path to the saved file
        """
        if metadata is None:
            metadata = {}

        # Add default metadata
        metadata.update(
            {
                "collection_timestamp": datetime.now().isoformat(),
                "api_version": "v4",
                "tool_version": "0.1.0",
            }
        )

        stored_issue = StoredIssue(org=org, repo=repo, issue=issue, metadata=metadata)

        file_path = self._get_file_path(org, repo, issue.number)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(
                    stored_issue.model_dump(),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,  # Handle datetime objects
                )

            console.print(f"Saved issue #{issue.number} to {file_path}")
            return file_path

        except Exception as e:
            console.print(f"Error saving issue #{issue.number}: {e}")
            raise

    def save_issues(
        self,
        org: str,
        repo: str,
        issues: list[GitHubIssue],
        metadata: dict[str, Any] | None = None,
    ) -> list[Path]:
        """Save multiple issues to JSON files.

        Args:
            org: Organization name
            repo: Repository name
            issues: List of GitHubIssue objects to save
            metadata: Additional metadata to include for all issues

        Returns:
            List of paths to saved files
        """
        saved_paths = []

        for issue in issues:
            try:
                path = self.save_issue(org, repo, issue, metadata)
                saved_paths.append(path)
            except Exception as e:
                console.print(f"Failed to save issue #{issue.number}: {e}")
                continue

        console.print(f"Saved {len(saved_paths)} out of {len(issues)} issues")
        return saved_paths

    def load_issue(self, org: str, repo: str, issue_number: int) -> StoredIssue | None:
        """Load an issue from JSON file.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number

        Returns:
            StoredIssue object or None if not found
        """
        file_path = self._get_file_path(org, repo, issue_number)

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                return StoredIssue.model_validate(data)

        except Exception as e:
            console.print(f"Error loading issue #{issue_number}: {e}")
            return None

    def load_issues(
        self, org: str, repo: str | None = None, issue_number: int | None = None
    ) -> list[StoredIssue]:
        """Load issues from JSON files.

        Args:
            org: Organization name
            repo: Repository name (optional, loads all repos in org if None)
            issue_number: Specific issue number (optional, loads all issues if None)

        Returns:
            List of StoredIssue objects
        """
        issues = []

        if issue_number is not None:
            # Load single issue
            if repo is None:
                raise ValueError("Repository name required when loading single issue")
            issue = self.load_issue(org, repo, issue_number)
            if issue:
                issues.append(issue)
        else:
            # Load multiple issues
            if repo is not None:
                # Load all issues from specific repo
                pattern = f"{org}_{repo}_issue_*.json"
            else:
                # Load all issues from organization
                pattern = f"{org}_*_issue_*.json"

            for file_path in self.base_path.glob(pattern):
                try:
                    with open(file_path, encoding="utf-8") as f:
                        data = json.load(f)
                        issue = StoredIssue.model_validate(data)
                        issues.append(issue)
                except Exception as e:
                    console.print(f"Error loading {file_path}: {e}")
                    continue

        return issues

    def list_stored_issues(
        self, org: str | None = None, repo: str | None = None
    ) -> list[str]:
        """List all stored issue filenames.

        Args:
            org: Filter by organization (optional)
            repo: Filter by repository (optional)

        Returns:
            List of issue filenames
        """
        pattern = "*_issue_*.json"

        if org and repo:
            pattern = f"{org}_{repo}_issue_*.json"
        elif org:
            pattern = f"{org}_*_issue_*.json"

        return [f.name for f in self.base_path.glob(pattern)]

    def get_storage_stats(self) -> dict[str, Any]:
        """Get statistics about stored issues.

        Returns:
            Dictionary with storage statistics
        """
        all_files = list(self.base_path.glob("*_issue_*.json"))

        total_files = len(all_files)
        total_size = sum(f.stat().st_size for f in all_files)

        # Count issues by repository
        repo_counts: dict[str, int] = {}
        for f in all_files:
            parts = f.stem.split("_issue_")[0].split("_")
            if len(parts) >= 2:
                org = parts[0]
                repo = "_".join(parts[1:])
                repo_key = f"{org}/{repo}"
                repo_counts[repo_key] = repo_counts.get(repo_key, 0) + 1

        return {
            "total_issues": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "repositories": repo_counts,
            "storage_path": str(self.base_path.absolute()),
        }

    def save_attachment_metadata(
        self,
        org: str,
        repo: str,
        issue_number: int,
        attachment_metadata: AttachmentMetadata,
    ) -> Path:
        """Save attachment metadata to JSON file.

        Args:
            org: Organization name
            repo: Repository name
            issue_number: Issue number
            attachment_metadata: AttachmentMetadata object to save

        Returns:
            Path to the saved metadata file
        """
        attachments_dir = Path("data/attachments")
        attachments_dir.mkdir(parents=True, exist_ok=True)

        issue_dir = attachments_dir / f"{org}_{repo}_issue_{issue_number}"
        issue_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = issue_dir / "attachment_metadata.json"

        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(
                    attachment_metadata.model_dump(),
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,  # Handle datetime objects
                )

            console.print(f"Saved attachment metadata to {metadata_file}")
            return metadata_file

        except Exception as e:
            console.print(f"Error saving attachment metadata: {e}")
            raise
