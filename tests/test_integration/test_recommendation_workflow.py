"""Integration tests for the complete recommendation workflow."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from github_issue_analysis.ai.models import (
    LabelAssessment,
    ProductLabel,
    ProductLabelingResponse,
    RecommendedLabel,
)
from github_issue_analysis.cli.main import app
from github_issue_analysis.recommendation.manager import RecommendationManager
from github_issue_analysis.recommendation.models import (
    RecommendationMetadata,
    RecommendationStatus,
)

runner = CliRunner()


class TestRecommendationWorkflow:
    """Test complete workflow from discovery through review."""

    def create_realistic_ai_result(
        self, data_dir: Path, org: str, repo: str, issue_number: int, confidence: float
    ) -> None:
        """Create realistic AI result files with actual ProductLabelingResponse."""
        results_dir = data_dir / "results"
        issues_dir = data_dir / "issues"
        results_dir.mkdir(parents=True, exist_ok=True)
        issues_dir.mkdir(parents=True, exist_ok=True)

        # Create realistic AI response
        ai_response = ProductLabelingResponse(
            root_cause_analysis="The issue describes a problem with KOTS admin console "
            "not loading properly after upgrade. The error messages indicate "
            "a database migration failure.",
            root_cause_confidence=0.85,
            recommendation_confidence=confidence,
            recommended_labels=[
                RecommendedLabel(
                    label=ProductLabel.KOTS,
                    reasoning="Admin console and database migration are KOTS",
                ),
                RecommendedLabel(
                    label=ProductLabel.TROUBLESHOOT,
                    reasoning="Support bundle analysis needed for debugging",
                ),
            ],
            current_labels_assessment=[
                LabelAssessment(
                    label="product::vendor",
                    correct=False,
                    reasoning="This is not a vendor portal issue",
                ),
                LabelAssessment(
                    label="type::bug",
                    correct=True,
                    reasoning="Correctly identified as a bug",
                ),
                LabelAssessment(
                    label="priority::high",
                    correct=True,
                    reasoning="Database migration failures are high priority",
                ),
            ],
            summary="KOTS admin console database migration failure after upgrade",
            reasoning="The issue clearly describes KOTS admin console problems with "
            "database migration errors. The stack trace shows kotsadm-postgres "
            "connection issues. This requires KOTS expertise to resolve.",
            images_analyzed=[],
            image_impact="",
        )

        # Create result file
        result_data = {
            "issue_reference": {
                "file_path": f"data/issues/{org}_{repo}_issue_{issue_number}.json",
                "org": org,
                "repo": repo,
                "issue_number": issue_number,
            },
            "processor": {
                "name": "product-labeling",
                "version": "2.1.0",
                "model_name": "openai:gpt-4o-mini",
                "include_images": False,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            "analysis": ai_response.model_dump(),
        }

        result_file = (
            results_dir / f"{org}_{repo}_issue_{issue_number}_product-labeling.json"
        )
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

        # Create corresponding issue file
        issue_data = {
            "org": org,
            "repo": repo,
            "issue": {
                "number": issue_number,
                "title": "KOTS admin console not loading after upgrade",
                "body": "After upgrading KOTS from 1.95 to 1.96, the admin console "
                "fails to load. Error logs show database migration issues:\n\n"
                "```\nkotsadm-postgres connection refused\n"
                "Migration 20230501_add_index failed\n```",
                "labels": [
                    {"name": "product::vendor"},
                    {"name": "type::bug"},
                    {"name": "priority::high"},
                ],
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "user": {"login": "testuser"},
                "comments": [],
                "attachments": [],
            },
        }

        issue_file = issues_dir / f"{org}_{repo}_issue_{issue_number}.json"
        with open(issue_file, "w") as f:
            json.dump(issue_data, f, indent=2)

    def test_full_discovery_to_review_workflow(self):
        """Test complete workflow from discovery through review."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)

            # Create realistic AI result files
            test_cases = [
                ("example-org", "example-repo", 100, 0.95),
                ("example-org", "example-repo", 101, 0.85),
                ("test-org", "test-repo", 200, 0.75),
            ]

            for org, repo, issue_num, confidence in test_cases:
                self.create_realistic_ai_result(
                    data_dir, org, repo, issue_num, confidence
                )

            # Run discover command
            result = runner.invoke(
                app, ["recommendations", "discover", "--data-dir", temp_dir]
            )
            assert result.exit_code == 0

            # Verify recommendations created correctly
            manager = RecommendationManager(data_dir)
            all_recs = manager.status_tracker.get_all_recommendations()
            assert len(all_recs) == 3

            # Verify recommendation details
            rec1 = manager.status_tracker.get_recommendation(
                "example-org", "example-repo", 100
            )
            assert rec1 is not None
            assert rec1.original_confidence == 0.95
            assert "product::kots" in rec1.recommended_labels
            assert "product::troubleshoot" in rec1.recommended_labels
            assert rec1.labels_to_remove == ["product::vendor"]
            assert rec1.status == RecommendationStatus.PENDING

            # Run review-session and simulate approving/rejecting
            with patch(
                "github_issue_analysis.recommendation.review_session.Confirm.ask"
            ) as mock_confirm:
                with patch(
                    "github_issue_analysis.recommendation.review_session.Prompt.ask"
                ) as mock_prompt:
                    mock_confirm.return_value = True
                    # Approve first, reject second, quit on third
                    mock_prompt.side_effect = [
                        "1",
                        "Good analysis",  # Approve first
                        "2",
                        "Not relevant",  # Reject second
                        "5",  # Quit
                    ]

                    result = runner.invoke(
                        app,
                        ["recommendations", "review-session", "--data-dir", temp_dir],
                    )
                    assert result.exit_code == 0

            # Verify status changes persisted correctly
            rec1_updated = manager.status_tracker.get_recommendation(
                "example-org", "example-repo", 100
            )
            assert rec1_updated is not None
            assert rec1_updated.status == RecommendationStatus.APPROVED
            assert rec1_updated.review_notes == "Good analysis"
            assert rec1_updated.reviewed_at is not None

            rec2_updated = manager.status_tracker.get_recommendation(
                "example-org", "example-repo", 101
            )
            assert rec2_updated is not None
            assert rec2_updated.status == RecommendationStatus.REJECTED
            assert rec2_updated.review_notes == "Not relevant"

            rec3_updated = manager.status_tracker.get_recommendation(
                "test-org", "test-repo", 200
            )
            assert rec3_updated is not None
            assert rec3_updated.status == RecommendationStatus.PENDING  # Not reviewed

    @patch("github_issue_analysis.cli.process.analyze_issue")
    def test_reprocessing_integration_with_ai_processor(self, mock_analyze):
        """Test that AI processing respects recommendation status."""
        # Save original env var if it exists
        original_data_dir = os.environ.get("GITHUB_ANALYSIS_DATA_DIR")

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Set environment variable to use temp directory
                os.environ["GITHUB_ANALYSIS_DATA_DIR"] = temp_dir
                data_dir = Path(temp_dir)

                # Create recommendations with various statuses
                manager = RecommendationManager(data_dir)

                test_data = [
                    ("org", "repo", 1, RecommendationStatus.PENDING),
                    ("org", "repo", 2, RecommendationStatus.APPROVED),
                    ("org", "repo", 3, RecommendationStatus.REJECTED),
                    ("org", "repo", 4, RecommendationStatus.NEEDS_MODIFICATION),
                ]

                for org, repo, issue_num, status in test_data:
                    # Create issue file
                    self.create_realistic_ai_result(data_dir, org, repo, issue_num, 0.8)

                    # Create recommendation with specific status
                    rec = RecommendationMetadata(
                        org=org,
                        repo=repo,
                        issue_number=issue_num,
                        original_confidence=0.8,
                        ai_reasoning="Test",
                        recommended_labels=["product::kots"],
                        labels_to_remove=[],
                        status=status,
                        status_updated_at=datetime.now(),
                        ai_result_file=f"{org}_{repo}_{issue_num}_result.json",
                        issue_file=f"{org}_{repo}_{issue_num}_issue.json",
                    )
                    manager.status_tracker.save_recommendation(rec)

                # Mock AI agent analysis to track which issues are processed
                processed_issues = []

                async def mock_analyze_fn(
                    agent,
                    issue_data,
                    include_images=True,
                    model=None,
                    model_settings=None,
                ):
                    processed_issues.append(issue_data["issue"]["number"])
                    return ProductLabelingResponse(
                        root_cause_analysis="Test",
                        recommendation_confidence=0.8,
                        recommended_labels=[
                            RecommendedLabel(label=ProductLabel.KOTS, reasoning="Test")
                        ],
                        current_labels_assessment=[],
                        summary="Test",
                        reasoning="Test",
                        images_analyzed=[],
                        image_impact="",
                    )

                mock_analyze.side_effect = mock_analyze_fn

                # Run process command without --reprocess
                runner.invoke(
                    app,
                    [
                        "process",
                        "product-labeling",
                        "--org",
                        "org",
                        "--repo",
                        "repo",
                    ],
                )

                # Verify PENDING/APPROVED/REJECTED issues are skipped
                assert 1 not in processed_issues  # PENDING - skipped
                assert 2 not in processed_issues  # APPROVED - skipped
                assert 3 not in processed_issues  # REJECTED - skipped
                assert 4 in processed_issues  # NEEDS_MODIFICATION - processed

                # Reset
                processed_issues.clear()

                # Run with --reprocess flag
                runner.invoke(
                    app,
                    [
                        "process",
                        "product-labeling",
                        "--org",
                        "org",
                        "--repo",
                        "repo",
                        "--reprocess",
                    ],
                )

                # Verify --reprocess flag processes all issues
                assert sorted(processed_issues) == [1, 2, 3, 4]
            finally:
                # Restore original environment variable
                if original_data_dir is None:
                    os.environ.pop("GITHUB_ANALYSIS_DATA_DIR", None)
                else:
                    os.environ["GITHUB_ANALYSIS_DATA_DIR"] = original_data_dir

    def test_discovery_updates_existing_recommendations(self):
        """Test that discover command can update existing recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            manager = RecommendationManager(data_dir)

            # Create initial AI result
            self.create_realistic_ai_result(data_dir, "org", "repo", 123, 0.75)

            # First discovery
            result = runner.invoke(
                app, ["recommendations", "discover", "--data-dir", temp_dir]
            )
            assert result.exit_code == 0

            # Modify and approve the recommendation
            rec = manager.status_tracker.get_recommendation("org", "repo", 123)
            assert rec is not None
            rec.status = RecommendationStatus.APPROVED
            rec.reviewed_at = datetime.now()
            rec.review_notes = "Approved by user"
            manager.status_tracker.save_recommendation(rec)

            # Update AI result with higher confidence
            self.create_realistic_ai_result(data_dir, "org", "repo", 123, 0.95)

            # Run discover without force - should preserve existing
            result = runner.invoke(
                app, ["recommendations", "discover", "--data-dir", temp_dir]
            )
            assert result.exit_code == 0

            rec_after = manager.status_tracker.get_recommendation("org", "repo", 123)
            assert rec_after is not None
            assert rec_after.status == RecommendationStatus.APPROVED
            assert rec_after.original_confidence == 0.75  # Not updated

            # Run discover with force - should update
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "discover",
                    "--force-refresh",
                    "--data-dir",
                    temp_dir,
                ],
            )
            assert result.exit_code == 0

            rec_forced = manager.status_tracker.get_recommendation("org", "repo", 123)
            assert rec_forced is not None
            assert rec_forced.status == RecommendationStatus.PENDING  # Reset
            assert rec_forced.original_confidence == 0.95  # Updated

    def test_workflow_with_filters(self):
        """Test workflow with various filtering options."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)

            # Create diverse set of recommendations
            test_cases = [
                ("org1", "repo1", 1, 0.95, ["product::kots"]),
                ("org1", "repo2", 2, 0.75, ["product::vendor"]),
                ("org2", "repo1", 3, 0.65, ["product::troubleshoot"]),
                ("org2", "repo2", 4, 0.85, ["product::kots", "product::vendor"]),
            ]

            for org, repo, issue_num, confidence, _ in test_cases:
                self.create_realistic_ai_result(
                    data_dir, org, repo, issue_num, confidence
                )

            # Discover all
            result = runner.invoke(
                app, ["recommendations", "discover", "--data-dir", temp_dir]
            )
            assert result.exit_code == 0

            # List with org filter
            result = runner.invoke(
                app,
                ["recommendations", "list", "--org", "org1", "--data-dir", temp_dir],
            )
            assert "repo1" in result.output
            assert "repo2" in result.output
            assert "org2" not in result.output

            # List with confidence filter
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--min-confidence",
                    "0.8",
                    "--data-dir",
                    temp_dir,
                ],
            )
            # Check by confidence values (URLs may be truncated)
            assert "0.95" in result.output  # Issue 1
            assert "0.85" in result.output  # Issue 4
            assert "0.75" not in result.output  # Issue 2 (filtered out)
            assert "0.65" not in result.output  # Issue 3 (filtered out)

            # Summary shows correct statistics
            result = runner.invoke(
                app, ["recommendations", "summary", "--data-dir", temp_dir]
            )
            assert "Total Recommendations" in result.output
            assert "4" in result.output
            assert "By Product" in result.output
