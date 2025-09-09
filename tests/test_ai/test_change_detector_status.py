"""Tests for ChangeDetector status filtering functionality."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from gh_analysis.ai.change_detector import ChangeDetector


class TestChangeDetectorStatusFiltering:
    """Test status filtering in ChangeDetector."""

    @pytest.fixture
    def detector_with_status(self, temp_data_dir: Path) -> ChangeDetector:
        """Create detector with status tracking enabled."""
        return ChangeDetector(
            min_confidence=0.8, ignore_status=False, data_dir=temp_data_dir
        )

    @pytest.fixture
    def detector_ignore_status(self, temp_data_dir: Path) -> ChangeDetector:
        """Create detector with status tracking disabled."""
        return ChangeDetector(
            min_confidence=0.8, ignore_status=True, data_dir=temp_data_dir
        )

    @pytest.fixture
    def sample_files(self, temp_data_dir: Path) -> tuple[Path, Path]:
        """Create sample issue and result files."""
        issues_dir = temp_data_dir / "issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        results_dir = temp_data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Sample issue data
        issue_data = {
            "org": "test-org",
            "repo": "test-repo",
            "issue": {
                "number": 123,
                "title": "Test issue",
                "body": "Test issue body",
                "state": "open",
                "labels": [
                    {"name": "bug", "color": "d73a4a", "description": "Bug"},
                    {"name": "product::kots", "color": "0052cc", "description": "KOTS"},
                ],
                "user": {"login": "testuser", "id": 1},
                "comments": [],
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z",
            },
            "metadata": {},
        }

        # Sample AI result data
        ai_result_data = {
            "recommendation_confidence": 0.9,
            "recommended_labels": [
                {"label": "product::vendor", "reasoning": "Test reasoning"}
            ],
            "current_labels_assessment": [
                {"label": "bug", "correct": True, "reasoning": "Test"},
                {"label": "product::kots", "correct": False, "reasoning": "Test"},
            ],
            "summary": "Test summary",
            "reasoning": "Test reasoning",
            "images_analyzed": [],
            "image_impact": "",
        }

        issue_file = issues_dir / "test-org_test-repo_issue_123.json"
        result_file = results_dir / "test-org_test-repo_issue_123_product-labeling.json"

        issue_file.write_text(json.dumps(issue_data))
        result_file.write_text(json.dumps(ai_result_data))

        return issue_file, result_file

    def test_load_and_detect_with_approved_status(
        self,
        detector_with_status: ChangeDetector,
        sample_files: tuple[Path, Path],
        temp_data_dir: Path,
    ) -> None:
        """Test that approved recommendations are processed."""
        issue_file, result_file = sample_files

        # Create approved status
        status_dir = temp_data_dir / "recommendation_status"
        status_dir.mkdir(parents=True, exist_ok=True)

        status_data = {
            "org": "test-org",
            "repo": "test-repo",
            "issue_number": 123,
            "processor_name": "product-labeling",
            "original_confidence": 0.9,
            "ai_reasoning": "Test reasoning",
            "root_cause_analysis": None,
            "root_cause_confidence": None,
            "recommended_labels": ["product::vendor"],
            "labels_to_remove": ["product::kots"],
            "current_labels": ["bug", "product::kots"],
            "status": "approved",
            "status_updated_at": datetime.now().isoformat(),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_confidence": None,
            "review_notes": None,
            "modified_labels": None,
            "ai_result_file": "test-org_test-repo_issue_123_product-labeling.json",
            "issue_file": "test-org_test-repo_issue_123.json",
        }

        (status_dir / "test-org_test-repo_issue_123_status.json").write_text(
            json.dumps(status_data)
        )

        # Should process approved recommendation
        plan = detector_with_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is not None
        assert plan.org == "test-org"
        assert plan.repo == "test-repo"
        assert plan.issue_number == 123
        assert len(plan.changes) > 0

    def test_load_and_detect_with_pending_status(
        self,
        detector_with_status: ChangeDetector,
        sample_files: tuple[Path, Path],
        temp_data_dir: Path,
    ) -> None:
        """Test that pending recommendations are skipped."""
        issue_file, result_file = sample_files

        # Create pending status
        status_dir = temp_data_dir / "recommendation_status"
        status_dir.mkdir(parents=True, exist_ok=True)

        status_data = {
            "org": "test-org",
            "repo": "test-repo",
            "issue_number": 123,
            "processor_name": "product-labeling",
            "original_confidence": 0.9,
            "ai_reasoning": "Test reasoning",
            "root_cause_analysis": None,
            "root_cause_confidence": None,
            "recommended_labels": ["product::vendor"],
            "labels_to_remove": [],
            "current_labels": ["bug"],
            "status": "pending",  # Not approved
            "status_updated_at": datetime.now().isoformat(),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_confidence": None,
            "review_notes": None,
            "modified_labels": None,
            "ai_result_file": "test-org_test-repo_issue_123_product-labeling.json",
            "issue_file": "test-org_test-repo_issue_123.json",
        }

        (status_dir / "test-org_test-repo_issue_123_status.json").write_text(
            json.dumps(status_data)
        )

        # Should skip pending recommendation
        plan = detector_with_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is None

    def test_load_and_detect_with_rejected_status(
        self,
        detector_with_status: ChangeDetector,
        sample_files: tuple[Path, Path],
        temp_data_dir: Path,
    ) -> None:
        """Test that rejected recommendations are skipped."""
        issue_file, result_file = sample_files

        # Create rejected status
        status_dir = temp_data_dir / "recommendation_status"
        status_dir.mkdir(parents=True, exist_ok=True)

        status_data = {
            "org": "test-org",
            "repo": "test-repo",
            "issue_number": 123,
            "processor_name": "product-labeling",
            "original_confidence": 0.9,
            "ai_reasoning": "Test reasoning",
            "root_cause_analysis": None,
            "root_cause_confidence": None,
            "recommended_labels": ["product::vendor"],
            "labels_to_remove": [],
            "current_labels": ["bug"],
            "status": "rejected",  # Rejected
            "status_updated_at": datetime.now().isoformat(),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_confidence": None,
            "review_notes": None,
            "modified_labels": None,
            "ai_result_file": "test-org_test-repo_issue_123_product-labeling.json",
            "issue_file": "test-org_test-repo_issue_123.json",
        }

        (status_dir / "test-org_test-repo_issue_123_status.json").write_text(
            json.dumps(status_data)
        )

        # Should skip rejected recommendation
        plan = detector_with_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is None

    def test_load_and_detect_no_status_file(
        self, detector_with_status: ChangeDetector, sample_files: tuple[Path, Path]
    ) -> None:
        """Test that recommendations without status files are skipped."""
        issue_file, result_file = sample_files

        # No status file exists
        plan = detector_with_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is None

    def test_load_and_detect_ignore_status_flag(
        self,
        detector_ignore_status: ChangeDetector,
        sample_files: tuple[Path, Path],
        temp_data_dir: Path,
    ) -> None:
        """Test that ignore_status flag bypasses status checking."""
        issue_file, result_file = sample_files

        # Create pending status (would normally be skipped)
        status_dir = temp_data_dir / "recommendation_status"
        status_dir.mkdir(parents=True, exist_ok=True)

        status_data = {
            "org": "test-org",
            "repo": "test-repo",
            "issue_number": 123,
            "processor_name": "product-labeling",
            "original_confidence": 0.9,
            "ai_reasoning": "Test reasoning",
            "root_cause_analysis": None,
            "root_cause_confidence": None,
            "recommended_labels": ["product::vendor"],
            "labels_to_remove": [],
            "current_labels": ["bug"],
            "status": "pending",  # Would normally be skipped
            "status_updated_at": datetime.now().isoformat(),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_confidence": None,
            "review_notes": None,
            "modified_labels": None,
            "ai_result_file": "test-org_test-repo_issue_123_product-labeling.json",
            "issue_file": "test-org_test-repo_issue_123.json",
        }

        (status_dir / "test-org_test-repo_issue_123_status.json").write_text(
            json.dumps(status_data)
        )

        # Should process even with pending status when ignore_status=True
        plan = detector_ignore_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is not None
        assert plan.org == "test-org"
        assert plan.repo == "test-repo"
        assert plan.issue_number == 123

    def test_load_and_detect_ignore_status_no_status_file(
        self, detector_ignore_status: ChangeDetector, sample_files: tuple[Path, Path]
    ) -> None:
        """Test that ignore_status flag works even without status files."""
        issue_file, result_file = sample_files

        # No status file exists but ignore_status=True
        plan = detector_ignore_status.load_and_detect_for_file(issue_file, result_file)
        assert plan is not None
        assert plan.org == "test-org"
        assert plan.repo == "test-repo"
        assert plan.issue_number == 123

    def test_detector_initialization_with_status_tracking(
        self, temp_data_dir: Path
    ) -> None:
        """Test detector initialization with status tracking."""
        detector = ChangeDetector(
            min_confidence=0.8, ignore_status=False, data_dir=temp_data_dir
        )

        assert detector.min_confidence == 0.8
        assert detector.ignore_status is False
        assert detector.status_tracker is not None
        assert (
            detector.status_tracker.status_dir
            == temp_data_dir / "recommendation_status"
        )

    def test_detector_initialization_without_status_tracking(self) -> None:
        """Test detector initialization without status tracking."""
        detector = ChangeDetector(min_confidence=0.8, ignore_status=True, data_dir=None)

        assert detector.min_confidence == 0.8
        assert detector.ignore_status is True
        assert detector.status_tracker is None
