"""Tests for change detector functionality."""

from datetime import datetime
from pathlib import Path

import pytest

from gh_analysis.ai.change_detector import (
    ChangeDetector,
    IssueUpdatePlan,
    LabelChange,
)
from gh_analysis.ai.models import (
    LabelAssessment,
    ProductLabel,
    ProductLabelingResponse,
    RecommendedLabel,
)
from gh_analysis.github_client.models import (
    GitHubIssue,
    GitHubLabel,
    GitHubUser,
)


@pytest.fixture
def sample_issue() -> GitHubIssue:
    """Sample GitHub issue for testing."""
    return GitHubIssue(
        number=123,
        title="Test issue",
        body="Test issue body",
        state="open",
        labels=[
            GitHubLabel(
                name="bug", color="d73a4a", description="Something isn't working"
            ),
            GitHubLabel(
                name="product::kots", color="0052cc", description="KOTS related"
            ),
        ],
        user=GitHubUser(login="testuser", id=1),
        comments=[],
        created_at=datetime(2023, 1, 1),
        updated_at=datetime(2023, 1, 1),
    )


@pytest.fixture
def sample_ai_result() -> ProductLabelingResponse:
    """Sample AI result for testing."""
    return ProductLabelingResponse(
        recommendation_confidence=0.9,
        root_cause_confidence=0.8,
        recommended_labels=[
            RecommendedLabel(
                label=ProductLabel.VENDOR,
                reasoning="Issue is about vendor portal functionality",
            ),
        ],
        current_labels_assessment=[
            LabelAssessment(
                label="bug", correct=True, reasoning="This is indeed a bug report"
            ),
            LabelAssessment(
                label="product::kots",
                correct=False,
                reasoning="Issue is primarily about vendor portal, not KOTS core",
            ),
        ],
        summary="Issue about vendor portal with some KOTS integration",
        reasoning="Based on analysis of the issue content",
    )


class TestChangeDetector:
    """Test change detection logic."""

    def test_init_with_default_confidence(self) -> None:
        """Test initialization with default confidence threshold."""
        detector = ChangeDetector()
        assert detector.min_confidence == 0.8

    def test_init_with_custom_confidence(self) -> None:
        """Test initialization with custom confidence threshold."""
        detector = ChangeDetector(min_confidence=0.75)
        assert detector.min_confidence == 0.75

    def test_detect_changes_add_labels(
        self, sample_issue: GitHubIssue, sample_ai_result: ProductLabelingResponse
    ) -> None:
        """Test detecting label additions."""
        detector = ChangeDetector(min_confidence=0.8)
        plan = detector.detect_changes(
            sample_issue, sample_ai_result, "test-org", "test-repo"
        )

        # Should add vendor label (overall confidence 0.9 > 0.8)
        additions = [c for c in plan.changes if c.action == "add"]
        assert len(additions) == 1
        assert additions[0].label == "product::vendor"
        assert additions[0].confidence == 0.9  # Uses overall confidence

    def test_detect_changes_remove_labels(
        self, sample_issue: GitHubIssue, sample_ai_result: ProductLabelingResponse
    ) -> None:
        """Test detecting label removals."""
        detector = ChangeDetector(min_confidence=0.8)
        plan = detector.detect_changes(
            sample_issue, sample_ai_result, "test-org", "test-repo"
        )

        # Should remove product::kots label (assessment says incorrect)
        removals = [c for c in plan.changes if c.action == "remove"]
        assert len(removals) == 1
        assert removals[0].label == "product::kots"
        assert removals[0].confidence == 0.9  # Uses overall confidence

    def test_detect_changes_confidence_filtering(
        self, sample_issue: GitHubIssue, sample_ai_result: ProductLabelingResponse
    ) -> None:
        """Test that low confidence recommendations are filtered out."""
        detector = ChangeDetector(min_confidence=0.95)  # Higher threshold
        plan = detector.detect_changes(
            sample_issue, sample_ai_result, "test-org", "test-repo"
        )

        # Should not make any changes (overall confidence 0.9 < 0.95)
        assert len(plan.changes) == 0
        assert not plan.needs_update

    def test_low_confidence_skips_all_changes(
        self, sample_issue: GitHubIssue, sample_ai_result: ProductLabelingResponse
    ) -> None:
        """Test that low overall confidence skips all changes."""
        # Modify AI result to have low confidence
        sample_ai_result.recommendation_confidence = 0.5

        detector = ChangeDetector(min_confidence=0.8)
        plan = detector.detect_changes(
            sample_issue, sample_ai_result, "test-org", "test-repo"
        )

        # Should not make any changes due to low overall confidence
        assert len(plan.changes) == 0
        assert not plan.needs_update
        assert plan.overall_confidence == 0.5

    def test_detect_changes_no_changes_needed(self, sample_issue: GitHubIssue) -> None:
        """Test when no changes are needed."""
        # AI result that matches current labels
        ai_result = ProductLabelingResponse(
            recommendation_confidence=0.9,
            recommended_labels=[
                RecommendedLabel(
                    label=ProductLabel.KOTS,
                    reasoning="Issue is about KOTS",
                )
            ],
            current_labels_assessment=[
                LabelAssessment(label="bug", correct=True, reasoning="This is a bug"),
                LabelAssessment(
                    label="product::kots",
                    correct=True,
                    reasoning="KOTS label is correct",
                ),
            ],
            summary="Issue is correctly labeled",
            reasoning="All labels are appropriate",
        )

        detector = ChangeDetector(min_confidence=0.8)
        plan = detector.detect_changes(sample_issue, ai_result, "test-org", "test-repo")

        assert len(plan.changes) == 0
        assert not plan.needs_update

    def test_generate_comment_summary(
        self, sample_issue: GitHubIssue, sample_ai_result: ProductLabelingResponse
    ) -> None:
        """Test comment summary generation."""
        detector = ChangeDetector(min_confidence=0.8)
        plan = detector.detect_changes(
            sample_issue, sample_ai_result, "test-org", "test-repo"
        )

        assert plan.comment_summary != ""
        assert "Adding 1 label(s)" in plan.comment_summary
        assert "vendor portal" in plan.comment_summary.lower()

    def test_should_remove_label_logic(self) -> None:
        """Test the label removal decision logic."""
        detector = ChangeDetector()

        # Should remove when assessment is incorrect and reasoning is substantial
        assessment = LabelAssessment(
            label="product::wrong",
            correct=False,
            reasoning=(
                "This label is incorrect because the issue is not about this product"
            ),
        )
        recommendations: list[RecommendedLabel] = []

        assert detector._should_remove_label(assessment, recommendations)

        # Should not remove when reasoning is too short
        assessment_short = LabelAssessment(
            label="product::wrong",
            correct=False,
            reasoning="Wrong",  # Too short
        )

        assert not detector._should_remove_label(assessment_short, recommendations)

        # Should not remove when recommendation suggests keeping it
        assessment_keep = LabelAssessment(
            label="product::kots",
            correct=False,
            reasoning="This label might be incorrect",
        )
        recommendations_keep = [
            RecommendedLabel(
                label=ProductLabel.KOTS,
                reasoning="Actually this is correct",
            )
        ]

        assert not detector._should_remove_label(assessment_keep, recommendations_keep)

    def test_find_matching_files(self, temp_data_dir: Path) -> None:
        """Test finding matching issue and result files."""
        # Create test file structure (flat structure)
        issues_dir = temp_data_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        results_dir = temp_data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Create test files using flat structure
        (issues_dir / "test-org_test-repo_issue_123.json").write_text("{}")
        (results_dir / "test-org_test-repo_issue_123_product-labeling.json").write_text(
            "{}"
        )
        (issues_dir / "test-org_test-repo_issue_456.json").write_text("{}")
        # Missing result file for 456

        detector = ChangeDetector()

        # Test finding all files
        matches = detector.find_matching_files(temp_data_dir, "test-org", "test-repo")
        assert len(matches) == 1
        assert "test-org_test-repo_issue_123.json" in str(matches[0][0])

        # Test finding specific issue
        matches = detector.find_matching_files(
            temp_data_dir, "test-org", "test-repo", 123
        )
        assert len(matches) == 1

        # Test missing issue
        matches = detector.find_matching_files(
            temp_data_dir, "test-org", "test-repo", 999
        )
        assert len(matches) == 0


class TestLabelChange:
    """Test LabelChange dataclass."""

    def test_label_change_creation(self) -> None:
        """Test creating a LabelChange."""
        change = LabelChange(
            action="add", label="product::test", reason="Test reason", confidence=0.9
        )

        assert change.action == "add"
        assert change.label == "product::test"
        assert change.reason == "Test reason"
        assert change.confidence == 0.9


class TestIssueUpdatePlan:
    """Test IssueUpdatePlan dataclass."""

    def test_issue_update_plan_creation(self) -> None:
        """Test creating an IssueUpdatePlan."""
        changes = [LabelChange("add", "product::test", "Test reason", 0.9)]

        plan = IssueUpdatePlan(
            org="test-org",
            repo="test-repo",
            issue_number=123,
            changes=changes,
            overall_confidence=0.85,
            needs_update=True,
            comment_summary="Test summary",
        )

        assert plan.org == "test-org"
        assert plan.repo == "test-repo"
        assert plan.issue_number == 123
        assert len(plan.changes) == 1
        assert plan.overall_confidence == 0.85
        assert plan.needs_update
        assert plan.comment_summary == "Test summary"
