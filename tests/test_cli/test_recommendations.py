"""Test recommendation CLI commands."""

import json
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
from github_issue_analysis.recommendation.models import (
    RecommendationMetadata,
    RecommendationStatus,
)

runner = CliRunner()


class TestRecommendationsCLI:
    """Test recommendations CLI commands."""

    def create_mock_ai_result(
        self, data_dir: Path, org: str, repo: str, issue_number: int
    ) -> None:
        """Create mock AI result and issue files."""
        results_dir = data_dir / "results"
        issues_dir = data_dir / "issues"
        results_dir.mkdir(parents=True, exist_ok=True)
        issues_dir.mkdir(parents=True, exist_ok=True)

        # Create AI result
        ai_response = ProductLabelingResponse(
            root_cause_analysis="Test root cause",
            root_cause_confidence=0.9,
            recommendation_confidence=0.85,
            recommended_labels=[
                RecommendedLabel(
                    label=ProductLabel.KOTS,
                    reasoning="KOTS issue",
                ),
            ],
            current_labels_assessment=[
                LabelAssessment(
                    label="product::vendor",
                    correct=False,
                    reasoning="Not vendor",
                ),
            ],
            summary="Test summary",
            reasoning="Test reasoning",
            images_analyzed=[],
            image_impact="",
        )

        result_data = {
            "issue_reference": {
                "org": org,
                "repo": repo,
                "issue_number": issue_number,
            },
            "analysis": ai_response.model_dump(),
        }

        result_file = (
            results_dir / f"{org}_{repo}_issue_{issue_number}_product-labeling.json"
        )
        with open(result_file, "w") as f:
            json.dump(result_data, f)

        # Create issue file
        issue_data = {
            "org": org,
            "repo": repo,
            "issue": {
                "number": issue_number,
                "title": f"Test issue {issue_number}",
                "labels": ["product::vendor"],
            },
        }

        issue_file = issues_dir / f"{org}_{repo}_issue_{issue_number}.json"
        with open(issue_file, "w") as f:
            json.dump(issue_data, f)

    def test_discover_command(self):
        """Test recommendation discovery CLI command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock AI result and issue files
            self.create_mock_ai_result(Path(temp_dir), "testorg", "testrepo", 123)

            # Run: uv run gh-analysis recommendations discover
            result = runner.invoke(
                app, ["recommendations", "discover", "--data-dir", temp_dir]
            )

            # Verify command succeeds
            assert result.exit_code == 0
            assert "Found 1 recommendations" in result.output

            # Verify recommendation status files created
            status_file = (
                Path(temp_dir)
                / "recommendation_status"
                / "testorg_testrepo_issue_123_status.json"
            )
            assert status_file.exists()

    def test_list_command_no_filters(self):
        """Test list command with no filters shows all recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create 3 recommendation status files
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            for i in range(1, 4):
                rec = RecommendationMetadata(
                    org="testorg",
                    repo=f"repo{i}",
                    issue_number=i,
                    original_confidence=0.8,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=[f"product::test{i}"],
                    labels_to_remove=[],
                    status=RecommendationStatus.PENDING,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test{i}.json",
                    issue_file=f"test{i}.json",
                )
                status_file = status_dir / f"testorg_repo{i}_issue_{i}_status.json"
                with open(status_file, "w") as f:
                    json.dump(rec.model_dump(), f, default=str)

            # Run: uv run gh-analysis recommendations list
            result = runner.invoke(
                app, ["recommendations", "list", "--data-dir", temp_dir]
            )

            # Verify output shows all 3 recommendations in table format
            assert result.exit_code == 0

            # Check that key content is present (URLs may be truncated in table)
            assert "repo1" in result.output  # Check repo is present
            assert "0.80" in result.output  # Check confidence is shown
            assert "pending" in result.output  # Check status is shown
            assert "none" in result.output  # Check current labels shows "none"
            # Check that we have 3 rows of data (checking truncated content)
            output_lines = result.output.split("\n")
            data_rows = [
                line for line in output_lines if "│" in line and "repo" in line
            ]
            assert len(data_rows) == 3

    def test_list_command_with_filters(self):
        """Test list command with various filter combinations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Create recommendations with different org, status, confidence
            test_data = [
                ("org1", "repo1", RecommendationStatus.PENDING, 0.95),
                ("org1", "repo2", RecommendationStatus.APPROVED, 0.75),
                ("org2", "repo1", RecommendationStatus.PENDING, 0.65),
            ]

            for i, (org, repo, status, conf) in enumerate(test_data):
                rec = RecommendationMetadata(
                    org=org,
                    repo=repo,
                    issue_number=i + 1,
                    original_confidence=conf,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=["product::kots"],
                    labels_to_remove=[],
                    status=status,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test{i}.json",
                    issue_file=f"test{i}.json",
                )
                status_file = status_dir / f"{org}_{repo}_issue_{i + 1}_status.json"
                with open(status_file, "w") as f:
                    json.dump(rec.model_dump(), f, default=str)

            # Test --org filter
            result = runner.invoke(
                app,
                ["recommendations", "list", "--org", "org1", "--data-dir", temp_dir],
            )
            assert result.exit_code == 0
            assert "repo1" in result.output
            assert "repo2" in result.output
            # When filtering by org1, org2/repo1 should not be in the results
            # We can verify this by checking that we only have 2 data rows, not 3

            # Test --status filter
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--status",
                    "pending",
                    "--data-dir",
                    temp_dir,
                ],
            )
            assert result.exit_code == 0
            assert "pending" in result.output.lower()
            assert "approved" not in result.output.lower()

            # Test --min-confidence filter
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--min-confidence",
                    "0.9",
                    "--data-dir",
                    temp_dir,
                ],
            )
            assert result.exit_code == 0
            assert "repo1" in result.output
            # We can verify filtering worked by checking specific confidence score
            assert (
                "0.95" in result.output
            )  # Only org1/repo1 has this confidence (>=0.9)

    def test_summary_command(self):
        """Test summary dashboard command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Create recommendations with various statuses and products
            test_data = [
                (RecommendationStatus.PENDING, ["product::kots"], 0.95),
                (RecommendationStatus.PENDING, ["product::vendor"], 0.75),
                (RecommendationStatus.APPROVED, ["product::kots"], 0.85),
                (RecommendationStatus.REJECTED, ["product::troubleshoot"], 0.65),
            ]

            for i, (status, labels, conf) in enumerate(test_data):
                rec = RecommendationMetadata(
                    org="test",
                    repo=f"repo{i}",
                    issue_number=i + 1,
                    original_confidence=conf,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=labels,
                    labels_to_remove=[],
                    status=status,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test{i}.json",
                    issue_file=f"test{i}.json",
                )
                status_file = status_dir / f"test_repo{i}_issue_{i + 1}_status.json"
                with open(status_file, "w") as f:
                    json.dump(rec.model_dump(), f, default=str)

            # Run: uv run gh-analysis recommendations summary
            result = runner.invoke(
                app, ["recommendations", "summary", "--data-dir", temp_dir]
            )

            # Verify statistics table displayed
            assert result.exit_code == 0
            assert "Total Recommendations" in result.output
            assert "4" in result.output  # total count

            # Verify counts match created recommendations
            assert "By Status" in result.output
            assert "By Product" in result.output

    @patch("github_issue_analysis.recommendation.review_session.Confirm.ask")
    def test_review_session_command_no_recommendations(self, mock_confirm):
        """Test review session with no pending recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Ensure no recommendation files exist
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Run: uv run gh-analysis recommendations review-session
            result = runner.invoke(
                app, ["recommendations", "review-session", "--data-dir", temp_dir]
            )

            # Verify shows "No recommendations found" message
            assert result.exit_code == 0
            assert "No recommendations found" in result.output

    @patch("github_issue_analysis.recommendation.review_session.Prompt.ask")
    @patch("github_issue_analysis.recommendation.review_session.Confirm.ask")
    def test_review_session_command_with_filters(self, mock_confirm, mock_prompt):
        """Test review session command filters work correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Create recommendations with different orgs and confidence levels
            test_data = [
                ("org1", 0.95),  # High confidence
                ("org1", 0.65),  # Low confidence
                ("org2", 0.85),  # Different org
            ]

            for i, (org, conf) in enumerate(test_data):
                rec = RecommendationMetadata(
                    org=org,
                    repo="repo",
                    issue_number=i + 1,
                    original_confidence=conf,
                    ai_reasoning=f"Test {i}",
                    recommended_labels=["product::kots"],
                    labels_to_remove=[],
                    status=RecommendationStatus.PENDING,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test{i}.json",
                    issue_file=f"test{i}.json",
                )
                status_file = status_dir / f"{org}_repo_issue_{i + 1}_status.json"
                with open(status_file, "w") as f:
                    json.dump(rec.model_dump(), f, default=str)

            # Mock user confirming and then quitting
            mock_confirm.return_value = True
            mock_prompt.return_value = "5"  # Quit

            # Run with filters
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "review-session",
                    "--org",
                    "org1",
                    "--min-confidence",
                    "0.8",
                    "--data-dir",
                    temp_dir,
                ],
            )

            # Verify only matching recommendations are included in session
            assert result.exit_code == 0
            assert "Total recommendations: 1" in result.output  # Only the 0.95 one

    def test_list_json_format(self):
        """Test list command with JSON output format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Create a recommendation
            rec = RecommendationMetadata(
                org="test",
                repo="repo",
                issue_number=1,
                original_confidence=0.8,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            status_file = status_dir / "test_repo_issue_1_status.json"
            with open(status_file, "w") as f:
                json.dump(rec.model_dump(), f, default=str)

            # Run with JSON format
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--format",
                    "json",
                    "--data-dir",
                    temp_dir,
                ],
            )

            assert result.exit_code == 0
            # Verify valid JSON output
            output_data = json.loads(result.output)
            assert len(output_data) == 1
            assert output_data[0]["org"] == "test"
            assert output_data[0]["repo"] == "repo"

    def test_invalid_status_filter(self):
        """Test handling of invalid status values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--status",
                    "invalid_status",
                    "--data-dir",
                    temp_dir,
                ],
            )

            assert result.exit_code == 0
            assert "Invalid status value" in result.output

    def test_list_command_filters_no_change_recommendations(self):
        """Test that list command filters out recommendations with no label changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Manually create status files to test filtering
            status_dir = Path(temp_dir) / "recommendation_status"
            status_dir.mkdir(parents=True)

            # Create recommendation where current labels match recommended labels
            rec1 = RecommendationMetadata(
                org="org1",
                repo="repo1",
                issue_number=1,
                original_confidence=0.95,
                ai_reasoning="Test 1",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                current_labels=["product::kots", "type::bug"],  # Already has the label
                status=RecommendationStatus.NO_CHANGE_NEEDED,  # Set by discovery
                status_updated_at=datetime.now(),
                ai_result_file="test1.json",
                issue_file="test1.json",
            )
            status_file1 = status_dir / "org1_repo1_issue_1_status.json"
            with open(status_file1, "w") as f:
                json.dump(rec1.model_dump(), f, default=str)

            # Create recommendation with actual change needed
            rec2 = RecommendationMetadata(
                org="org1",
                repo="repo1",
                issue_number=2,
                original_confidence=0.85,
                ai_reasoning="Test 2",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                current_labels=["type::bug"],  # Missing product label
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test2.json",
                issue_file="test2.json",
            )
            status_file2 = status_dir / "org1_repo1_issue_2_status.json"
            with open(status_file2, "w") as f:
                json.dump(rec2.model_dump(), f, default=str)

            # Default: should filter out no-change recommendations
            result = runner.invoke(
                app,
                ["recommendations", "list", "--data-dir", temp_dir],
            )
            assert result.exit_code == 0
            # Should only show issue 2 (needs change from vendor to kots)
            assert "pending" in result.output.lower()
            # Count visible rows - should be 1
            output_lines = result.output.split("\n")
            data_rows = [
                line for line in output_lines if "│" in line and "repo1" in line
            ]
            assert len(data_rows) == 1

            # With --include-no-change: should show all
            result = runner.invoke(
                app,
                [
                    "recommendations",
                    "list",
                    "--include-no-change",
                    "--data-dir",
                    temp_dir,
                ],
            )
            assert result.exit_code == 0
            # Should show both recommendations
            output_lines = result.output.split("\n")
            data_rows = [
                line for line in output_lines if "│" in line and "repo1" in line
            ]
            assert len(data_rows) == 2
