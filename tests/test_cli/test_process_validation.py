"""Integration tests for CLI settings validation."""

from typer.testing import CliRunner

from github_issue_analysis.cli.main import app

runner = CliRunner(env={"NO_COLOR": "1", "FORCE_COLOR": "0"})


class TestProcessCommandValidation:
    """Test settings validation in process command."""

    def test_invalid_setting_name(self) -> None:
        """Test that invalid setting names are caught."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "openai:o4-mini",
                "--setting",
                "thinking=high",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "Unknown setting 'thinking'" in result.output
        assert "Valid settings for openai:o4-mini:" in result.output

    def test_model_inappropriate_setting(self) -> None:
        """Test that model-inappropriate settings are caught."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "anthropic:claude-3-5-sonnet-latest",
                "--setting",
                "openai_reasoning_effort=high",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "not supported by anthropic models" in result.output

    def test_temperature_out_of_range_openai(self) -> None:
        """Test temperature validation for OpenAI models."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "openai:o4-mini",
                "--setting",
                "temperature=3.0",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "Temperature 3.0 out of range for OpenAI (0-2)" in result.output

    def test_temperature_out_of_range_anthropic(self) -> None:
        """Test temperature validation for Anthropic models."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "anthropic:claude-3-5-sonnet-latest",
                "--setting",
                "temperature=1.5",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "Temperature 1.5 out of range for anthropic (0-1)" in result.output

    def test_invalid_reasoning_effort(self) -> None:
        """Test openai_reasoning_effort validation."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "openai:o4-mini",
                "--setting",
                "openai_reasoning_effort=extreme",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "must be 'low', 'medium', or 'high'" in result.output

    def test_multiple_invalid_settings(self) -> None:
        """Test multiple validation errors."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "openai:o4-mini",
                "--setting",
                "invalid_setting=value",
                "--setting",
                "temperature=3.0",
                "--setting",
                "max_tokens=-100",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "Unknown setting 'invalid_setting'" in result.output
        assert "Temperature 3.0 out of range" in result.output
        assert "max_tokens must be positive" in result.output

    def test_setting_format_validation(self) -> None:
        """Test that setting format is validated."""
        result = runner.invoke(
            app,
            [
                "process",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--issue-number",
                "123",
                "--model",
                "openai:o4-mini",
                "--setting",
                "invalid-format",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid setting format" in result.output
        assert "Use key=value format" in result.output


class TestBatchCommandValidation:
    """Test settings validation in batch command."""

    def test_non_openai_model_rejected(self) -> None:
        """Test that non-OpenAI models are rejected for batch processing."""
        result = runner.invoke(
            app,
            [
                "batch",
                "submit",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--model",
                "anthropic:claude-3-5-sonnet-latest",
                "--dry-run",
            ],
        )
        assert result.exit_code == 1
        assert (
            "❌ Batch processing is only available for OpenAI models" in result.output
        )
        assert "Supported models: openai:gpt-4o, openai:o4-mini" in result.output

    def test_invalid_temperature_batch(self) -> None:
        """Test temperature validation in batch command."""
        result = runner.invoke(
            app,
            [
                "batch",
                "submit",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--model",
                "openai:o4-mini",
                "--temperature",
                "3.0",
                "--dry-run",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "Temperature 3.0 out of range for OpenAI (0-2)" in result.output

    def test_invalid_thinking_effort_batch(self) -> None:
        """Test thinking effort validation in batch command."""
        result = runner.invoke(
            app,
            [
                "batch",
                "submit",
                "product-labeling",
                "--org",
                "test-org",
                "--repo",
                "test-repo",
                "--model",
                "openai:o4-mini",
                "--thinking-effort",
                "extreme",
                "--dry-run",
            ],
        )
        assert result.exit_code == 1
        assert "❌ Invalid settings:" in result.output
        assert "must be 'low', 'medium', or 'high'" in result.output


class TestShowSettingsCommand:
    """Test show-settings command."""

    def test_show_settings_command(self) -> None:
        """Test that show-settings command runs without error."""
        result = runner.invoke(app, ["process", "show-settings"])
        # Command should succeed
        assert result.exit_code == 0
        # Should show some output about settings
        assert "settings" in result.output.lower() or "Settings" in result.output
