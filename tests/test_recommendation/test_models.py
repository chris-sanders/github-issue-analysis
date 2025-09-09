"""Test recommendation data models."""

from datetime import datetime

from gh_analysis.recommendation.models import (
    RecommendationFilter,
    RecommendationMetadata,
    RecommendationStatus,
    ReviewAction,
)


class TestRecommendationModels:
    """Test RecommendationMetadata and related models."""

    def test_recommendation_metadata_creation(self):
        """Test RecommendationMetadata model validation and creation."""
        # Create valid RecommendationMetadata with all required fields
        now = datetime.now()
        metadata = RecommendationMetadata(
            org="test-org",
            repo="test-repo",
            issue_number=123,
            processor_name="product-labeling",
            original_confidence=0.85,
            ai_reasoning="This issue is about KOTS installation",
            recommended_labels=["product::kots", "type::bug"],
            labels_to_remove=["product::vendor"],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="/path/to/result.json",
            issue_file="/path/to/issue.json",
        )

        assert metadata.org == "test-org"
        assert metadata.repo == "test-repo"
        assert metadata.issue_number == 123
        assert metadata.original_confidence == 0.85
        assert metadata.status == RecommendationStatus.PENDING
        assert len(metadata.recommended_labels) == 2
        assert len(metadata.labels_to_remove) == 1

        # Test optional field handling
        assert metadata.reviewed_by is None
        assert metadata.reviewed_at is None
        assert metadata.review_confidence is None
        assert metadata.review_notes is None
        assert metadata.modified_labels is None

    def test_recommendation_filter_validation(self):
        """Test RecommendationFilter model with various filter combinations."""
        # Test valid filter combinations
        filter1 = RecommendationFilter(
            org="test-org",
            status=[RecommendationStatus.PENDING, RecommendationStatus.APPROVED],
            min_confidence=0.7,
            max_confidence=0.9,
            confidence_tier=["high", "medium"],
        )

        assert filter1.org == "test-org"
        assert filter1.status is not None
        assert len(filter1.status) == 2
        assert filter1.min_confidence == 0.7
        assert filter1.max_confidence == 0.9

        # Test with date ranges
        filter2 = RecommendationFilter(
            created_after=datetime(2024, 1, 1),
            created_before=datetime(2024, 12, 31),
        )

        assert filter2.created_after is not None
        assert filter2.created_after.year == 2024
        assert filter2.created_before is not None
        assert filter2.created_before.month == 12

        # Test pagination
        filter3 = RecommendationFilter(limit=10, offset=20)
        assert filter3.limit == 10
        assert filter3.offset == 20

    def test_confidence_tier_property(self):
        """Test confidence_tier computed property returns correct tiers."""
        now = datetime.now()

        # Test confidence 0.95 → "high"
        high_conf = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=1,
            original_confidence=0.95,
            ai_reasoning="test",
            recommended_labels=[],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert high_conf.confidence_tier == "high"

        # Test confidence 0.75 → "medium"
        medium_conf = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=2,
            original_confidence=0.75,
            ai_reasoning="test",
            recommended_labels=[],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert medium_conf.confidence_tier == "medium"

        # Test confidence 0.5 → "low"
        low_conf = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=3,
            original_confidence=0.5,
            ai_reasoning="test",
            recommended_labels=[],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert low_conf.confidence_tier == "low"

        # Test with review confidence overriding original
        with_review = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=4,
            original_confidence=0.5,
            review_confidence=0.95,
            ai_reasoning="test",
            recommended_labels=[],
            labels_to_remove=[],
            status=RecommendationStatus.APPROVED,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert with_review.confidence_tier == "high"

    def test_primary_product_extraction(self):
        """Test primary_product property extracts correct product label."""
        now = datetime.now()

        # Test with ["product::kots", "other"] → "product::kots"
        with_product = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=1,
            original_confidence=0.8,
            ai_reasoning="test",
            recommended_labels=["product::kots", "type::bug", "priority::high"],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert with_product.primary_product == "product::kots"

        # Test with no product labels → None
        no_product = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=2,
            original_confidence=0.8,
            ai_reasoning="test",
            recommended_labels=["type::bug", "priority::high"],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert no_product.primary_product is None

        # Test with multiple product labels → first one
        multi_product = RecommendationMetadata(
            org="test",
            repo="test",
            issue_number=3,
            original_confidence=0.8,
            ai_reasoning="test",
            recommended_labels=["product::kots", "product::vendor", "type::bug"],
            labels_to_remove=[],
            status=RecommendationStatus.PENDING,
            status_updated_at=now,
            ai_result_file="test",
            issue_file="test",
        )
        assert multi_product.primary_product == "product::kots"

    def test_review_action_enum(self):
        """Test ReviewAction enum values."""
        assert ReviewAction.APPROVE.value == "approve"
        assert ReviewAction.REJECT.value == "reject"
        assert ReviewAction.MODIFY.value == "modify"
        assert ReviewAction.REQUEST_CHANGES.value == "request_changes"

    def test_recommendation_status_enum(self):
        """Test RecommendationStatus enum values."""
        assert RecommendationStatus.PENDING.value == "pending"
        assert RecommendationStatus.APPROVED.value == "approved"
        assert RecommendationStatus.REJECTED.value == "rejected"
        assert RecommendationStatus.NEEDS_MODIFICATION.value == "needs_modification"
        assert RecommendationStatus.APPLIED.value == "applied"
        assert RecommendationStatus.FAILED.value == "failed"
        assert RecommendationStatus.ARCHIVED.value == "archived"
