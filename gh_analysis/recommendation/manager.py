"""Central coordinator for recommendation management operations."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..ai.models import ProductLabelingResponse
from .models import RecommendationFilter, RecommendationMetadata, RecommendationStatus
from .status_tracker import StatusTracker


class RecommendationManager:
    """Central coordinator for recommendation management operations."""

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.issues_dir = data_dir / "issues"
        self.results_dir = data_dir / "results"
        self.status_tracker = StatusTracker(data_dir / "recommendation_status")

    def discover_recommendations(
        self, force_refresh: bool = False
    ) -> list[RecommendationMetadata]:
        """Scan for new AI results and create recommendation metadata."""
        recommendations = []

        # Scan results directory for AI analysis files
        for result_file in self.results_dir.glob("*_product-labeling.json"):
            try:
                # Parse filename to extract org, repo, issue_number
                parts = result_file.stem.split("_")
                if len(parts) >= 4:
                    org = parts[0]
                    repo = parts[1]
                    issue_number = int(parts[3])

                    # Check if we already have status for this recommendation
                    existing = self.status_tracker.get_recommendation(
                        org, repo, issue_number
                    )
                    if existing and not force_refresh:
                        recommendations.append(existing)
                        continue

                    # Load AI result
                    with open(result_file) as f:
                        result_data = json.load(f)

                    ai_analysis = ProductLabelingResponse.model_validate(
                        result_data["analysis"]
                    )

                    # Find corresponding issue file
                    issue_file = (
                        self.issues_dir / f"{org}_{repo}_issue_{issue_number}.json"
                    )
                    if not issue_file.exists():
                        continue

                    # Create recommendation metadata
                    recommendation = self._create_recommendation_metadata(
                        org,
                        repo,
                        issue_number,
                        ai_analysis,
                        str(result_file),
                        str(issue_file),
                    )

                    # Check if this represents an actual change
                    if not self.is_recommendation_change(recommendation):
                        recommendation.status = RecommendationStatus.NO_CHANGE_NEEDED
                        recommendation.status_updated_at = datetime.now()

                    # Save status if new or force refresh
                    if not existing:
                        self.status_tracker.save_recommendation(recommendation)
                    elif force_refresh:
                        # Update existing recommendation with new data
                        if self.is_recommendation_change(recommendation):
                            recommendation.status = RecommendationStatus.PENDING
                        else:
                            recommendation.status = (
                                RecommendationStatus.NO_CHANGE_NEEDED
                            )
                        recommendation.status_updated_at = datetime.now()
                        recommendation.reviewed_at = None
                        recommendation.review_notes = None
                        self.status_tracker.save_recommendation(recommendation)

                    recommendations.append(recommendation)

            except Exception as e:
                print(f"Error processing {result_file}: {e}")
                continue

        return recommendations

    def _create_recommendation_metadata(
        self,
        org: str,
        repo: str,
        issue_number: int,
        ai_analysis: ProductLabelingResponse,
        result_file: str,
        issue_file: str,
    ) -> RecommendationMetadata:
        """Create recommendation metadata from AI analysis."""

        # Extract recommended labels
        recommended_labels = [rec.label.value for rec in ai_analysis.recommended_labels]

        # Extract labels to remove (incorrect current labels)
        labels_to_remove = [
            assessment.label
            for assessment in ai_analysis.current_labels_assessment
            if not assessment.correct
        ]

        # Load issue data to get current labels
        current_labels = []
        try:
            with open(issue_file) as f:
                issue_data = json.load(f)
                # Labels are nested under 'issue' key in the JSON structure
                if "issue" in issue_data:
                    current_labels = [
                        label["name"] for label in issue_data["issue"].get("labels", [])
                    ]
                else:
                    # Fallback to top-level labels if no 'issue' wrapper
                    current_labels = [
                        label["name"] for label in issue_data.get("labels", [])
                    ]
        except Exception:
            pass  # If we can't load issue data, use empty list

        return RecommendationMetadata(
            org=org,
            repo=repo,
            issue_number=issue_number,
            processor_name="product-labeling",
            original_confidence=ai_analysis.recommendation_confidence,
            ai_reasoning=ai_analysis.reasoning,
            root_cause_analysis=(
                ai_analysis.root_cause_analysis
                if ai_analysis.root_cause_analysis != "Root cause unclear"
                else None
            ),
            root_cause_confidence=ai_analysis.root_cause_confidence,
            recommended_labels=recommended_labels,
            labels_to_remove=labels_to_remove,
            current_labels=current_labels,
            status=RecommendationStatus.PENDING,
            status_updated_at=datetime.now(),
            ai_result_file=result_file,
            issue_file=issue_file,
        )

    def get_recommendations(
        self, filter: RecommendationFilter
    ) -> list[RecommendationMetadata]:
        """Get recommendations matching filter criteria."""
        return self.status_tracker.query_recommendations(filter)

    def is_recommendation_change(self, recommendation: RecommendationMetadata) -> bool:
        """Check if recommendation represents a change from current labels."""
        # Get current product labels (filter out non-product labels)
        current_product_labels = [
            label
            for label in recommendation.current_labels
            if label.startswith("product::")
        ]

        # Get recommended product labels
        recommended_product_labels = [
            label
            for label in recommendation.recommended_labels
            if label.startswith("product::")
        ]

        # Check if there's any difference
        # 1. Different number of product labels
        if len(current_product_labels) != len(recommended_product_labels):
            return True

        # 2. Different labels (order doesn't matter)
        if set(current_product_labels) != set(recommended_product_labels):
            return True

        # 3. Labels to remove indicates a change
        if recommendation.labels_to_remove:
            return True

        return False

    def should_reprocess_issue(
        self, org: str, repo: str, issue_number: int, force_reprocess: bool = False
    ) -> bool:
        """Determine if an issue should be reprocessed for AI analysis."""

        if force_reprocess:
            return True  # --reprocess flag processes everything

        # Check if we have an existing recommendation
        recommendation = self.status_tracker.get_recommendation(org, repo, issue_number)

        if not recommendation:
            return True  # No existing recommendation, process it

        # Process if explicitly marked for reanalysis
        if recommendation.status == RecommendationStatus.NEEDS_MODIFICATION:
            return True

        # Skip if already analyzed and reviewed
        if recommendation.status in [
            RecommendationStatus.PENDING,
            RecommendationStatus.NO_CHANGE_NEEDED,
            RecommendationStatus.APPROVED,
            RecommendationStatus.REJECTED,
        ]:
            return False

        return True  # Default to processing

    def get_recommendation_summary(self) -> dict[str, Any]:
        """Get summary statistics for recommendations."""
        all_recommendations = self.status_tracker.get_all_recommendations()

        summary: dict[str, Any] = {
            "total_recommendations": len(all_recommendations),
            "by_status": {},
            "by_product": {},
            "by_confidence_tier": {},
            "by_repository": {},
            "pending_high_confidence": 0,
            "no_change_needed": 0,
            "recently_applied": 0,
        }

        # Calculate statistics
        for rec in all_recommendations:
            # Status distribution
            status = rec.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            # Product distribution
            product = rec.primary_product or "unknown"
            summary["by_product"][product] = summary["by_product"].get(product, 0) + 1

            # Confidence tier distribution
            tier = rec.confidence_tier
            summary["by_confidence_tier"][tier] = (
                summary["by_confidence_tier"].get(tier, 0) + 1
            )

            # Repository distribution
            repo_key = f"{rec.org}/{rec.repo}"
            summary["by_repository"][repo_key] = (
                summary["by_repository"].get(repo_key, 0) + 1
            )

            # Special counts
            if (
                rec.status == RecommendationStatus.PENDING
                and rec.confidence_tier == "high"
            ):
                summary["pending_high_confidence"] += 1

            if rec.status == RecommendationStatus.NO_CHANGE_NEEDED:
                summary["no_change_needed"] += 1

            # Note: recently_applied will be implemented in Phase 2
            # if (rec.status == RecommendationStatus.APPLIED and
            #     rec.applied_at and
            #     (datetime.now() - rec.applied_at).days <= 7):
            #     summary["recently_applied"] += 1

        return summary
