"""Tests for comment generator functionality."""

import pytest

from gh_analysis.ai.change_detector import IssueUpdatePlan, LabelChange
from gh_analysis.ai.comment_generator import CommentGenerator


@pytest.fixture
def sample_plan_with_additions() -> IssueUpdatePlan:
    """Sample update plan with label additions."""
    changes = [
        LabelChange(
            action="add",
            label="product::vendor",
            reason="Issue concerns vendor portal functionality",
            confidence=0.92,
        ),
        LabelChange(
            action="add",
            label="product::troubleshoot",
            reason="Contains troubleshooting request",
            confidence=0.85,
        ),
    ]

    return IssueUpdatePlan(
        org="test-org",
        repo="test-repo",
        issue_number=123,
        changes=changes,
        overall_confidence=0.88,
        needs_update=True,
        comment_summary=(
            "Adding vendor and troubleshoot labels based on issue content analysis"
        ),
    )


@pytest.fixture
def sample_plan_with_removals() -> IssueUpdatePlan:
    """Sample update plan with label removals."""
    changes = [
        LabelChange(
            action="remove",
            label="product::kots",
            reason="Analysis indicates this is not KOTS-related",
            confidence=0.78,
        )
    ]

    return IssueUpdatePlan(
        org="test-org",
        repo="test-repo",
        issue_number=456,
        changes=changes,
        overall_confidence=0.82,
        needs_update=True,
        comment_summary="Removing incorrect KOTS label",
    )


@pytest.fixture
def sample_plan_mixed_changes() -> IssueUpdatePlan:
    """Sample update plan with both additions and removals."""
    changes = [
        LabelChange(
            action="add",
            label="product::vendor",
            reason="Issue is about vendor portal",
            confidence=0.90,
        ),
        LabelChange(
            action="remove",
            label="product::kots",
            reason="Not KOTS-related",
            confidence=0.85,
        ),
    ]

    return IssueUpdatePlan(
        org="test-org",
        repo="test-repo",
        issue_number=789,
        changes=changes,
        overall_confidence=0.87,
        needs_update=True,
        comment_summary="Correcting labels based on analysis",
    )


class TestCommentGenerator:
    """Test comment generation functionality."""

    def test_init(self) -> None:
        """Test initialization."""
        generator = CommentGenerator()
        assert generator is not None

    def test_generate_update_comment_with_additions(
        self, sample_plan_with_additions: IssueUpdatePlan
    ) -> None:
        """Test generating comment for label additions."""
        generator = CommentGenerator()
        comment = generator.generate_update_comment(sample_plan_with_additions)

        # Check that comment contains expected elements
        assert "**Label Update**" in comment
        assert "Based on AI analysis" in comment
        assert "**Confidence Level**" in comment

    def test_generate_update_comment_with_removals(
        self, sample_plan_with_removals: IssueUpdatePlan
    ) -> None:
        """Test generating comment for label removals."""
        generator = CommentGenerator()
        comment = generator.generate_update_comment(sample_plan_with_removals)

        # Check that comment contains expected elements
        assert "**Label Update**" in comment
        assert "Based on AI analysis" in comment
        assert "**Confidence Level**" in comment

    def test_generate_update_comment_mixed_changes(
        self, sample_plan_mixed_changes: IssueUpdatePlan
    ) -> None:
        """Test generating comment for mixed changes."""
        generator = CommentGenerator()
        comment = generator.generate_update_comment(sample_plan_mixed_changes)

        # Check that comment contains expected elements
        assert "**Label Update:" in comment
        assert "Based on AI analysis" in comment
        assert "**Confidence Level**" in comment

    def test_generate_update_comment_empty_plan(self) -> None:
        """Test generating comment for plan with no changes."""
        plan = IssueUpdatePlan(
            org="test-org",
            repo="test-repo",
            issue_number=123,
            changes=[],
            overall_confidence=0.9,
            needs_update=False,
            comment_summary="",
        )

        generator = CommentGenerator()
        comment = generator.generate_update_comment(plan)

        assert comment == ""

    def test_generate_dry_run_summary_multiple_plans(
        self,
        sample_plan_with_additions: IssueUpdatePlan,
        sample_plan_with_removals: IssueUpdatePlan,
    ) -> None:
        """Test generating dry run summary for multiple plans."""
        plans = [sample_plan_with_additions, sample_plan_with_removals]

        generator = CommentGenerator()
        summary = generator.generate_dry_run_summary(plans)

        # Check basic structure
        assert "Found 2 issue(s) that need label updates:" in summary
        assert "**Issue #123 (test-org/test-repo/issues/123)**" in summary
        assert "**Issue #456 (test-org/test-repo/issues/456)**" in summary
        assert "Recommendation confidence: 0.88" in summary
        assert "Recommendation confidence: 0.82" in summary

        # Check that reasoning is included with changes
        assert (
            "+ product::vendor - Issue concerns vendor portal functionality"
        ) in summary
        assert ("+ product::troubleshoot - Contains troubleshooting request") in summary
        assert (
            "- product::kots - Analysis indicates this is not KOTS-related"
        ) in summary

        # Check that GitHub comment previews are included
        assert "**GitHub Comment Preview:**" in summary
        assert "**Label Update" in summary
        assert "Based on AI analysis" in summary

    def test_generate_dry_run_summary_no_plans(self) -> None:
        """Test generating dry run summary for no plans."""
        generator = CommentGenerator()
        summary = generator.generate_dry_run_summary([])

        assert "No changes needed based on current confidence threshold." in summary

    def test_dry_run_comment_matches_actual_comment(
        self, sample_plan_with_additions: IssueUpdatePlan
    ) -> None:
        """Test that dry run preview shows exact same comment as actual execution."""
        generator = CommentGenerator()

        # Generate the actual comment that would be posted
        actual_comment = generator.generate_update_comment(sample_plan_with_additions)

        # Generate dry run summary
        dry_run_summary = generator.generate_dry_run_summary(
            [sample_plan_with_additions]
        )

        # Verify the actual comment appears exactly in the dry run summary
        assert actual_comment in dry_run_summary

        # Verify the dry run shows it's a preview
        assert "**GitHub Comment Preview:**" in dry_run_summary

    def test_generate_execution_summary_success_only(
        self, sample_plan_with_additions: IssueUpdatePlan
    ) -> None:
        """Test generating execution summary for successful updates only."""
        successful = [sample_plan_with_additions]
        failed: list[tuple[IssueUpdatePlan, str]] = []

        generator = CommentGenerator()
        summary = generator.generate_execution_summary(successful, failed)

        assert "✅ Successfully updated 1 issue(s):" in summary
        assert "Issue #123: 2 change(s)" in summary
        assert "❌ Failed to update" not in summary

    def test_generate_execution_summary_failures_only(
        self, sample_plan_with_removals: IssueUpdatePlan
    ) -> None:
        """Test generating execution summary for failed updates only."""
        successful: list[IssueUpdatePlan] = []
        failed = [(sample_plan_with_removals, "API rate limit exceeded")]

        generator = CommentGenerator()
        summary = generator.generate_execution_summary(successful, failed)

        assert "❌ Failed to update 1 issue(s):" in summary
        assert "Issue #456: API rate limit exceeded" in summary
        assert "✅ Successfully updated" not in summary

    def test_generate_execution_summary_mixed_results(
        self,
        sample_plan_with_additions: IssueUpdatePlan,
        sample_plan_with_removals: IssueUpdatePlan,
    ) -> None:
        """Test generating execution summary for mixed results."""
        successful = [sample_plan_with_additions]
        failed = [(sample_plan_with_removals, "Permission denied")]

        generator = CommentGenerator()
        summary = generator.generate_execution_summary(successful, failed)

        assert "✅ Successfully updated 1 issue(s):" in summary
        assert "❌ Failed to update 1 issue(s):" in summary
        assert "Issue #123: 2 change(s)" in summary
        assert "Issue #456: Permission denied" in summary

    def test_generate_execution_summary_no_results(self) -> None:
        """Test generating execution summary with no results."""
        generator = CommentGenerator()
        summary = generator.generate_execution_summary([], [])

        assert "No issues processed." in summary
