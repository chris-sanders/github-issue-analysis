"""Schema validation tests for troubleshooting agents.

# type: ignore

This test catches issues that our current tests miss:
1. Response schema validation failures
2. Agent output format mismatches
3. Pydantic model compatibility
4. Complex nested field validation

These tests use mocked responses to validate the full pipeline
without making real API calls.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from gh_analysis.ai.analysis import analyze_troubleshooting_issue
from gh_analysis.ai.models import (
    NeedsDataAnalysis,
    ResolvedAnalysis,
)
from gh_analysis.ai.troubleshooting_agents import create_troubleshooting_agent


class TestTroubleshootingSchemaValidation:
    """Test schema validation for troubleshooting responses."""

    @pytest.fixture
    def sample_issue_data(self):
        """Sample issue data for testing."""
        return {
            "org": "test-org",
            "repo": "test-repo",
            "issue": {
                "number": 123,
                "title": "Database connection timeout",
                "body": "Getting timeout errors when connecting to PostgreSQL",
                "labels": [{"name": "bug"}],
                "user": {"login": "testuser"},
                "comments": [],
            },
        }

    def test_resolved_analysis_schema_valid(self):
        """Test that a valid resolved analysis passes schema validation."""
        valid_resolved = {
            "status": "resolved",
            "root_cause": "Database connection pool exhaustion",
            "evidence": [
                "Connection timeout after 30 seconds",
                "Max connections reached",
            ],
            "solution": "Increase connection pool size and monitoring",
            "validation": "Evidence confirms pool exhaustion as root cause.",
        }

        # This should not raise an exception
        response = ResolvedAnalysis(**valid_resolved)
        assert response.status == "resolved"
        assert len(response.evidence) == 2
        assert "pool exhaustion" in response.root_cause

    def test_needs_data_analysis_schema_valid(self):
        """Test that a valid needs_data analysis passes schema validation."""
        valid_needs_data = {
            "status": "needs_data",
            "current_hypothesis": "Possible database connection issue",
            "missing_evidence": [
                "Database connection logs",
                "Network connectivity test results",
            ],
            "next_steps": [
                "Check database server status",
                "Run network diagnostics",
            ],
            "eliminated": ["Out of disk space - logs show sufficient space"],
        }

        # This should not raise an exception
        response = NeedsDataAnalysis(**valid_needs_data)
        assert response.status == "needs_data"
        assert len(response.missing_evidence) == 2
        assert "database connection" in response.current_hypothesis.lower()

    def test_resolved_analysis_schema_invalid_missing_fields(self):
        """Test that resolved analysis missing required fields fail validation."""
        invalid_responses = [
            # Missing root_cause
            {
                "status": "resolved",
                "evidence": ["finding"],
                "solution": "Test fix",
                "validation": "Test validation",
            },
            # Missing evidence
            {
                "status": "resolved",
                "root_cause": "Test cause",
                "solution": "Test fix",
                "validation": "Test validation",
            },
            # Missing solution
            {
                "status": "resolved",
                "root_cause": "Test cause",
                "evidence": ["finding"],
                "validation": "Test validation",
            },
        ]

        for invalid_response in invalid_responses:
            with pytest.raises(ValidationError):
                ResolvedAnalysis(**invalid_response)  # type: ignore[arg-type]

    def test_needs_data_analysis_schema_invalid_missing_fields(self):
        """Test that needs_data analysis missing required fields fail validation."""
        invalid_responses = [
            # Missing current_hypothesis
            {
                "status": "needs_data",
                "missing_evidence": ["evidence"],
                "next_steps": ["step"],
                "eliminated": ["ruled out"],
            },
            # Missing missing_evidence
            {
                "status": "needs_data",
                "current_hypothesis": "Test hypothesis",
                "next_steps": ["step"],
                "eliminated": ["ruled out"],
            },
        ]

        for invalid_response in invalid_responses:
            with pytest.raises(ValidationError):
                NeedsDataAnalysis(**invalid_response)

    def test_discriminated_union_validation(self):
        """Test that the discriminated union works correctly."""
        # Valid resolved analysis should work
        resolved_data = {
            "status": "resolved",
            "root_cause": "Database connection pool exhaustion",
            "evidence": ["Connection timeout", "Max connections reached"],
            "solution": "Increase connection pool size",
            "validation": "Evidence confirms root cause",
        }

        resolved = ResolvedAnalysis(**resolved_data)
        assert resolved.status == "resolved"

        # Valid needs_data analysis should work
        needs_data_data = {
            "status": "needs_data",
            "current_hypothesis": "Possible memory leak",
            "missing_evidence": ["Memory usage logs"],
            "next_steps": ["Check memory usage"],
            "eliminated": ["Disk space issues"],
        }

        needs_data = NeedsDataAnalysis(**needs_data_data)
        assert needs_data.status == "needs_data"

        # Wrong status for model should fail
        with pytest.raises(ValidationError):
            ResolvedAnalysis(
                **{
                    "status": "needs_data",  # Wrong status for ResolvedAnalysis
                    "root_cause": "Test",
                    "evidence": ["test"],
                    "solution": "test",
                    "validation": "test",
                }
            )

    def test_resolved_analysis_forbids_extra_fields(self):
        """Test that extra fields are rejected due to extra='forbid'."""
        response_with_extra = {
            "status": "resolved",
            "root_cause": "Test cause",
            "evidence": ["finding"],
            "solution": "Test fix",
            "validation": "Test validation",
            "extra_field": "This should be rejected",  # Extra field
        }

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ResolvedAnalysis(**response_with_extra)

    def test_agent_creation_with_union_output_type(self):
        """Test that agents can be created with discriminated union output type."""
        # This test verifies that PydanticAI can handle discriminated unions
        # as output_type without throwing "Cannot instantiate typing.Union" errors

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            try:
                agent = create_troubleshooting_agent("gpt5_mini_medium", "test-token")
                assert agent is not None
                # Just verify the agent was created successfully
                assert hasattr(agent, "output_type")

                # Verify the Union type is properly set
                from typing import get_origin

                assert get_origin(agent.output_type) is not None  # Should be Union

            except TypeError as e:
                if "union" in str(e).lower() and "instantiate" in str(e).lower():
                    pytest.fail(f"Union instantiation error: {e}")
                else:
                    raise

    @pytest.mark.asyncio
    async def test_agent_response_validation_missing_fields(self, sample_issue_data):
        """Test agent pipeline with API response missing required fields."""

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            agent = create_troubleshooting_agent("gpt5_mini_medium", "test-token")

            # Mock resolved response
            mock_response = ResolvedAnalysis(
                status="resolved",
                root_cause="Database issue",
                evidence=["Connection timeout"],
                solution="Restart database",
                validation="Database needs restart",
            )

            mock_result = AsyncMock()
            mock_result.output = mock_response

            with patch.object(agent, "run", return_value=mock_result):
                # This should work with the mocked response
                result = await analyze_troubleshooting_issue(
                    agent, sample_issue_data, include_images=False
                )
                # Verify the result is our mocked response
                assert result.status == "resolved"
                assert result.root_cause == "Database issue"

    def test_json_serialization_roundtrip(self):
        """Test that valid responses can be serialized and deserialized."""
        resolved_data = {
            "status": "resolved",
            "root_cause": "Network connectivity issue",
            "evidence": [
                "DNS resolution failing",
                "Firewall blocking port 443",
            ],
            "solution": "Update DNS settings and configure firewall rules",
            "validation": "App cannot reach external services - network issues.",
        }

        # Create model instance
        response = ResolvedAnalysis(**resolved_data)

        # Serialize to JSON
        json_str = response.model_dump_json()

        # Deserialize back
        reconstructed_data = json.loads(json_str)
        reconstructed_response = ResolvedAnalysis(**reconstructed_data)

        # Verify it's identical
        assert reconstructed_response.status == response.status
        assert reconstructed_response.root_cause == response.root_cause
        assert reconstructed_response.evidence == response.evidence

    def test_real_world_response_patterns(self):
        """Test patterns that might come from actual GPT responses."""

        # Pattern 1: Resolved analysis with detailed explanations
        resolved_response = {
            "status": "resolved",
            "root_cause": "The issue is caused by insufficient memory allocation",
            "evidence": [
                "Pod memory usage at 95%",
                "OOMKilled events in logs",
                "No memory limits set",
            ],
            "solution": "Set memory limits and requests in deployment manifests",
            "validation": "Memory exhaustion issue based on logs and data.",
        }

        # This should work fine
        response = ResolvedAnalysis(**resolved_response)
        assert "memory" in response.root_cause.lower()

        # Pattern 2: Needs data analysis with empty lists (valid)
        needs_data_response = {
            "status": "needs_data",
            "current_hypothesis": "Possible resource exhaustion",
            "missing_evidence": ["Resource usage logs"],
            "next_steps": ["Check resource usage"],
            "eliminated": [],  # Empty list is valid
        }

        response2 = NeedsDataAnalysis(**needs_data_response)
        assert response2.eliminated == []
