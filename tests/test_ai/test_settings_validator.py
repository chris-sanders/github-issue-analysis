"""Tests for settings validation module."""

from gh_analysis.ai.settings_validator import (
    get_provider_from_model,
    get_valid_settings_help,
    validate_settings,
)


class TestGetProviderFromModel:
    """Test provider extraction from model strings."""

    def test_openai_model(self) -> None:
        """Test OpenAI model provider extraction."""
        assert get_provider_from_model("openai:gpt-4o") == "openai"
        assert get_provider_from_model("openai:o4-mini") == "openai"

    def test_anthropic_model(self) -> None:
        """Test Anthropic model provider extraction."""
        assert get_provider_from_model("anthropic:claude-3-5-sonnet") == "anthropic"
        assert get_provider_from_model("anthropic:claude-3-opus") == "anthropic"

    def test_google_model(self) -> None:
        """Test Google model provider extraction."""
        assert get_provider_from_model("google:gemini-pro") == "google"
        assert get_provider_from_model("google:gemini-ultra") == "google"

    def test_unknown_provider(self) -> None:
        """Test unknown provider handling."""
        assert get_provider_from_model("custom-model") == "unknown"
        assert get_provider_from_model("no-colon") == "unknown"


class TestValidateSettings:
    """Test settings validation logic."""

    def test_valid_openai_settings(self) -> None:
        """Test valid settings for OpenAI models."""
        settings = {
            "temperature": 0.5,
            "max_tokens": 1000,
            "openai_reasoning_effort": "high",
            "timeout": 30.0,
            "seed": 42,
            "top_p": 0.9,
        }
        errors = validate_settings("openai:gpt-4o", settings)
        assert errors == []

    def test_valid_anthropic_settings(self) -> None:
        """Test valid settings for Anthropic models."""
        settings = {
            "temperature": 0.7,
            "max_tokens": 2000,
            "anthropic_thinking": "true",
            "timeout": 60.0,
            "top_p": 0.95,
        }
        errors = validate_settings("anthropic:claude-3-5-sonnet", settings)
        assert errors == []

    def test_valid_google_settings(self) -> None:
        """Test valid settings for Google models."""
        settings = {
            "temperature": 0.8,
            "max_tokens": 1500,
            "google_thinking_config": "enabled",
            "timeout": 45.0,
        }
        errors = validate_settings("google:gemini-pro", settings)
        assert errors == []

    def test_unknown_setting_name(self) -> None:
        """Test that unknown settings are caught."""
        settings = {"thinking": "high", "invalid_setting": "value"}
        errors = validate_settings("openai:gpt-4o", settings)
        assert len(errors) == 2
        assert "Unknown setting 'thinking'" in errors[0]
        assert "Unknown setting 'invalid_setting'" in errors[1]

    def test_model_inappropriate_settings(self) -> None:
        """Test that model-inappropriate settings are caught."""
        # OpenAI setting on Anthropic model
        settings = {"openai_reasoning_effort": "high"}
        errors = validate_settings("anthropic:claude-3-5-sonnet", settings)
        assert len(errors) == 1
        assert "not supported by anthropic models" in errors[0]

        # Anthropic setting on OpenAI model
        settings = {"anthropic_thinking": "true"}
        errors = validate_settings("openai:gpt-4o", settings)
        assert len(errors) == 1
        assert "not supported by openai models" in errors[0]

        # Google setting on OpenAI model
        settings = {"google_thinking_config": "enabled"}
        errors = validate_settings("openai:gpt-4o", settings)
        assert len(errors) == 1
        assert "not supported by openai models" in errors[0]

    def test_temperature_validation(self) -> None:
        """Test temperature range validation."""
        # Valid for OpenAI (0-2)
        assert validate_settings("openai:gpt-4o", {"temperature": 0.0}) == []
        assert validate_settings("openai:gpt-4o", {"temperature": 2.0}) == []

        # Invalid for OpenAI
        errors = validate_settings("openai:gpt-4o", {"temperature": 2.5})
        assert len(errors) == 1
        assert "out of range for OpenAI (0-2)" in errors[0]

        # Valid for Anthropic/Google (0-1)
        assert validate_settings("anthropic:claude-3", {"temperature": 0.5}) == []
        assert validate_settings("google:gemini-pro", {"temperature": 1.0}) == []

        # Invalid for Anthropic/Google
        errors = validate_settings("anthropic:claude-3", {"temperature": 1.5})
        assert len(errors) == 1
        assert "out of range for anthropic (0-1)" in errors[0]

        # Invalid type
        errors = validate_settings("openai:gpt-4o", {"temperature": "hot"})
        assert len(errors) == 1
        assert "Temperature must be a number" in errors[0]

    def test_max_tokens_validation(self) -> None:
        """Test max_tokens validation."""
        # Valid
        assert validate_settings("openai:gpt-4o", {"max_tokens": 100}) == []
        assert validate_settings("openai:gpt-4o", {"max_tokens": 4096}) == []

        # Invalid - negative
        errors = validate_settings("openai:gpt-4o", {"max_tokens": -100})
        assert len(errors) == 1
        assert "max_tokens must be positive" in errors[0]

        # Invalid - zero
        errors = validate_settings("openai:gpt-4o", {"max_tokens": 0})
        assert len(errors) == 1
        assert "max_tokens must be positive" in errors[0]

        # Invalid type
        errors = validate_settings("openai:gpt-4o", {"max_tokens": "many"})
        assert len(errors) == 1
        assert "max_tokens must be an integer" in errors[0]

    def test_timeout_validation(self) -> None:
        """Test timeout validation."""
        # Valid
        assert validate_settings("openai:gpt-4o", {"timeout": 30.0}) == []
        assert validate_settings("openai:gpt-4o", {"timeout": 60}) == []

        # Invalid - negative
        errors = validate_settings("openai:gpt-4o", {"timeout": -10.0})
        assert len(errors) == 1
        assert "timeout must be positive" in errors[0]

        # Invalid type
        errors = validate_settings("openai:gpt-4o", {"timeout": "long"})
        assert len(errors) == 1
        assert "timeout must be a number" in errors[0]

    def test_seed_validation(self) -> None:
        """Test seed validation."""
        # Valid
        assert validate_settings("openai:gpt-4o", {"seed": 42}) == []
        assert validate_settings("openai:gpt-4o", {"seed": 0}) == []
        assert validate_settings("openai:gpt-4o", {"seed": -1}) == []

        # Invalid type
        errors = validate_settings("openai:gpt-4o", {"seed": "random"})
        assert len(errors) == 1
        assert "seed must be an integer" in errors[0]

    def test_top_p_validation(self) -> None:
        """Test top_p validation."""
        # Valid
        assert validate_settings("openai:gpt-4o", {"top_p": 0.0}) == []
        assert validate_settings("openai:gpt-4o", {"top_p": 0.5}) == []
        assert validate_settings("openai:gpt-4o", {"top_p": 1.0}) == []

        # Invalid - out of range
        errors = validate_settings("openai:gpt-4o", {"top_p": 1.5})
        assert len(errors) == 1
        assert "top_p must be between 0 and 1" in errors[0]

        errors = validate_settings("openai:gpt-4o", {"top_p": -0.1})
        assert len(errors) == 1
        assert "top_p must be between 0 and 1" in errors[0]

        # Invalid type
        errors = validate_settings("openai:gpt-4o", {"top_p": "high"})
        assert len(errors) == 1
        assert "top_p must be a number" in errors[0]

    def test_openai_reasoning_effort_validation(self) -> None:
        """Test openai_reasoning_effort validation."""
        # Valid
        assert (
            validate_settings("openai:gpt-4o", {"openai_reasoning_effort": "low"}) == []
        )
        assert (
            validate_settings("openai:gpt-4o", {"openai_reasoning_effort": "medium"})
            == []
        )
        assert (
            validate_settings("openai:gpt-4o", {"openai_reasoning_effort": "high"})
            == []
        )

        # Invalid value
        errors = validate_settings(
            "openai:gpt-4o", {"openai_reasoning_effort": "extreme"}
        )
        assert len(errors) == 1
        assert "must be 'low', 'medium', or 'high'" in errors[0]

    def test_multiple_errors(self) -> None:
        """Test that multiple errors are all caught."""
        settings = {
            "invalid_setting": "value",
            "temperature": 3.0,
            "max_tokens": -100,
            "openai_reasoning_effort": "extreme",
        }
        errors = validate_settings("openai:gpt-4o", settings)
        assert len(errors) == 4
        assert any("Unknown setting" in e for e in errors)
        assert any("Temperature" in e for e in errors)
        assert any("max_tokens" in e for e in errors)
        assert any("reasoning_effort" in e for e in errors)

    def test_unknown_provider_validation(self) -> None:
        """Test validation with unknown provider."""
        # Should allow all valid PydanticAI settings
        settings = {
            "temperature": 0.5,
            "max_tokens": 1000,
            "timeout": 30.0,
            "seed": 42,
            "top_p": 0.9,
        }
        errors = validate_settings("custom-model", settings)
        assert errors == []

        # But still catch invalid settings
        errors = validate_settings("custom-model", {"invalid": "value"})
        assert len(errors) == 1
        assert "Unknown setting" in errors[0]


class TestGetValidSettingsHelp:
    """Test help text generation."""

    def test_openai_help(self) -> None:
        """Test help text for OpenAI models."""
        help_text = get_valid_settings_help("openai:gpt-4o")
        assert "Valid settings for openai:gpt-4o:" in help_text
        assert "openai_reasoning_effort" in help_text
        assert "temperature: Sampling temperature (0-2)" in help_text
        assert "max_tokens" in help_text
        assert "timeout" in help_text
        assert "seed" in help_text
        assert "top_p" in help_text

    def test_anthropic_help(self) -> None:
        """Test help text for Anthropic models."""
        help_text = get_valid_settings_help("anthropic:claude-3-5-sonnet")
        assert "Valid settings for anthropic:claude-3-5-sonnet:" in help_text
        assert "anthropic_thinking" in help_text
        assert "temperature: Sampling temperature (0-1)" in help_text
        assert "max_tokens" in help_text
        assert "timeout" in help_text
        assert "top_p" in help_text
        # Should not include OpenAI-specific settings
        assert "openai_reasoning_effort" not in help_text

    def test_google_help(self) -> None:
        """Test help text for Google models."""
        help_text = get_valid_settings_help("google:gemini-pro")
        assert "Valid settings for google:gemini-pro:" in help_text
        assert "google_thinking_config" in help_text
        assert "temperature: Sampling temperature (0-1)" in help_text
        assert "max_tokens" in help_text
        assert "timeout" in help_text
        # Should not include provider-specific settings from other providers
        assert "openai_reasoning_effort" not in help_text
        assert "anthropic_thinking" not in help_text

    def test_unknown_provider_help(self) -> None:
        """Test help text for unknown provider."""
        help_text = get_valid_settings_help("custom-model")
        assert "Valid settings for custom-model:" in help_text
        # Should show all general settings
        assert "temperature" in help_text
        assert "max_tokens" in help_text
        assert "timeout" in help_text
        assert "seed" in help_text
        assert "top_p" in help_text
