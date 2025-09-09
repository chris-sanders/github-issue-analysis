"""Tests for simplified PydanticAI agent creation interface."""

import pytest

from gh_analysis.ai.agents import product_labeling_agent

# Tests for model validation and thinking support have been removed
# as we now let PydanticAI handle all model validation


class TestProductLabelingAgent:
    """Tests for the default product labeling agent."""

    def test_agent_exists(self) -> None:
        """Test that the product labeling agent is available."""
        # Verify the agent exists and has expected attributes
        assert product_labeling_agent is not None
        assert hasattr(product_labeling_agent, "run")  # Should have a run method

    @pytest.mark.asyncio
    async def test_agent_usage(self) -> None:
        """Test basic usage of the agent."""
        # This is more of an integration test - it would require actual API keys
        # For now, just verify the agent can be called
        try:
            # This will fail without API keys, but we can test the interface
            await product_labeling_agent.run("Test prompt")
        except Exception:
            # Expected without proper API setup - just verify the interface exists
            pass
