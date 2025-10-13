"""Logic for detecting and planning GitHub issue label changes based on
AI recommendations."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..github_client.models import GitHubIssue, StoredIssue
from ..recommendation.models import RecommendationMetadata, RecommendationStatus
from ..recommendation.status_tracker import StatusTracker
from .models import LabelAssessment, ProductLabelingResponse, RecommendedLabel


@dataclass
class LabelChange:
    """Represents a single label change operation."""

    action: Literal["add", "remove"]
    label: str
    reason: str
    confidence: float


@dataclass
class IssueUpdatePlan:
    """Complete plan for updating a single issue's labels."""

    org: str
    repo: str
    issue_number: int
    changes: list[LabelChange]
    overall_confidence: float
    needs_update: bool
    comment_summary: str
    ai_result: ProductLabelingResponse | None = None
    root_cause_analysis: str | None = None
    ai_reasoning: str | None = None


class ChangeDetector:
    """Detects needed label changes by comparing current labels with
    AI recommendations."""

    def __init__(
        self,
        min_confidence: float = 0.8,
        ignore_status: bool = False,
        data_dir: Path | None = None,
    ):
        """Initialize the change detector.

        Args:
            min_confidence: Minimum confidence threshold for applying changes
            ignore_status: If True, process all recommendations regardless of status
            data_dir: Base data directory for status tracking
        """
        self.min_confidence = min_confidence
        self.ignore_status = ignore_status
        self.status_tracker = (
            StatusTracker(data_dir / "recommendation_status") if data_dir else None
        )

    def detect_changes(
        self,
        issue: GitHubIssue,
        ai_result: ProductLabelingResponse,
        org: str,
        repo: str,
    ) -> IssueUpdatePlan:
        """Detect what label changes are needed for an issue.

        Args:
            issue: The GitHub issue with current labels
            ai_result: AI recommendations for the issue
            org: Organization name
            repo: Repository name

        Returns:
            IssueUpdatePlan with all detected changes
        """
        current_labels = {label.name for label in issue.labels}
        changes: list[LabelChange] = []

        # Use unified confidence filtering
        if ai_result.recommendation_confidence < self.min_confidence:
            # Skip all changes if overall confidence is too low
            return IssueUpdatePlan(
                org=org,
                repo=repo,
                issue_number=issue.number,
                changes=[],
                overall_confidence=ai_result.recommendation_confidence,
                needs_update=False,
                comment_summary="",
                ai_result=ai_result,
                root_cause_analysis=ai_result.root_cause_analysis,
                ai_reasoning=ai_result.reasoning,
            )

        # Process recommended additions
        for recommendation in ai_result.recommended_labels:
            if recommendation.label.value not in current_labels:
                changes.append(
                    LabelChange(
                        action="add",
                        label=recommendation.label.value,
                        reason=recommendation.reasoning,
                        confidence=ai_result.recommendation_confidence,
                    )
                )

        # Process recommended removals based on assessment
        for assessment in ai_result.current_labels_assessment:
            if (
                not assessment.correct
                and assessment.label in current_labels
                and self._should_remove_label(assessment, ai_result.recommended_labels)
            ):
                changes.append(
                    LabelChange(
                        action="remove",
                        label=assessment.label,
                        reason=assessment.reasoning,
                        confidence=ai_result.recommendation_confidence,
                    )
                )

        needs_update = len(changes) > 0
        comment_summary = (
            self._generate_comment_summary(changes, ai_result) if needs_update else ""
        )

        return IssueUpdatePlan(
            org=org,
            repo=repo,
            issue_number=issue.number,
            changes=changes,
            overall_confidence=ai_result.recommendation_confidence,
            needs_update=needs_update,
            comment_summary=comment_summary,
            ai_result=ai_result,
            root_cause_analysis=ai_result.root_cause_analysis,
            ai_reasoning=ai_result.reasoning,
        )

    def _should_remove_label(
        self, assessment: LabelAssessment, recommendations: list[RecommendedLabel]
    ) -> bool:
        """Determine if a label should be removed based on assessment and
        recommendations.

        We only remove labels if:
        1. The assessment says it's incorrect
        2. No recommendation suggests keeping it
        3. The assessment reasoning is specific enough
        """
        # Check if any recommendation suggests this label
        for rec in recommendations:
            if rec.label.value == assessment.label:
                return False

        # Only remove if the reasoning is substantial (not just uncertain)
        return len(assessment.reasoning.strip()) > 20

    def _generate_comment_summary(
        self, changes: list[LabelChange], ai_result: ProductLabelingResponse
    ) -> str:
        """Generate a summary comment explaining the changes."""
        additions = [c for c in changes if c.action == "add"]
        removals = [c for c in changes if c.action == "remove"]

        summary_parts = []

        if additions:
            summary_parts.append(f"Adding {len(additions)} label(s)")
        if removals:
            summary_parts.append(f"Removing {len(removals)} label(s)")

        summary = " and ".join(summary_parts)

        # Add brief reasoning
        if ai_result.summary:
            summary += f" based on analysis: {ai_result.summary[:100]}..."

        return summary

    def load_and_detect_for_file(
        self, issue_file: Path, results_file: Path
    ) -> IssueUpdatePlan | None:
        """Load issue and AI result files and detect changes.

        Args:
            issue_file: Path to stored issue JSON file
            results_file: Path to AI results JSON file

        Returns:
            IssueUpdatePlan if changes needed, None otherwise
        """
        try:
            # Load issue data
            with open(issue_file) as f:
                issue_data = json.load(f)
            stored_issue = StoredIssue(**issue_data)

            # Check recommendation status if status tracking is enabled
            if not self.ignore_status and self.status_tracker:
                recommendation = self.status_tracker.get_recommendation(
                    stored_issue.org, stored_issue.repo, stored_issue.issue.number
                )

                # Skip if recommendation doesn't exist or is not approved
                if (
                    not recommendation
                    or recommendation.status != RecommendationStatus.APPROVED
                ):
                    return None

            # Load AI results
            with open(results_file) as f:
                ai_data = json.load(f)

            # Extract the analysis part if it's wrapped in metadata
            if "analysis" in ai_data:
                analysis_data = ai_data["analysis"]
            else:
                analysis_data = ai_data

            ai_result = ProductLabelingResponse(**analysis_data)

            # Detect changes
            plan = self.detect_changes(
                stored_issue.issue, ai_result, stored_issue.org, stored_issue.repo
            )

            return plan if plan.needs_update else None

        except Exception as e:
            # Log error but don't fail the whole batch
            print(f"Error processing {issue_file}: {e}")
            return None

    def find_matching_files(
        self,
        data_dir: Path,
        org: str,
        repo: str | None,
        issue_number: int | None = None,
    ) -> list[tuple[Path, Path]]:
        """Find matching issue and result files.

        Args:
            data_dir: Base data directory
            org: Organization name
            repo: Repository name (optional - if None, searches all repos in org)
            issue_number: Specific issue number (optional)

        Returns:
            List of (issue_file, result_file) tuples
        """
        issues_dir = data_dir / "issues"
        results_dir = data_dir / "results"

        if not issues_dir.exists() or not results_dir.exists():
            return []

        matches = []

        if repo and issue_number:
            # Single issue in specific repo
            issue_file = issues_dir / f"{org}_{repo}_issue_{issue_number}.json"
            result_file = (
                results_dir / f"{org}_{repo}_issue_{issue_number}_product-labeling.json"
            )

            if issue_file.exists() and result_file.exists():
                matches.append((issue_file, result_file))
        elif repo:
            # All issues in specific repo
            pattern = f"{org}_{repo}_issue_*.json"
            for issue_file in issues_dir.glob(pattern):
                # Extract issue number from filename like: org_repo_issue_123.json
                filename_parts = issue_file.stem.split("_")
                if len(filename_parts) >= 4 and filename_parts[-2] == "issue":
                    issue_num = filename_parts[-1]
                    result_file = (
                        results_dir
                        / f"{org}_{repo}_issue_{issue_num}_product-labeling.json"
                    )

                    if result_file.exists():
                        matches.append((issue_file, result_file))
        else:
            # All issues in organization
            pattern = f"{org}_*_issue_*.json"
            for issue_file in issues_dir.glob(pattern):
                # Extract org, repo, and issue number from filename
                filename_parts = issue_file.stem.split("_")
                if len(filename_parts) >= 4 and filename_parts[-2] == "issue":
                    # Reconstruct the base filename without extension
                    base_name = issue_file.stem
                    result_file = results_dir / f"{base_name}_product-labeling.json"

                    if result_file.exists():
                        matches.append((issue_file, result_file))

        return matches

    def create_plan_from_recommendation(
        self, recommendation: RecommendationMetadata
    ) -> IssueUpdatePlan | None:
        """Create an update plan directly from recommendation metadata.

        This method allows creating plans without needing the original
        issue/result files.

        Args:
            recommendation: The recommendation metadata containing all necessary info

        Returns:
            IssueUpdatePlan if changes needed, None otherwise
        """
        # Skip if not approved (unless ignoring status)
        if (
            not self.ignore_status
            and recommendation.status != RecommendationStatus.APPROVED
        ):
            return None

        # Skip if confidence is too low
        effective_confidence = (
            recommendation.review_confidence or recommendation.original_confidence
        )
        if effective_confidence < self.min_confidence:
            return None

        # Build label changes
        changes: list[LabelChange] = []
        current_labels = set(recommendation.current_labels)

        # Add recommended labels that aren't already present
        for label in recommendation.recommended_labels:
            if label not in current_labels:
                changes.append(
                    LabelChange(
                        action="add",
                        label=label,
                        reason=recommendation.ai_reasoning
                        or f"AI recommendation (conf: {effective_confidence:.2f})",
                        confidence=effective_confidence,
                    )
                )

        # Remove labels that are in labels_to_remove and currently present
        for label in recommendation.labels_to_remove:
            if label in current_labels:
                changes.append(
                    LabelChange(
                        action="remove",
                        label=label,
                        reason=recommendation.ai_reasoning
                        or f"AI marked incorrect ({effective_confidence:.2f})",
                        confidence=effective_confidence,
                    )
                )

        # If no changes needed, return None
        if not changes:
            return None

        # Generate comment summary
        additions = [c for c in changes if c.action == "add"]
        removals = [c for c in changes if c.action == "remove"]

        summary_parts = []
        if additions:
            summary_parts.append(f"Adding {len(additions)} label(s)")
        if removals:
            summary_parts.append(f"Removing {len(removals)} label(s)")

        comment_summary = " and ".join(summary_parts)
        if recommendation.ai_reasoning:
            comment_summary += (
                f" based on analysis: {recommendation.ai_reasoning[:100]}..."
            )

        return IssueUpdatePlan(
            org=recommendation.org,
            repo=recommendation.repo,
            issue_number=recommendation.issue_number,
            changes=changes,
            overall_confidence=effective_confidence,
            needs_update=True,
            comment_summary=comment_summary,
            ai_result=None,  # Not available when working from status files
            root_cause_analysis=recommendation.root_cause_analysis,
            ai_reasoning=recommendation.ai_reasoning,
        )
