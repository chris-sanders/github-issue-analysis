"""Centralized vendor AI permission filtering for all Snowflake data loaders."""

from datetime import datetime, timedelta

from .snowflake_base import BaseSnowflakeClient


class VendorAIFilter(BaseSnowflakeClient):
    """Filter repositories based on vendor IS_AI_SUPPORT_ENABLED flag."""

    # Test/internal repos to always filter (no vendor association)
    ALWAYS_FILTERED_REPOS = {
        "superci-replicated",  # Test repository
        "replicated-qa",  # QA repository
        "replicated-dev-test",  # Dev test repository
        "testing-replicated",  # Testing repository
        "slackernews-replicated",  # Demo repository
        "inbound-escalation-catchall",  # Catchall repo
    }

    def __init__(self, cache_ttl_hours: int = 24):
        """Initialize with production database."""
        super().__init__(database="ANALYTICS_PROD", schema="ANALYTICS")
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self._ai_enabled_repo_ids: set[int] | None = None
        self._cache_timestamp: datetime | None = None

    def _refresh_cache(self) -> None:
        """Refresh the cache of AI-enabled repository IDs."""
        query = """
        SELECT DISTINCT REPOSITORY_ID
        FROM ANALYTICS_PROD.ANALYTICS.DIM_VENDORS
        WHERE IS_AI_SUPPORT_ENABLED = true
          AND REPOSITORY_ID IS NOT NULL
        """
        results = self.execute_query(query)
        self._ai_enabled_repo_ids = {row[0] for row in results}
        self._cache_timestamp = datetime.now()
        print(f"📊 Cached {len(self._ai_enabled_repo_ids)} AI-enabled repository IDs")

    def get_ai_enabled_repository_ids(self) -> set[int]:
        """Get set of repository IDs where AI support is enabled."""
        # Check if cache needs refresh
        if (
            self._ai_enabled_repo_ids is None
            or self._cache_timestamp is None
            or datetime.now() - self._cache_timestamp > self.cache_ttl
        ):
            self._refresh_cache()

        return self._ai_enabled_repo_ids

    def should_filter_repo(
        self, repo_name: str, repository_id: int | None = None
    ) -> bool:
        """
        Check if a repository should be filtered out.

        Returns True to filter out (exclude), False to include.
        """
        # Always filter test/internal repos by name
        if repo_name in self.ALWAYS_FILTERED_REPOS:
            return True

        # No repository_id means no vendor (likely test/internal)
        if repository_id is None:
            return True  # Conservative: filter unknown repos

        # Check if repository has AI enabled via vendor
        ai_enabled_ids = self.get_ai_enabled_repository_ids()
        return repository_id not in ai_enabled_ids

    def get_sql_filter_clause(self) -> str:
        """
        Get SQL WHERE clause fragment for efficient database filtering.
        Assumes tables aliased as: i (DIM_ISSUES), v (DIM_VENDORS)
        """
        # Build list of test repos to exclude
        test_repos_list = "', '".join(self.ALWAYS_FILTERED_REPOS)

        return f"""(
            i.REPO_NAME NOT IN ('{test_repos_list}')
            AND v.IS_AI_SUPPORT_ENABLED = true
        )"""
