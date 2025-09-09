"""Test recommendation manager functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from gh_analysis.ai.models import (
    LabelAssessment,
    ProductLabel,
    ProductLabelingResponse,
    RecommendedLabel,
)
from gh_analysis.recommendation.manager import RecommendationManager
from gh_analysis.recommendation.models import RecommendationStatus


class TestRecommendationManager:
    """Test RecommendationManager functionality."""

    def create_mock_ai_result(
        self, org: str, repo: str, issue_number: int, confidence: float = 0.85
    ) -> dict[str, Any]:
        """Create a mock AI result file for testing."""
        ai_response = ProductLabelingResponse(
            root_cause_analysis="Test root cause analysis",
            root_cause_confidence=0.9,
            recommendation_confidence=confidence,
            recommended_labels=[
                RecommendedLabel(
                    label=ProductLabel.KOTS,
                    reasoning="This is clearly a KOTS issue",
                ),
                RecommendedLabel(
                    label=ProductLabel.TROUBLESHOOT,
                    reasoning="Also involves troubleshoot",
                ),
            ],
            current_labels_assessment=[
                LabelAssessment(
                    label="product::vendor",
                    correct=False,
                    reasoning="This is not a vendor issue",
                ),
                LabelAssessment(
                    label="type::bug",
                    correct=True,
                    reasoning="Correctly labeled as bug",
                ),
            ],
            summary="Test summary",
            reasoning="Detailed reasoning for the recommendation",
            images_analyzed=[],
            image_impact="",
        )

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

        return result_data

    def create_mock_issue(
        self, org: str, repo: str, issue_number: int
    ) -> dict[str, Any]:
        """Create a mock issue for testing."""
        return {
            "org": org,
            "repo": repo,
            "issue": {
                "number": issue_number,
                "title": f"Test issue {issue_number}",
                "body": "Test issue body",
                "labels": ["product::vendor", "type::bug"],
            },
        }

    def test_discover_recommendations(self):
        """Test discovery of AI results and metadata creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            results_dir = data_dir / "results"
            issues_dir = data_dir / "issues"
            results_dir.mkdir(parents=True)
            issues_dir.mkdir(parents=True)

            manager = RecommendationManager(data_dir)

            # Create mock AI result files
            test_cases = [
                ("org1", "repo1", 123, 0.95),
                ("org1", "repo2", 456, 0.75),
                ("org2", "repo1", 789, 0.65),
            ]

            for org, repo, issue_num, confidence in test_cases:
                # Create AI result file
                result_file = results_dir / (
                    f"{org}_{repo}_issue_{issue_num}_product-labeling.json"
                )
                result_data = self.create_mock_ai_result(
                    org, repo, issue_num, confidence
                )
                with open(result_file, "w") as f:
                    json.dump(result_data, f)

                # Create corresponding issue file
                issue_file = issues_dir / f"{org}_{repo}_issue_{issue_num}.json"
                issue_data = self.create_mock_issue(org, repo, issue_num)
                with open(issue_file, "w") as f:
                    json.dump(issue_data, f)

            # Call discover_recommendations()
            recommendations = manager.discover_recommendations()

            # Verify correct number of RecommendationMetadata created
            assert len(recommendations) == 3

            # Verify metadata fields populated correctly from AI results
            for rec in recommendations:
                assert rec.processor_name == "product-labeling"
                # Status should be PENDING since labels differ from current
                assert rec.status == RecommendationStatus.PENDING
                assert len(rec.recommended_labels) == 2
                assert "product::kots" in rec.recommended_labels
                assert "product::troubleshoot" in rec.recommended_labels
                assert rec.labels_to_remove == ["product::vendor"]
                assert rec.ai_reasoning == "Detailed reasoning for the recommendation"

            # Verify recommendations are saved
            all_saved = manager.status_tracker.get_all_recommendations()
            assert len(all_saved) == 3

    def test_should_reprocess_issue_logic(self):
        """Test reprocessing decision logic for different statuses."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))

            # Test no existing recommendation → True
            assert manager.should_reprocess_issue("org", "repo", 1) is True

            # Create recommendations with different statuses
            from gh_analysis.recommendation.models import (
                RecommendationMetadata,
            )

            # PENDING status → False (skip)
            pending_rec = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=2,
                original_confidence=0.8,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            manager.status_tracker.save_recommendation(pending_rec)
            assert manager.should_reprocess_issue("org", "repo", 2) is False

            # APPROVED status → False (skip)
            approved_rec = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=3,
                original_confidence=0.8,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.APPROVED,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            manager.status_tracker.save_recommendation(approved_rec)
            assert manager.should_reprocess_issue("org", "repo", 3) is False

            # REJECTED status → False (skip)
            rejected_rec = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=4,
                original_confidence=0.8,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.REJECTED,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            manager.status_tracker.save_recommendation(rejected_rec)
            assert manager.should_reprocess_issue("org", "repo", 4) is False

            # NEEDS_MODIFICATION status → True (reprocess)
            needs_mod_rec = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=5,
                original_confidence=0.8,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                status=RecommendationStatus.NEEDS_MODIFICATION,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            manager.status_tracker.save_recommendation(needs_mod_rec)
            assert manager.should_reprocess_issue("org", "repo", 5) is True

            # Test force_reprocess=True → True (always)
            assert (
                manager.should_reprocess_issue("org", "repo", 2, force_reprocess=True)
                is True
            )
            assert (
                manager.should_reprocess_issue("org", "repo", 3, force_reprocess=True)
                is True
            )

    def test_recommendation_summary_statistics(self):
        """Test summary statistics generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))

            # Create recommendations with various statuses, products, confidence
            from gh_analysis.recommendation.models import (
                RecommendationMetadata,
            )

            test_data = [
                (
                    RecommendationStatus.PENDING,
                    ["product::kots"],
                    0.95,
                ),  # high confidence pending
                (
                    RecommendationStatus.PENDING,
                    ["product::vendor"],
                    0.75,
                ),  # medium confidence
                (RecommendationStatus.APPROVED, ["product::kots"], 0.85),
                (RecommendationStatus.REJECTED, ["product::troubleshoot"], 0.65),
                (
                    RecommendationStatus.PENDING,
                    ["product::kots", "product::vendor"],
                    0.92,
                ),  # multi-product, high conf
            ]

            for i, (status, labels, confidence) in enumerate(test_data):
                rec = RecommendationMetadata(
                    org="test",
                    repo=f"repo{i}",
                    issue_number=i + 1,
                    original_confidence=confidence,
                    ai_reasoning="Test",
                    recommended_labels=labels,
                    labels_to_remove=[],
                    status=status,
                    status_updated_at=datetime.now(),
                    ai_result_file=f"test{i}.json",
                    issue_file=f"test{i}.json",
                )
                manager.status_tracker.save_recommendation(rec)

            # Call get_recommendation_summary()
            summary = manager.get_recommendation_summary()

            # Verify counts by status are correct
            assert summary["total_recommendations"] == 5
            assert summary["by_status"]["pending"] == 3
            assert summary["by_status"]["approved"] == 1
            assert summary["by_status"]["rejected"] == 1

            # Verify counts by product are correct
            assert summary["by_product"]["product::kots"] == 3
            assert summary["by_product"]["product::vendor"] == 1
            assert summary["by_product"]["product::troubleshoot"] == 1

            # Verify confidence tier distribution is correct
            assert summary["by_confidence_tier"]["high"] == 2  # 0.95, 0.92
            assert summary["by_confidence_tier"]["medium"] == 2  # 0.75, 0.85
            assert summary["by_confidence_tier"]["low"] == 1  # 0.65

            # Verify special counts
            assert summary["pending_high_confidence"] == 2  # pending with >= 0.9

    def test_force_refresh_discovery(self):
        """Test force_refresh parameter in discover_recommendations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            results_dir = data_dir / "results"
            issues_dir = data_dir / "issues"
            results_dir.mkdir(parents=True)
            issues_dir.mkdir(parents=True)

            manager = RecommendationManager(data_dir)

            # Create a mock AI result and issue
            result_file = results_dir / "org_repo_issue_123_product-labeling.json"
            result_data = self.create_mock_ai_result("org", "repo", 123)
            with open(result_file, "w") as f:
                json.dump(result_data, f)

            issue_file = issues_dir / "org_repo_issue_123.json"
            issue_data = self.create_mock_issue("org", "repo", 123)
            with open(issue_file, "w") as f:
                json.dump(issue_data, f)

            # First discovery
            recs1 = manager.discover_recommendations()
            assert len(recs1) == 1
            assert recs1[0].status == RecommendationStatus.PENDING

            # Modify the recommendation
            rec = manager.status_tracker.get_recommendation("org", "repo", 123)
            assert rec is not None
            rec.status = RecommendationStatus.APPROVED
            rec.reviewed_at = datetime.now()
            manager.status_tracker.save_recommendation(rec)

            # Second discovery without force_refresh - should return existing
            recs2 = manager.discover_recommendations(force_refresh=False)
            assert len(recs2) == 1
            assert recs2[0].status == RecommendationStatus.APPROVED

            # Third discovery with force_refresh - should recreate
            recs3 = manager.discover_recommendations(force_refresh=True)
            assert len(recs3) == 1
            # Status should be reset to PENDING since it's recreated from AI result
            assert recs3[0].status == RecommendationStatus.PENDING

    def test_missing_issue_file_handling(self):
        """Test handling of AI results without corresponding issue files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            results_dir = data_dir / "results"
            issues_dir = data_dir / "issues"
            results_dir.mkdir(parents=True)
            issues_dir.mkdir(parents=True)

            manager = RecommendationManager(data_dir)

            # Create AI result without corresponding issue file
            result_file = results_dir / "org_repo_issue_123_product-labeling.json"
            result_data = self.create_mock_ai_result("org", "repo", 123)
            with open(result_file, "w") as f:
                json.dump(result_data, f)

            # Discover should skip this result
            recommendations = manager.discover_recommendations()
            assert len(recommendations) == 0

    def test_invalid_filename_handling(self):
        """Test handling of files with invalid naming patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            results_dir = data_dir / "results"
            issues_dir = data_dir / "issues"
            results_dir.mkdir(parents=True)
            issues_dir.mkdir(parents=True)

            manager = RecommendationManager(data_dir)

            # Create files with invalid names
            invalid_files = [
                "invalid_format.json",
                "org_repo_product-labeling.json",  # missing issue number
                "org_issue_123_product-labeling.json",  # missing repo
            ]

            for filename in invalid_files:
                file_path = results_dir / filename
                with open(file_path, "w") as f:
                    json.dump({"test": "data"}, f)

            # Should not crash and should find 0 recommendations
            recommendations = manager.discover_recommendations()
            assert len(recommendations) == 0

    def test_is_recommendation_change(self):
        """Test is_recommendation_change method identifies changes correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = RecommendationManager(Path(temp_dir))

            from gh_analysis.recommendation.models import (
                RecommendationMetadata,
            )

            # Test 1: Same product labels - no change
            rec1 = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=1,
                original_confidence=0.9,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                current_labels=["product::kots", "type::bug", "priority::high"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            assert manager.is_recommendation_change(rec1) is False

            # Test 2: Different product labels - change needed
            rec2 = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=2,
                original_confidence=0.9,
                ai_reasoning="Test",
                recommended_labels=["product::vendor"],
                labels_to_remove=[],
                current_labels=["product::kots", "type::bug"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            assert manager.is_recommendation_change(rec2) is True

            # Test 3: No current product labels - change needed
            rec3 = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=3,
                original_confidence=0.9,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=[],
                current_labels=["type::bug", "priority::high"],  # No product labels
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            assert manager.is_recommendation_change(rec3) is True

            # Test 4: Multiple product labels, same set - no change
            rec4 = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=4,
                original_confidence=0.9,
                ai_reasoning="Test",
                recommended_labels=["product::kots", "product::troubleshoot"],
                labels_to_remove=[],
                current_labels=[
                    "product::troubleshoot",
                    "product::kots",
                    "type::bug",
                ],  # Order different
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            assert manager.is_recommendation_change(rec4) is False

            # Test 5: Labels to remove indicates change
            rec5 = RecommendationMetadata(
                org="org",
                repo="repo",
                issue_number=5,
                original_confidence=0.9,
                ai_reasoning="Test",
                recommended_labels=["product::kots"],
                labels_to_remove=["product::vendor"],  # Has labels to remove
                current_labels=["product::kots", "product::vendor"],
                status=RecommendationStatus.PENDING,
                status_updated_at=datetime.now(),
                ai_result_file="test.json",
                issue_file="test.json",
            )
            assert manager.is_recommendation_change(rec5) is True

    def test_discover_sets_no_change_needed_status(self):
        """Test that discovery sets NO_CHANGE_NEEDED status when labels match."""
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            results_dir = data_dir / "results"
            issues_dir = data_dir / "issues"
            results_dir.mkdir(parents=True)
            issues_dir.mkdir(parents=True)

            manager = RecommendationManager(data_dir)

            # Create AI result that matches current labels exactly
            ai_response = ProductLabelingResponse(
                root_cause_analysis="Test root cause analysis",
                root_cause_confidence=0.9,
                recommendation_confidence=0.85,
                recommended_labels=[
                    RecommendedLabel(
                        label=ProductLabel.KOTS,
                        reasoning="This is clearly a KOTS issue",
                    ),
                    RecommendedLabel(
                        label=ProductLabel.TROUBLESHOOT,
                        reasoning="Also involves troubleshoot",
                    ),
                ],
                current_labels_assessment=[
                    LabelAssessment(
                        label="product::kots",
                        correct=True,
                        reasoning="Correctly labeled as KOTS",
                    ),
                    LabelAssessment(
                        label="product::troubleshoot",
                        correct=True,
                        reasoning="Correctly labeled as troubleshoot",
                    ),
                    LabelAssessment(
                        label="type::bug",
                        correct=True,
                        reasoning="Correctly labeled as bug",
                    ),
                ],
                summary="Test summary",
                reasoning="All labels are correct",
                images_analyzed=[],
                image_impact="",
            )

            result_data = {
                "issue_reference": {
                    "file_path": "data/issues/org_repo_issue_123.json",
                    "org": "org",
                    "repo": "repo",
                    "issue_number": 123,
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

            result_file = results_dir / "org_repo_issue_123_product-labeling.json"
            with open(result_file, "w") as f:
                json.dump(result_data, f)

            # Create issue that already has product::kots label
            issue_data = {
                "org": "org",
                "repo": "repo",
                "issue": {
                    "number": 123,
                    "title": "Test issue",
                    "body": "Test body",
                    "labels": [
                        {"name": "product::kots"},  # Already has recommended label
                        {"name": "product::troubleshoot"},  # And the other one
                        {"name": "type::bug"},
                    ],
                },
            }
            issue_file = issues_dir / "org_repo_issue_123.json"
            with open(issue_file, "w") as f:
                json.dump(issue_data, f)

            # Discover should set NO_CHANGE_NEEDED status
            recommendations = manager.discover_recommendations()
            assert len(recommendations) == 1

            rec = recommendations[0]
            assert rec.status == RecommendationStatus.NO_CHANGE_NEEDED
            assert rec.current_labels == [
                "product::kots",
                "product::troubleshoot",
                "type::bug",
            ]
            assert rec.recommended_labels == ["product::kots", "product::troubleshoot"]
