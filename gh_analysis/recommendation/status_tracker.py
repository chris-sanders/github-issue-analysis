"""Handles persistence and querying of recommendation status."""

import json
from pathlib import Path

from .models import RecommendationFilter, RecommendationMetadata


class StatusTracker:
    """Handles persistence and querying of recommendation status."""

    def __init__(self, status_dir: Path):
        self.status_dir = status_dir
        self.status_dir.mkdir(parents=True, exist_ok=True)

        # Store all recommendations in main directory (archival added in Phase 2)
        self.recommendations_dir = status_dir
        self.recommendations_dir.mkdir(exist_ok=True)

    def save_recommendation(self, recommendation: RecommendationMetadata) -> None:
        """Save or update recommendation status."""
        file_path = self._get_status_file_path(recommendation)

        with open(file_path, "w") as f:
            json.dump(recommendation.model_dump(), f, indent=2, default=str)

    def get_recommendation(
        self, org: str, repo: str, issue_number: int
    ) -> RecommendationMetadata | None:
        """Get recommendation by identifier."""
        file_path = (
            self.recommendations_dir / f"{org}_{repo}_issue_{issue_number}_status.json"
        )

        if not file_path.exists():
            return None

        try:
            with open(file_path) as f:
                data = json.load(f)
            return RecommendationMetadata.model_validate(data)
        except Exception as e:
            print(f"Error loading recommendation {file_path}: {e}")
            return None

    def query_recommendations(
        self, filter: RecommendationFilter
    ) -> list[RecommendationMetadata]:
        """Query recommendations with filtering."""
        recommendations = self.get_all_recommendations()
        filtered = []

        for rec in recommendations:
            if self._matches_filter(rec, filter):
                filtered.append(rec)

        # Apply pagination
        if filter.offset:
            filtered = filtered[filter.offset :]
        if filter.limit:
            filtered = filtered[: filter.limit]

        return filtered

    def _matches_filter(
        self, rec: RecommendationMetadata, filter: RecommendationFilter
    ) -> bool:
        """Check if recommendation matches filter criteria."""

        # Basic filters
        if filter.org and rec.org != filter.org:
            return False
        if filter.repo and rec.repo != filter.repo:
            return False
        if filter.status and rec.status not in filter.status:
            return False

        # Confidence filters
        effective_confidence = rec.review_confidence or rec.original_confidence
        if filter.min_confidence and effective_confidence < filter.min_confidence:
            return False
        if filter.max_confidence and effective_confidence > filter.max_confidence:
            return False
        if filter.confidence_tier and rec.confidence_tier not in filter.confidence_tier:
            return False

        # Product filters
        if filter.product:
            rec_product = rec.primary_product
            if not rec_product or rec_product not in filter.product:
                return False

        # Date filters
        if filter.created_after and rec.status_updated_at < filter.created_after:
            return False
        if filter.created_before and rec.status_updated_at > filter.created_before:
            return False
        if filter.reviewed_after and (
            not rec.reviewed_at or rec.reviewed_at < filter.reviewed_after
        ):
            return False
        if filter.reviewed_before and (
            not rec.reviewed_at or rec.reviewed_at > filter.reviewed_before
        ):
            return False

        # Text search
        if filter.search_text:
            search_lower = filter.search_text.lower()
            searchable_text = f"{rec.ai_reasoning} {rec.review_notes or ''}".lower()
            if search_lower not in searchable_text:
                return False

        return True

    def get_all_recommendations(self) -> list[RecommendationMetadata]:
        """Get all recommendations."""
        recommendations = []

        for status_file in self.recommendations_dir.glob("*_status.json"):
            try:
                with open(status_file) as f:
                    data = json.load(f)
                recommendations.append(RecommendationMetadata.model_validate(data))
            except Exception as e:
                print(f"Error loading {status_file}: {e}")

        # Sort by org, repo, issue_number for consistent ordering
        recommendations.sort(key=lambda r: (r.org, r.repo, r.issue_number))
        return recommendations

    def _get_status_file_path(self, recommendation: RecommendationMetadata) -> Path:
        """Get file path for recommendation status."""
        return self.recommendations_dir / (
            f"{recommendation.org}_{recommendation.repo}_issue_"
            f"{recommendation.issue_number}_status.json"
        )
