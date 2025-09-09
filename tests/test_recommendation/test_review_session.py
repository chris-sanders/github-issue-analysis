"""Test interactive review session functionality."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from gh_analysis.recommendation.manager import RecommendationManager
from gh_analysis.recommendation.models import (
    RecommendationFilter,
    RecommendationMetadata,
    RecommendationStatus,
)
from gh_analysis.recommendation.review_session import ReviewSession


class TestReviewSession:
    """Test ReviewSession functionality."""

    def create_test_recommendations(
        self, manager: RecommendationManager
    ) -> list[RecommendationMetadata]:
        """Create test recommendations for review testing."""
        test_data = [
            ("org1", "repo1", 1, ["product::kots"], 0.95),
            ("org1", "repo2", 2, ["product::vendor"], 0.85),
            ("org2", "repo1", 3, ["product::troubleshoot"], 0.75),
            ("org2", "repo2", 4, ["product::kots", "product::vendor"], 0.65),
        ]

        recommendations = []
        for org, repo, issue_num, labels, confidence in test_data:
            rec = RecommendationMetadata(
                org=org,
                repo=repo,
                issue_number=issue_num,
                original_confidence=confidence,
                ai_reasoning=f"AI reasoning for {org}/{repo}#{issue_num}",
                recommended_labels=labels,
                labels_to_remove=["old::label"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file=f"{org}_{repo}_{issue_num}_result.json",
                issue_file=f"{org}_{repo}_{issue_num}_issue.json",
            )
            manager.status_tracker.save_recommendation(rec)
            recommendations.append(rec)

        return recommendations

    @patch("gh_analysis.recommendation.review_session.console")
    def test_session_overview_display(self, mock_console):
        """Test session overview shows correct statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Create recommendations with different products and confidence
            recommendations = self.create_test_recommendations(manager)

            # Mock console output
            review_session._display_session_overview(recommendations)

            # Verify the display method was called
            # The overview should show:
            # - Total: 4 recommendations
            # - By Product: kots: 2, vendor: 2, troubleshoot: 1
            # - By Confidence: high: 1, medium: 1, low: 2
            assert mock_console.print.called
            # Check that a Panel was printed (Rich wraps the content)
            from rich.panel import Panel

            assert any(
                isinstance(call[0][0], Panel)
                for call in mock_console.print.call_args_list
            )

    @patch("gh_analysis.recommendation.review_session.Prompt.ask")
    @patch("gh_analysis.recommendation.review_session.console")
    def test_review_single_recommendation_approve(self, mock_console, mock_prompt):
        """Test approving a single recommendation updates status correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Create RecommendationMetadata with PENDING status
            rec = RecommendationMetadata(
                org="test",
                repo="repo",
                issue_number=1,
                original_confidence=0.85,
                ai_reasoning="Test reasoning",
                recommended_labels=["product::kots"],
                labels_to_remove=["old::label"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test_result.json",
                issue_file="test_issue.json",
            )
            manager.status_tracker.save_recommendation(rec)

            # Mock user input to select "approve" and add notes
            mock_prompt.side_effect = ["1", "Looks good to me"]  # 1 = Approve

            # Call _review_single_recommendation()
            action = review_session._review_single_recommendation(rec)

            # Verify status changed to APPROVED
            updated_rec = manager.status_tracker.get_recommendation("test", "repo", 1)
            assert updated_rec is not None
            assert updated_rec.status == RecommendationStatus.APPROVED

            # Verify reviewed_at timestamp set
            assert updated_rec.reviewed_at is not None

            # Verify notes saved
            assert updated_rec.review_notes == "Looks good to me"

            # Verify action returned
            assert action == "approved"

    @patch("gh_analysis.recommendation.review_session.Prompt.ask")
    @patch("gh_analysis.recommendation.review_session.Confirm.ask")
    @patch("gh_analysis.recommendation.review_session.console")
    def test_session_stats_tracking(self, mock_console, mock_confirm, mock_prompt):
        """Test session tracks statistics correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Create 5 recommendations
            for i in range(5):
                rec = RecommendationMetadata(
                    org="test",
                    repo="repo",
                    issue_number=i + 1,
                    original_confidence=0.8,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=["product::kots"],
                    labels_to_remove=[],
                    status=RecommendationStatus.PENDING,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test_{i}.json",
                    issue_file=f"test_{i}.json",
                )
                manager.status_tracker.save_recommendation(rec)

            # Mock user confirming session start
            mock_confirm.return_value = True

            # Mock approving 2, rejecting 1, skipping 2
            mock_prompt.side_effect = [
                "1",
                "Approved 1",  # Approve first
                "2",
                "Rejected",  # Reject second
                "4",  # Skip third
                "4",  # Skip fourth
                "5",  # Quit on fifth
            ]

            # Start session
            filter_criteria = RecommendationFilter()
            results = review_session.start_session(filter_criteria)

            # Verify session_stats reflects correct counts
            assert results["approved"] == 1
            assert results["rejected"] == 1
            assert results["skipped"] == 2
            assert results["reviewed"] == 2  # approved + rejected
            assert results["needs_modification"] == 0

    @patch("gh_analysis.recommendation.review_session.console")
    def test_empty_recommendations_handling(self, mock_console):
        """Test handling when no recommendations match criteria."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Start session with filter that matches nothing
            filter_criteria = RecommendationFilter(org="nonexistent")
            results = review_session.start_session(filter_criteria)

            # Verify appropriate message shown
            mock_console.print.assert_called_with(
                "[yellow]No recommendations found matching criteria[/yellow]"
            )

            # Verify stats are all zero
            assert all(v == 0 for v in results.values())

    @patch("gh_analysis.recommendation.review_session.Prompt.ask")
    def test_review_actions(self, mock_prompt):
        """Test different review actions (approve, reject, modify, skip, quit)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Create test recommendation
            rec = RecommendationMetadata(
                org="test",
                repo="repo",
                issue_number=1,
                original_confidence=0.85,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            manager.status_tracker.save_recommendation(rec)

            # Test reject action
            mock_prompt.side_effect = ["2", "Not relevant"]
            action = review_session._review_single_recommendation(rec)
            assert action == "rejected"
            updated = manager.status_tracker.get_recommendation("test", "repo", 1)
            assert updated is not None
            assert updated.status == RecommendationStatus.REJECTED

            # Reset status
            rec.status = RecommendationStatus.PENDING
            manager.status_tracker.save_recommendation(rec)

            # Test needs modification
            mock_prompt.side_effect = ["3", "Needs work"]
            action = review_session._review_single_recommendation(rec)
            assert action == "needs_modification"
            updated = manager.status_tracker.get_recommendation("test", "repo", 1)
            assert updated is not None
            assert updated.status == RecommendationStatus.NEEDS_MODIFICATION

            # Test skip
            mock_prompt.side_effect = ["4"]
            action = review_session._review_single_recommendation(rec)
            assert action == "skip"
            # Status should remain unchanged
            updated = manager.status_tracker.get_recommendation("test", "repo", 1)
            assert updated is not None
            assert updated.status == RecommendationStatus.NEEDS_MODIFICATION

            # Test quit
            mock_prompt.side_effect = ["5"]
            action = review_session._review_single_recommendation(rec)
            assert action == "quit"

    @patch("gh_analysis.recommendation.review_session.console")
    def test_recommendation_details_display(self, mock_console):
        """Test display of recommendation details."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            rec = RecommendationMetadata(
                org="test-org",
                repo="test-repo",
                issue_number=123,
                original_confidence=0.92,
                ai_reasoning="This is clearly a KOTS issue based on the error logs",
                recommended_labels=["product::kots", "type::bug"],
                labels_to_remove=["product::vendor"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )

            review_session._display_recommendation_details(rec)

            # Verify the display method was called
            assert mock_console.print.called
            # Check that a Panel was printed for the details
            from rich.panel import Panel

            assert any(
                isinstance(call[0][0], Panel)
                for call in mock_console.print.call_args_list
            )

    @patch("gh_analysis.recommendation.review_session.console")
    def test_session_summary_display(self, mock_console):
        """Test final session summary display."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Set session stats
            review_session.session_stats = {
                "reviewed": 10,
                "approved": 6,
                "rejected": 2,
                "needs_modification": 2,
                "skipped": 3,
            }

            review_session._display_session_summary()

            # Verify summary table shows correct counts
            assert mock_console.print.called
            # Table should show all the stats

    @patch("gh_analysis.recommendation.review_session.Prompt.ask")
    @patch("gh_analysis.recommendation.review_session.Confirm.ask")
    def test_filtered_review_session(self, mock_confirm, mock_prompt):
        """Test review session with filters applied."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))
            review_session = ReviewSession(manager)

            # Create recommendations
            self.create_test_recommendations(manager)

            # Start session with high confidence filter
            mock_confirm.return_value = True
            mock_prompt.side_effect = ["1", "Approved", "5"]  # Approve one, then quit

            filter_criteria = RecommendationFilter(min_confidence=0.9)
            results = review_session.start_session(filter_criteria)

            # Should only review the one high-confidence recommendation
            assert results["reviewed"] == 1
            assert results["approved"] == 1
