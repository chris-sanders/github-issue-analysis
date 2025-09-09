"""Tests for AI analysis functions."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.messages import BinaryContent

from gh_analysis.ai.analysis import (
    analyze_issue,
    format_issue_prompt,
    prepare_issue_for_analysis,
)
from gh_analysis.ai.models import (
    LabelAssessment,
    ProductLabel,
    ProductLabelingResponse,
    RecommendedLabel,
)


@pytest.fixture
def sample_issue_data() -> dict[str, Any]:
    """Sample issue data for testing."""
    return {
        "org": "test-org",
        "repo": "test-repo",
        "issue": {
            "number": 1,
            "title": "KOTS admin console not loading",
            "body": "The kotsadm interface shows a blank screen after login",
            "labels": [{"name": "bug"}, {"name": "product::kots"}],
            "comments": [],
        },
    }


@pytest.fixture
def sample_kots_response() -> ProductLabelingResponse:
    """Sample ProductLabelingResponse for KOTS issue."""
    return ProductLabelingResponse(
        recommendation_confidence=0.9,
        recommended_labels=[
            RecommendedLabel(
                label=ProductLabel.KOTS,
                reasoning="Issue clearly mentions kotsadm admin interface",
            )
        ],
        current_labels_assessment=[
            LabelAssessment(
                label="bug", correct=True, reasoning="This is indeed a bug report"
            )
        ],
        summary="KOTS admin console loading issue",
        reasoning="The issue mentions kotsadm interface problems, "
        "which is the KOTS admin console",
    )


@pytest.mark.asyncio
async def test_analyze_issue_basic(
    sample_issue_data: dict[str, Any], sample_kots_response: ProductLabelingResponse
) -> None:
    """Test basic issue analysis functionality."""
    # Mock the agent to avoid OpenAI client initialization
    mock_agent = AsyncMock()
    mock_agent.run.return_value.output = sample_kots_response

    # Just pass the mock agent directly - no need to patch
    result = await analyze_issue(mock_agent, sample_issue_data)

    # Verify the response structure
    assert isinstance(result, ProductLabelingResponse)
    assert result.recommendation_confidence == 0.9
    assert len(result.recommended_labels) == 1
    assert result.recommended_labels[0].label == ProductLabel.KOTS
    assert "kotsadm" in result.recommended_labels[0].reasoning.lower()

    # Verify agent was called with proper message parts
    mock_agent.run.assert_called_once()
    message_parts = mock_agent.run.call_args[0][0]
    assert isinstance(message_parts, list)
    assert len(message_parts) >= 1  # At least the text prompt
    assert isinstance(message_parts[0], str)


@pytest.mark.asyncio
async def test_analyze_issue_with_model_override() -> None:
    """Test issue analysis with model and settings override."""
    mock_response = ProductLabelingResponse(
        recommendation_confidence=0.85,
        recommended_labels=[
            RecommendedLabel(
                label=ProductLabel.EMBEDDED_CLUSTER,
                reasoning="Issue involves cluster installation and k0s setup",
            ),
        ],
        current_labels_assessment=[],
        summary="Installation issue",
        reasoning="Test reasoning",
    )

    sample_data = {
        "org": "test",
        "repo": "test",
        "issue": {
            "number": 1,
            "title": "Test issue",
            "body": "Test body",
            "labels": [],
            "comments": [],
        },
    }

    # Mock the agent
    mock_agent = AsyncMock()
    mock_agent.run.return_value.output = mock_response

    result = await analyze_issue(
        mock_agent,
        sample_data,
        model="anthropic:claude-3-5-sonnet",
        model_settings={"temperature": 0.5, "reasoning_effort": "high"},
    )

    # Verify result
    assert isinstance(result, ProductLabelingResponse)
    assert len(result.recommended_labels) == 1

    # Verify agent was called with overrides
    mock_agent.run.assert_called_once()
    _, kwargs = mock_agent.run.call_args
    assert kwargs.get("model") == "anthropic:claude-3-5-sonnet"
    assert kwargs.get("model_settings") == {
        "temperature": 0.5,
        "reasoning_effort": "high",
    }


def test_prepare_issue_for_analysis(sample_issue_data: dict[str, Any]) -> None:
    """Test prepare_issue_for_analysis function."""
    # Test without images
    message_parts = prepare_issue_for_analysis(sample_issue_data, include_images=False)
    assert isinstance(message_parts, list)
    assert len(message_parts) == 1
    assert isinstance(message_parts[0], str)
    assert "KOTS admin console not loading" in message_parts[0]

    # Test with images (mocked)
    with patch(
        "gh_analysis.ai.analysis.load_downloaded_images"
    ) as mock_load_images:
        mock_load_images.return_value = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,test"},
                "metadata": {"source": "issue_body", "filename": "test.png"},
            }
        ]
        message_parts = prepare_issue_for_analysis(
            sample_issue_data, include_images=True
        )
        assert len(message_parts) == 2
        assert isinstance(message_parts[0], str)
        assert isinstance(message_parts[1], BinaryContent)
        assert message_parts[1].media_type == "image/png"


def test_format_issue_prompt(sample_issue_data: dict[str, Any]) -> None:
    """Test issue prompt formatting."""
    prompt = format_issue_prompt(sample_issue_data)

    # Verify prompt contains expected components
    assert "KOTS admin console not loading" in prompt
    assert "kotsadm interface shows a blank screen" in prompt
    assert "test-org/test-repo" in prompt
    assert "product::kots" in prompt
    assert "bug" not in prompt  # Non-product labels should be filtered out
    assert "No comments" in prompt
    assert "NO IMAGES PROVIDED" in prompt  # No images context


def test_format_issue_prompt_with_comments_and_images() -> None:
    """Test issue prompt formatting with comments and image context."""
    issue_data_with_comments = {
        "org": "test-org",
        "repo": "test-repo",
        "issue": {
            "number": 1,
            "title": "Test issue",
            "body": "Test body",
            "labels": [],
            "comments": [
                {
                    "user": {"login": "user1"},
                    "body": "This is a test comment with some details about the issue",
                },
                {
                    "user": {"login": "user2"},
                    "body": "Another comment with more information",
                },
            ],
        },
    }

    # Test without images
    prompt = format_issue_prompt(issue_data_with_comments, image_count=0)
    assert "user1: This is a test comment" in prompt
    assert "user2: Another comment" in prompt
    assert "NO IMAGES PROVIDED" in prompt

    # Test with images
    prompt_with_images = format_issue_prompt(issue_data_with_comments, image_count=2)
    assert "IMAGES PROVIDED:** This issue contains 2 image(s)" in prompt_with_images
    assert "Fill in the images_analyzed array" in prompt_with_images


@pytest.mark.asyncio
async def test_analyze_issue_fallback_on_multimodal_failure() -> None:
    """Test that analyze_issue falls back to text-only on multimodal failure."""
    sample_data = {
        "org": "test",
        "repo": "test",
        "issue": {
            "number": 1,
            "title": "Test issue",
            "body": "Test body",
            "labels": [],
            "comments": [],
        },
    }

    mock_response = ProductLabelingResponse(
        recommendation_confidence=0.9,
        recommended_labels=[
            RecommendedLabel(label=ProductLabel.KOTS, reasoning="Fallback reasoning")
        ],
        current_labels_assessment=[],
        summary="Test summary",
        reasoning="Test reasoning",
    )

    # Mock agent that fails on multimodal but succeeds on text-only
    mock_agent = AsyncMock()
    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (multimodal) fails
            raise Exception("Multimodal processing failed")
        else:
            # Second call (text-only) succeeds
            result = AsyncMock()
            result.output = mock_response
            return result

    mock_agent.run.side_effect = side_effect

    # Mock image loading to return images
    with patch(
        "gh_analysis.ai.analysis.load_downloaded_images"
    ) as mock_load_images:
        mock_load_images.return_value = [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,test"},
            }
        ]

        result = await analyze_issue(mock_agent, sample_data, include_images=True)

        # Verify fallback happened
        assert mock_agent.run.call_count == 2
        assert isinstance(result, ProductLabelingResponse)
        assert result.recommendation_confidence == 0.9
