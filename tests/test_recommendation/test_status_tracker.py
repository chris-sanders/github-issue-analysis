"""Test recommendation status tracking and persistence."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from gh_analysis.recommendation.models import (
    RecommendationFilter,
    RecommendationMetadata,
    RecommendationStatus,
)
from gh_analysis.recommendation.status_tracker import StatusTracker


class TestStatusTracker:
    """Test StatusTracker functionality."""

    def test_save_and_retrieve_recommendation(self):
        """Test saving recommendation and retrieving by org/repo/issue_number."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create and save RecommendationMetadata
            metadata = RecommendationMetadata(
                org="test-org",
                repo="test-repo",
                issue_number=123,
                original_confidence=0.85,
                ai_reasoning="Test reasoning",
                recommended_labels=["product::kots"],
                labels_to_remove=["product::vendor"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test_result.json",
                issue_file="test_issue.json",
            )

            tracker.save_recommendation(metadata)

            # Test file path format: {org}_{repo}_issue_{issue_number}_status.json
            expected_file = Path(temp_dir) / "test-org_test-repo_issue_123_status.json"
            assert expected_file.exists()

            # Retrieve by identifiers and verify content matches
            retrieved = tracker.get_recommendation("test-org", "test-repo", 123)
            assert retrieved is not None
            assert retrieved.org == "test-org"
            assert retrieved.repo == "test-repo"
            assert retrieved.issue_number == 123
            assert retrieved.original_confidence == 0.85
            assert retrieved.ai_reasoning == "Test reasoning"
            assert retrieved.recommended_labels == ["product::kots"]

    def test_get_all_recommendations(self):
        """Test loading all recommendations from directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Save 3 different recommendations
            for i in range(1, 4):
                metadata = RecommendationMetadata(
                    org="test-org",
                    repo=f"repo-{i}",
                    issue_number=i,
                    original_confidence=0.7 + i * 0.1,
                    ai_reasoning=f"Reasoning {i}",
                    recommended_labels=[f"product::test{i}"],
                    labels_to_remove=[],
                    status=RecommendationStatus.PENDING,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"result_{i}.json",
                    issue_file=f"issue_{i}.json",
                )
                tracker.save_recommendation(metadata)

            # Call get_all_recommendations()
            all_recs = tracker.get_all_recommendations()

            # Verify returns list of 3 RecommendationMetadata objects
            assert len(all_recs) == 3
            assert all(isinstance(rec, RecommendationMetadata) for rec in all_recs)

            # Verify each recommendation is present
            repos = {rec.repo for rec in all_recs}
            assert repos == {"repo-1", "repo-2", "repo-3"}

    def test_query_with_filters(self):
        """Test filtering recommendations by various criteria."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create recommendations with different org, repo, status, confidence
            test_data = [
                ("org1", "repo1", RecommendationStatus.PENDING, 0.95),
                ("org1", "repo2", RecommendationStatus.APPROVED, 0.85),
                ("org2", "repo1", RecommendationStatus.REJECTED, 0.75),
                ("org2", "repo2", RecommendationStatus.PENDING, 0.65),
            ]

            for i, (org, repo, status, confidence) in enumerate(test_data):
                metadata = RecommendationMetadata(
                    org=org,
                    repo=repo,
                    issue_number=i + 1,
                    original_confidence=confidence,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=["product::kots"],
                    labels_to_remove=[],
                    status=status,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"result_{i}.json",
                    issue_file=f"issue_{i}.json",
                )
                tracker.save_recommendation(metadata)

            # Test org filter returns only matching org
            org_filter = RecommendationFilter(org="org1")
            org_results = tracker.query_recommendations(org_filter)
            assert len(org_results) == 2
            assert all(rec.org == "org1" for rec in org_results)

            # Test status filter returns only matching statuses
            status_filter = RecommendationFilter(status=[RecommendationStatus.PENDING])
            status_results = tracker.query_recommendations(status_filter)
            assert len(status_results) == 2
            assert all(
                rec.status == RecommendationStatus.PENDING for rec in status_results
            )

            # Test confidence range filter
            conf_filter = RecommendationFilter(min_confidence=0.8, max_confidence=0.9)
            conf_results = tracker.query_recommendations(conf_filter)
            assert len(conf_results) == 1
            assert conf_results[0].original_confidence == 0.85

            # Test combined filters
            combined_filter = RecommendationFilter(
                org="org1", status=[RecommendationStatus.PENDING]
            )
            combined_results = tracker.query_recommendations(combined_filter)
            assert len(combined_results) == 1
            assert combined_results[0].org == "org1"
            assert combined_results[0].status == RecommendationStatus.PENDING

    def test_invalid_json_handling(self):
        """Test graceful handling of corrupted status files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create a valid recommendation
            valid_metadata = RecommendationMetadata(
                org="valid",
                repo="repo",
                issue_number=1,
                original_confidence=0.8,
                ai_reasoning="Valid",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="valid.json",
                issue_file="valid.json",
            )
            tracker.save_recommendation(valid_metadata)

            # Create invalid JSON file in status directory
            invalid_file = Path(temp_dir) / "invalid_status.json"
            with open(invalid_file, "w") as f:
                f.write("{ invalid json content")

            # Verify get_all_recommendations() doesn't crash
            all_recs = tracker.get_all_recommendations()

            # Verify error is logged but other files still load
            assert len(all_recs) == 1
            assert all_recs[0].org == "valid"

    def test_pagination(self):
        """Test pagination support in query_recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create 10 recommendations
            for i in range(10):
                metadata = RecommendationMetadata(
                    org="test",
                    repo="repo",
                    issue_number=i + 1,
                    original_confidence=0.8,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=["product::kots"],
                    labels_to_remove=[],
                    status=RecommendationStatus.PENDING,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"result_{i}.json",
                    issue_file=f"issue_{i}.json",
                )
                tracker.save_recommendation(metadata)

            # Test limit
            filter_limit = RecommendationFilter(limit=5)
            limited_results = tracker.query_recommendations(filter_limit)
            assert len(limited_results) == 5

            # Test offset
            filter_offset = RecommendationFilter(offset=7)
            offset_results = tracker.query_recommendations(filter_offset)
            assert len(offset_results) == 3

            # Test limit + offset
            filter_both = RecommendationFilter(limit=3, offset=5)
            both_results = tracker.query_recommendations(filter_both)
            assert len(both_results) == 3

    def test_text_search(self):
        """Test text search in reasoning and notes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create recommendations with different text content
            metadata1 = RecommendationMetadata(
                org="test",
                repo="repo1",
                issue_number=1,
                original_confidence=0.8,
                ai_reasoning="This is about KOTS installation issues",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="result1.json",
                issue_file="issue1.json",
            )
            tracker.save_recommendation(metadata1)

            metadata2 = RecommendationMetadata(
                org="test",
                repo="repo2",
                issue_number=2,
                original_confidence=0.8,
                ai_reasoning="This is about vendor portal problems",
                recommended_labels=["product::vendor"],
                labels_to_remove=[],
                status=RecommendationStatus.APPROVED,
                status_updated_at=datetime.now(),
                review_notes="Confirmed vendor issue",
                ai_result_file="result2.json",
                issue_file="issue2.json",
            )
            tracker.save_recommendation(metadata2)

            # Search for "KOTS" (case insensitive)
            kots_filter = RecommendationFilter(search_text="kots")
            kots_results = tracker.query_recommendations(kots_filter)
            assert len(kots_results) == 1
            assert kots_results[0].issue_number == 1

            # Search for "vendor"
            vendor_filter = RecommendationFilter(search_text="vendor")
            vendor_results = tracker.query_recommendations(vendor_filter)
            assert len(vendor_results) == 1
            assert vendor_results[0].issue_number == 2

            # Search for non-existent text
            none_filter = RecommendationFilter(search_text="nonexistent")
            none_results = tracker.query_recommendations(none_filter)
            assert len(none_results) == 0

    def test_date_filtering(self):
        """Test date-based filtering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            tracker = StatusTracker(Path(temp_dir))

            # Create recommendations with different dates
            base_date = datetime.now()

            metadata1 = RecommendationMetadata(
                org="test",
                repo="repo1",
                issue_number=1,
                original_confidence=0.8,
                ai_reasoning="Old recommendation",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=base_date - timedelta(days=10),
                ai_result_file="result1.json",
                issue_file="issue1.json",
            )
            tracker.save_recommendation(metadata1)

            metadata2 = RecommendationMetadata(
                org="test",
                repo="repo2",
                issue_number=2,
                original_confidence=0.8,
                ai_reasoning="Recent recommendation",
                recommended_labels=["product::vendor"],
                labels_to_remove=[],
                status=RecommendationStatus.APPROVED,
                status_updated_at=base_date - timedelta(days=2),
                reviewed_at=base_date - timedelta(days=1),
                ai_result_file="result2.json",
                issue_file="issue2.json",
            )
            tracker.save_recommendation(metadata2)

            # Test created_after filter
            after_filter = RecommendationFilter(
                created_after=base_date - timedelta(days=5)
            )
            after_results = tracker.query_recommendations(after_filter)
            assert len(after_results) == 1
            assert after_results[0].issue_number == 2

            # Test reviewed_after filter
            reviewed_filter = RecommendationFilter(
                reviewed_after=base_date - timedelta(days=3)
            )
            reviewed_results = tracker.query_recommendations(reviewed_filter)
            assert len(reviewed_results) == 1
            assert reviewed_results[0].issue_number == 2
