"""Minimal utilities for GitHub issue experiments.

Only what's actually needed.
"""

import json
import os
from pathlib import Path
from typing import Any

from gh_analysis.github_client import GitHubClient
from gh_analysis.github_client.attachments import AttachmentDownloader
from gh_analysis.storage import StorageManager

from .snowflake_base import BaseSnowflakeClient
from .types import StoredIssueDict
from .vendor_filter import VendorAIFilter

# Type alias for issue references: (org, repo, issue_number)
IssueRef = tuple[str, str, int]


class IssueLoader:
    """Simple issue loading utility."""

    def __init__(
        self, storage: StorageManager | None = None, truncate_comments: bool = True
    ):
        self.storage = storage or StorageManager()
        self.truncate_comments = truncate_comments

    async def load_issues(self, issue_refs: list[IssueRef]) -> list[StoredIssueDict]:
        """Load issues from storage, downloading only if missing.

        Args:
            issue_refs: List of (org, repo, issue_number) tuples

        Returns:
            List of StoredIssue data dictionaries.
            Each StoredIssue contains: {"org": str, "repo": str, "issue": GitHubIssue, "metadata": dict}
        """
        # Check which issues need downloading
        missing_issues = []
        stored_issues = []

        for org, repo, issue_number in issue_refs:
            try:
                stored_issue = self.storage.load_issue(org, repo, issue_number)
                if stored_issue:
                    issue_dict = stored_issue.model_dump()
                    if self.truncate_comments:
                        issue_dict = self._truncate_large_comments(issue_dict)
                    stored_issues.append(issue_dict)
                    print(f"Using cached {org}/{repo}-{issue_number} ✓")
                else:
                    missing_issues.append((org, repo, issue_number))
            except Exception as e:
                print(f"❌ Error loading {org}/{repo}-{issue_number}: {e}")
                missing_issues.append((org, repo, issue_number))

        # Download only missing issues
        if missing_issues:
            print(f"📥 Downloading {len(missing_issues)} missing issues...")
            await self._download_issues(missing_issues)

            # Load the newly downloaded issues
            for org, repo, issue_number in missing_issues:
                try:
                    stored_issue = self.storage.load_issue(org, repo, issue_number)
                    if stored_issue:
                        issue_dict = stored_issue.model_dump()
                        if self.truncate_comments:
                            issue_dict = self._truncate_large_comments(issue_dict)
                        stored_issues.append(issue_dict)
                    else:
                        print(
                            f"⚠️  Issue {org}/{repo}-{issue_number} still not found after download"
                        )
                except Exception as e:
                    print(
                        f"❌ Error loading {org}/{repo}-{issue_number} after download: {e}"
                    )

        return stored_issues

    def _truncate_large_comments(self, issue_dict: dict[str, Any]) -> dict[str, Any]:
        """Truncate very large comments in issue data to prevent context overflow.

        Comments over 5000 chars are truncated to 3500 chars (2000 head + 1500 tail)
        to preserve both beginning context and final results.
        """
        # Make a copy to avoid modifying the original
        filtered_issue = issue_dict.copy()

        if "issue" in filtered_issue and "comments" in filtered_issue["issue"]:
            truncated_comments = []
            for comment in filtered_issue["issue"]["comments"]:
                body = comment["body"]
                # Truncate very large comments (likely command output or logs)
                if len(body) > 5000:
                    head_size = 2000
                    tail_size = 1500
                    truncated_body = (
                        f"{body[:head_size]}\n\n"
                        f"[... truncated {len(body) - head_size - tail_size:,} characters ...]\n\n"
                        f"{body[-tail_size:]}"
                    )
                    # Create new comment dict with truncated body
                    truncated_comment = comment.copy()
                    truncated_comment["body"] = truncated_body
                    truncated_comments.append(truncated_comment)
                else:
                    truncated_comments.append(comment)

            filtered_issue["issue"]["comments"] = truncated_comments

        return filtered_issue

    async def _download_issues(self, issue_refs: list[IssueRef]) -> None:
        """Download missing issues from GitHub, including attachments."""
        # Check GitHub token
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            raise ValueError("GITHUB_TOKEN environment variable not set")

        client = GitHubClient(github_token)
        downloader = AttachmentDownloader(github_token)

        for org, repo, issue_num in issue_refs:
            try:
                print(
                    f"Downloading {org}/{repo}-{issue_num} (with attachments)...",
                    end="",
                    flush=True,
                )
                issue_data = client.get_issue(org, repo, issue_num)

                # Process attachments (detect them)
                issue_with_attachments = downloader.process_issue_attachments(
                    issue_data
                )

                # Download attachments if any were found
                if issue_with_attachments.attachments:
                    print(
                        f" [{len(issue_with_attachments.attachments)} attachments]...",
                        end="",
                        flush=True,
                    )
                    from pathlib import Path

                    base_dir = Path("data/attachments")
                    issue_with_attachments = (
                        await downloader.download_issue_attachments(
                            issue_with_attachments, base_dir, org, repo
                        )
                    )

                self.storage.save_issue(org, repo, issue_with_attachments)
                print(" ✓")
            except Exception as e:
                print(f" ✗ Error: {e}")


class SnowflakeIssueLoader(BaseSnowflakeClient):
    """Issue loader that queries Snowflake for issue data with dynamic AI permission filtering."""

    def __init__(
        self,
        account: str | None = None,
        user: str | None = None,
        private_key_path: str | None = None,
        private_key_passphrase: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        cache_dir: str | None = None,
        truncate_at_reply: bool = False,
        number_of_comments: int | None = None,
        truncate_comments: bool = True,
    ):
        """Initialize with Snowflake connection parameters and issue-specific options."""
        # Initialize base Snowflake client with HARDCODED production database
        super().__init__(
            account=account,
            user=user,
            private_key_path=private_key_path,
            private_key_passphrase=private_key_passphrase,
            warehouse=warehouse,
            database="ANALYTICS_PROD",  # HARDCODED - always read from production
            schema="ANALYTICS",  # HARDCODED - always use analytics schema
        )

        # Issue-specific configuration
        self.cache_dir = Path(cache_dir or "data/snowflake_issues")
        self.truncate_at_reply = truncate_at_reply
        self.number_of_comments = number_of_comments
        self.truncate_comments = truncate_comments

        # Initialize AI permission filter
        self.vendor_filter = VendorAIFilter()

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, org: str, repo: str, issue_number: int) -> Path:
        """Get the cache file path for an issue. Always cache raw unfiltered data."""
        return self.cache_dir / f"{org}_{repo}_issue_{issue_number}.json"

    def _load_from_cache(
        self, org: str, repo: str, issue_number: int
    ) -> dict[str, Any] | None:
        """Load issue data from cache if it exists."""
        cache_path = self._get_cache_path(org, repo, issue_number)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    return json.load(f)
            except Exception as e:
                print(
                    f"Warning: Failed to load cached issue {org}/{repo}-{issue_number}: {e}"
                )
        return None

    def _save_to_cache(
        self, org: str, repo: str, issue_number: int, issue_data: dict[str, Any]
    ) -> None:
        """Save issue data to cache."""
        cache_path = self._get_cache_path(org, repo, issue_number)
        try:
            with open(cache_path, "w") as f:
                json.dump(issue_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Warning: Failed to cache issue {org}/{repo}-{issue_number}: {e}")

    def _parse_labels(self, labels_data) -> list[dict[str, str]]:
        """Parse labels from Snowflake format to GitHub API format.

        Snowflake LABELS column contains a bracketed comma-separated string like:
        '[severity::s3, status::closed, new_install]'

        Args:
            labels_data: Bracketed comma-separated string from Snowflake LABELS column

        Returns:
            List of dicts in format [{"name": "label1"}, {"name": "label2"}]
        """
        if not labels_data:
            return []

        # Snowflake LABELS column is a bracketed comma-separated string
        if isinstance(labels_data, str):
            labels_data = labels_data.strip()
            if labels_data.startswith("[") and labels_data.endswith("]"):
                # Remove brackets and split by comma
                content = labels_data[1:-1].strip()
                if not content:
                    return []
                labels = [label.strip() for label in content.split(",")]
                return [{"name": label} for label in labels if label]
            else:
                raise ValueError(
                    f"Expected bracketed format in LABELS column, got: {labels_data}"
                )

        raise ValueError(
            f"Expected string from Snowflake LABELS column, got {type(labels_data)}: {labels_data}"
        )

    def _apply_comment_filtering(self, issue_data: dict[str, Any]) -> dict[str, Any]:
        """Apply comment filtering to issue data if enabled.

        If number_of_comments is set:
        - Take exactly that many comments

        Else if truncate_at_reply is True:
        - Truncate comments before the first replicated response
        """
        # Make a copy to avoid modifying the original
        filtered_issue = issue_data.copy()
        filtered_issue["issue"] = issue_data["issue"].copy()

        comments = issue_data["issue"].get("comments", [])
        if not comments:
            return filtered_issue

        # If number_of_comments is set, just take that many
        if self.number_of_comments is not None:
            filtered_issue["issue"]["comments"] = comments[: self.number_of_comments]
            return filtered_issue

        # Otherwise check truncate_at_reply
        if not self.truncate_at_reply:
            return issue_data

        # Find first replicated response index
        first_reply_idx = None
        for i, comment in enumerate(comments):
            if comment.get("is_first_replicated_response"):
                first_reply_idx = i
                break

        if first_reply_idx is None:
            # No replicated response found, return all comments
            return filtered_issue

        # Truncate before the first replicated response
        filtered_issue["issue"]["comments"] = comments[:first_reply_idx]
        return filtered_issue

    def _truncate_large_comments(self, issue_dict: dict[str, Any]) -> dict[str, Any]:
        """Truncate very large comments in issue data to prevent context overflow.

        Comments over 5000 chars are truncated to 3500 chars (2000 head + 1500 tail)
        to preserve both beginning context and final results.
        """
        # Make a copy to avoid modifying the original
        filtered_issue = issue_dict.copy()

        if "issue" in filtered_issue and "comments" in filtered_issue["issue"]:
            truncated_comments = []
            for comment in filtered_issue["issue"]["comments"]:
                body = comment["body"]
                # Truncate very large comments (likely command output or logs)
                if len(body) > 5000:
                    head_size = 2000
                    tail_size = 1500
                    truncated_body = (
                        f"{body[:head_size]}\n\n"
                        f"[... truncated {len(body) - head_size - tail_size:,} characters ...]\n\n"
                        f"{body[-tail_size:]}"
                    )
                    # Create new comment dict with truncated body
                    truncated_comment = comment.copy()
                    truncated_comment["body"] = truncated_body
                    truncated_comments.append(truncated_comment)
                else:
                    truncated_comments.append(comment)

            filtered_issue["issue"]["comments"] = truncated_comments

        return filtered_issue

    async def load_issues(self, issue_refs: list[IssueRef]) -> list[StoredIssueDict]:
        """Load issues from cache or Snowflake with AI permission filtering."""
        # Pre-filter known test repos to avoid unnecessary queries
        filtered_refs = [
            (org, repo, issue_number)
            for org, repo, issue_number in issue_refs
            if repo not in self.vendor_filter.ALWAYS_FILTERED_REPOS
        ]

        if len(filtered_refs) < len(issue_refs):
            filtered_count = len(issue_refs) - len(filtered_refs)
            print(f"⚠️ Filtered out {filtered_count} issues from test repositories")

        print(f"📥 Loading {len(filtered_refs)} issues from Snowflake...")

        issues = []
        missing_issues = []

        # Check cache first
        for org, repo, issue_number in filtered_refs:
            cached_data = self._load_from_cache(org, repo, issue_number)
            if cached_data:
                # Apply filtering to cached data
                filtered_data = self._apply_comment_filtering(cached_data)
                if self.truncate_comments:
                    filtered_data = self._truncate_large_comments(filtered_data)
                issues.append(filtered_data)
                print(f"Using cached {org}/{repo}-{issue_number} ✓")
            else:
                missing_issues.append((org, repo, issue_number))

        # Query Snowflake for missing issues
        if missing_issues:
            print(f"📥 Querying {len(missing_issues)} missing issues from Snowflake...")

            with self._get_connection() as conn:
                cursor = conn.cursor()

                for org, repo, issue_number in missing_issues:
                    try:
                        print(
                            f"Querying {org}/{repo}-{issue_number}...",
                            end="",
                            flush=True,
                        )

                        # Query with vendor join for AI filtering
                        query = f"""
                        SELECT
                            i.ISSUE_NUMBER,
                            i.TITLE,
                            i.BODY,
                            i.OPENED_AT,
                            i.CLOSED_AT,
                            i.CREATOR_HANDLE,
                            i.LABELS,
                            i.REPOSITORY_ID,
                            c.BODY as COMMENT_BODY,
                            c.CREATED_AT as COMMENT_CREATED_AT,
                            c.HANDLE as COMMENT_USER,
                            c.IS_FIRST_REPLICATED_RESPONSE,
                            v.IS_AI_SUPPORT_ENABLED
                        FROM "ANALYTICS_PROD"."ANALYTICS"."DIM_ISSUES" i
                        LEFT JOIN "ANALYTICS_PROD"."ANALYTICS"."DIM_VENDORS" v
                            ON i.REPOSITORY_ID = v.REPOSITORY_ID
                        LEFT JOIN "ANALYTICS_PROD"."ANALYTICS"."DIM_ISSUE_COMMENTS" c
                            ON i.ISSUE_ID = c.ISSUE_ID
                        WHERE i.ORG_NAME = %s AND i.REPO_NAME = %s AND i.ISSUE_NUMBER = %s
                            AND i.IS_INBOUND_ESCALATION = true
                            AND {self.vendor_filter.get_sql_filter_clause()}
                        ORDER BY i.ISSUE_ID, c.CREATED_AT
                        """

                        cursor.execute(query, (org, repo, issue_number))
                        results = cursor.fetchall()

                        if results:
                            # Double-check with vendor filter (belt and suspenders)
                            repository_id = results[0][7]  # REPOSITORY_ID column
                            if self.vendor_filter.should_filter_repo(
                                repo, repository_id
                            ):
                                print(f" ⚠️ Filtered {repo} (AI support disabled)")
                                continue

                            # Separate issue body from comments
                            first_row = results[0]
                            issue_body = first_row[2] or ""

                            # Build comments array in same format as GitHub (with extra Snowflake fields)
                            comments = []
                            for row in results:
                                comment_body = row[
                                    8
                                ]  # COMMENT_BODY (shifted due to REPOSITORY_ID)
                                comment_created_at = row[9]  # COMMENT_CREATED_AT
                                comment_user = row[10]  # COMMENT_USER
                                is_first_replicated_response = row[
                                    11
                                ]  # IS_FIRST_REPLICATED_RESPONSE

                                if comment_body:
                                    comments.append(
                                        {
                                            "user": {
                                                "login": comment_user or "unknown"
                                            },
                                            "body": comment_body,
                                            "created_at": comment_created_at,
                                            "is_first_replicated_response": is_first_replicated_response,
                                        }
                                    )

                            # Don't filter here - cache raw data and filter at read time

                            # Convert to format expected by analysis code
                            issue_data = {
                                "org": org,
                                "repo": repo,
                                "issue": {
                                    "number": first_row[0],
                                    "title": first_row[1],
                                    "body": issue_body,  # Keep original body separate from comments
                                    "state": "closed",  # We know these are closed from the query
                                    "created_at": first_row[3],
                                    "updated_at": first_row[4],
                                    "user": {"login": first_row[5]}
                                    if first_row[5]
                                    else None,
                                    "labels": self._parse_labels(first_row[6]),
                                    "comments": comments,  # Structured comments array like GitHub
                                    "attachments": [],  # No attachments from Snowflake
                                },
                            }

                            # Save to cache (raw unfiltered data)
                            self._save_to_cache(org, repo, issue_number, issue_data)

                            # Apply filtering for return
                            filtered_data = self._apply_comment_filtering(issue_data)
                            if self.truncate_comments:
                                filtered_data = self._truncate_large_comments(
                                    filtered_data
                                )
                            issues.append(filtered_data)
                            print(" ✓")
                        else:
                            print(" ✗ Not found")

                    except Exception as e:
                        print(f" ✗ Error: {e}")

        return issues

    async def get_recent_closed_cases(self, limit: int = 5) -> list[IssueRef]:
        """Get the most recently closed cases from Snowflake, excluding filtered repos.

        Args:
            limit: Number of recent cases to return

        Returns:
            List of (org_name, repo_name, issue_number) tuples
        """
        try:
            # Query with vendor join for AI filtering
            query = f"""
            SELECT DISTINCT
                i.ORG_NAME,
                i.REPO_NAME,
                i.ISSUE_NUMBER,
                i.CLOSED_AT
            FROM "ANALYTICS_PROD"."ANALYTICS"."DIM_ISSUES" i
            LEFT JOIN "ANALYTICS_PROD"."ANALYTICS"."DIM_VENDORS" v
                ON i.REPOSITORY_ID = v.REPOSITORY_ID
            WHERE i.IS_INBOUND_ESCALATION = true
                AND i.CLOSED_AT IS NOT NULL
                AND {self.vendor_filter.get_sql_filter_clause()}
            ORDER BY i.CLOSED_AT DESC
            LIMIT %s
            """

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (limit,))
                results = cursor.fetchall()

            print(f"📊 Found {len(results)} recently closed cases")

            # Convert to (org, repo, issue_number) tuples
            case_tuples = []
            for row in results:
                org_name, repo_name, issue_number, closed_at = row
                # Results are already filtered by SQL, but we can still validate
                case_tuples.append((org_name, repo_name, issue_number))
                print(
                    f"   - {repo_name.split('/')[-1]}-{issue_number} (closed: {closed_at})"
                )

            return case_tuples

        except Exception as e:
            print(f"❌ Failed to get recent closed cases: {e}")
            return []
