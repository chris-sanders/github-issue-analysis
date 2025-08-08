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

from github_issue_analysis.ai.analysis import analyze_troubleshooting_issue
from github_issue_analysis.ai.models import (
    ResolvedAnalysis,
    TechnicalAnalysis,
    TroubleshootingResponse,
)
from github_issue_analysis.ai.troubleshooting_agents import create_troubleshooting_agent


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

    def test_troubleshooting_response_schema_invalid_missing_fields(self):
        """Test that responses missing required fields fail validation."""
        invalid_responses = [
            # Missing analysis
            {
                "confidence_score": 0.85,
                "tools_used": ["kubectl"],
                "processing_time_seconds": 15.2,
            },
            # Missing confidence_score
            {
                "analysis": {
                    "root_cause": "Test cause",
                    "key_findings": ["finding"],
                    "remediation": "Test fix",
                    "explanation": "Test explanation",
                },
                "tools_used": ["kubectl"],
                "processing_time_seconds": 15.2,
            },
            # Missing processing_time_seconds
            {
                "analysis": {
                    "root_cause": "Test cause",
                    "key_findings": ["finding"],
                    "remediation": "Test fix",
                    "explanation": "Test explanation",
                },
                "confidence_score": 0.85,
                "tools_used": ["kubectl"],
            },
        ]

        for invalid_response in invalid_responses:
            with pytest.raises(ValidationError):
                TroubleshootingResponse(**invalid_response)

    def test_troubleshooting_response_schema_invalid_field_types(self):
        """Test that responses with wrong field types fail validation."""
        invalid_responses = [
            # confidence_score > 1.0
            {
                "analysis": {
                    "root_cause": "Test",
                    "key_findings": ["test"],
                    "remediation": "Test",
                    "explanation": "Test",
                },
                "confidence_score": 1.5,  # Invalid: > 1.0
                "tools_used": ["kubectl"],
                "processing_time_seconds": 15.2,
            },
            # confidence_score < 0.0
            {
                "analysis": {
                    "root_cause": "Test",
                    "key_findings": ["test"],
                    "remediation": "Test",
                    "explanation": "Test",
                },
                "confidence_score": -0.1,  # Invalid: < 0.0
                "tools_used": ["kubectl"],
                "processing_time_seconds": 15.2,
            },
            # tools_used as string instead of list
            {
                "analysis": {
                    "root_cause": "Test",
                    "key_findings": ["test"],
                    "remediation": "Test",
                    "explanation": "Test",
                },
                "confidence_score": 0.8,
                "tools_used": "kubectl",  # Invalid: should be list
                "processing_time_seconds": 15.2,
            },
        ]

        for invalid_response in invalid_responses:
            with pytest.raises(ValidationError):
                TroubleshootingResponse(**invalid_response)

    def test_troubleshooting_response_forbids_extra_fields(self):
        """Test that extra fields are rejected due to extra='forbid'."""
        response_with_extra = {
            "analysis": {
                "root_cause": "Test cause",
                "key_findings": ["finding"],
                "remediation": "Test fix",
                "explanation": "Test explanation",
            },
            "confidence_score": 0.85,
            "tools_used": ["kubectl"],
            "processing_time_seconds": 15.2,
            "extra_field": "This should be rejected",  # Extra field
        }

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TroubleshootingResponse(**response_with_extra)

    @pytest.mark.asyncio
    async def test_agent_response_validation_with_mock_api(self, sample_issue_data):
        """Test agent pipeline with mocked API responses causing validation errors."""

        # Test Case 1: API returns malformed JSON
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            agent = create_troubleshooting_agent("gpt5_mini_medium", "test-token")

            # Mock the agent.run to return malformed response
            mock_result = AsyncMock()
            mock_result.output = "This is not valid JSON for TroubleshootingResponse"

            with patch.object(agent, "run", return_value=mock_result):
                # This should handle the validation error gracefully
                with pytest.raises(Exception):  # Could be ValidationError or other
                    await analyze_troubleshooting_issue(
                        agent, sample_issue_data, include_images=False
                    )

    @pytest.mark.asyncio
    async def test_agent_response_validation_missing_fields(self, sample_issue_data):
        """Test agent pipeline with API response missing required fields."""

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}):
            agent = create_troubleshooting_agent("gpt5_mini_medium", "test-token")

            # Mock incomplete response (missing confidence_score)
            incomplete_response = TechnicalAnalysis(
                root_cause="Database issue",
                key_findings=["Connection timeout"],
                remediation="Restart database",
                explanation="Database needs restart",
            )

            mock_result = AsyncMock()
            mock_result.output = incomplete_response  # Missing other required fields

            with patch.object(agent, "run", return_value=mock_result):
                # This should fail when trying to use the incomplete response
                with pytest.raises(
                    AttributeError
                ):  # Missing confidence_score, tools_used, etc.
                    result = await analyze_troubleshooting_issue(
                        agent, sample_issue_data, include_images=False
                    )
                    # Try to access fields that should be there
                    _ = result.confidence_score

    def test_json_serialization_roundtrip(self):
        """Test that valid responses can be serialized and deserialized."""
        valid_response_data = {
            "analysis": {
                "root_cause": "Network connectivity issue",
                "key_findings": [
                    "DNS resolution failing",
                    "Firewall blocking port 443",
                ],
                "remediation": "Update DNS settings and configure firewall rules",
                "explanation": "App cannot reach external services - network issues.",
            },
            "confidence_score": 0.92,
            "tools_used": ["nslookup", "telnet", "netstat"],
            "processing_time_seconds": 23.7,
        }

        # Create model instance
        response = TroubleshootingResponse(**valid_response_data)

        # Serialize to JSON
        json_str = response.model_dump_json()

        # Deserialize back
        reconstructed_data = json.loads(json_str)
        reconstructed_response = TroubleshootingResponse(**reconstructed_data)

        # Verify it's identical
        assert reconstructed_response.confidence_score == response.confidence_score
        assert (
            reconstructed_response.analysis.root_cause == response.analysis.root_cause
        )
        assert reconstructed_response.tools_used == response.tools_used

    def test_real_world_response_patterns(self):
        """Test patterns that might come from actual GPT responses."""

        # Pattern 1: GPT might return extra explanatory text
        gpt_style_response = {
            "analysis": {
                "root_cause": "The issue is caused by insufficient memory allocation",
                "key_findings": [
                    "Pod memory usage at 95%",
                    "OOMKilled events in logs",
                    "No memory limits set",
                ],
                "remediation": "Set memory limits and requests in deployment manifests",
                "explanation": "Memory exhaustion issue based on logs and data.",
            },
            "confidence_score": 0.88,
            "tools_used": ["kubectl top pods", "kubectl describe pod", "kubectl logs"],
            "processing_time_seconds": 18.5,
        }

        # This should work fine
        response = TroubleshootingResponse(**gpt_style_response)
        assert "memory" in response.analysis.root_cause.lower()

        # Pattern 2: Decimal confidence scores
        response_with_decimal = gpt_style_response.copy()
        response_with_decimal["confidence_score"] = 0.887655  # High precision

        response2 = TroubleshootingResponse(**response_with_decimal)
        assert response2.confidence_score == 0.887655

        # Pattern 3: Empty tools_used (valid)
        response_no_tools = gpt_style_response.copy()
        response_no_tools["tools_used"] = []

        response3 = TroubleshootingResponse(**response_no_tools)
        assert response3.tools_used == []
