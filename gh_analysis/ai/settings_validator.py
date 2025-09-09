"""Validation for PydanticAI model settings.

This module provides validation for settings passed to PydanticAI models,
ensuring they are valid before processing begins.
"""

from typing import Any

VALID_PYDANTIC_SETTINGS = {
    "temperature",
    "max_tokens",
    "timeout",
    "seed",
    "top_p",
    "openai_reasoning_effort",
    "openai_reasoning_summary",
    "anthropic_thinking",
    "google_thinking_config",
}

MODEL_SPECIFIC_SETTINGS = {
    "openai": {
        "openai_reasoning_effort",
        "openai_reasoning_summary",
        "temperature",
        "max_tokens",
        "timeout",
        "seed",
        "top_p",
    },
    "anthropic": {
        "anthropic_thinking",
        "temperature",
        "max_tokens",
        "timeout",
        "top_p",
    },
    "google": {"google_thinking_config", "temperature", "max_tokens", "timeout"},
}


def get_provider_from_model(model: str) -> str:
    """Extract provider from model string.

    Args:
        model: Model string (e.g., 'openai:o4-mini', 'anthropic:claude-3-5-sonnet')

    Returns:
        Provider name (e.g., 'openai', 'anthropic', 'google')
    """
    if ":" in model:
        return model.split(":")[0]
    return "unknown"


def validate_settings(model: str, settings: dict[str, Any]) -> list[str]:
    """Validate settings for the given model.

    Args:
        model: Model string (e.g., 'openai:o4-mini')
        settings: Dictionary of settings to validate

    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    provider = get_provider_from_model(model)

    # Get valid settings for this provider
    valid_settings = MODEL_SPECIFIC_SETTINGS.get(provider, VALID_PYDANTIC_SETTINGS)

    for key, value in settings.items():
        # Check if setting exists in PydanticAI
        if key not in VALID_PYDANTIC_SETTINGS:
            errors.append(f"Unknown setting '{key}' - not recognized by PydanticAI")

        # Check if setting is valid for this model
        elif key not in valid_settings:
            errors.append(f"Setting '{key}' is not supported by {provider} models")

        # Check value types/ranges
        elif key == "temperature":
            try:
                temp = float(value)
                if provider == "openai" and not 0 <= temp <= 2:
                    errors.append(f"Temperature {temp} out of range for OpenAI (0-2)")
                elif provider in ["anthropic", "google"] and not 0 <= temp <= 1:
                    errors.append(
                        f"Temperature {temp} out of range for {provider} (0-1)"
                    )
            except ValueError:
                errors.append(f"Temperature must be a number, got '{value}'")

        elif key == "max_tokens":
            try:
                tokens = int(value)
                if tokens <= 0:
                    errors.append(f"max_tokens must be positive, got {tokens}")
            except ValueError:
                errors.append(f"max_tokens must be an integer, got '{value}'")

        elif key == "timeout":
            try:
                timeout = float(value)
                if timeout <= 0:
                    errors.append(f"timeout must be positive, got {timeout}")
            except ValueError:
                errors.append(f"timeout must be a number, got '{value}'")

        elif key == "seed":
            try:
                int(value)
            except ValueError:
                errors.append(f"seed must be an integer, got '{value}'")

        elif key == "top_p":
            try:
                top_p = float(value)
                if not 0 <= top_p <= 1:
                    errors.append(f"top_p must be between 0 and 1, got {top_p}")
            except ValueError:
                errors.append(f"top_p must be a number, got '{value}'")

        elif key == "openai_reasoning_effort":
            if value not in ["low", "medium", "high"]:
                errors.append(
                    f"openai_reasoning_effort must be 'low', 'medium', "
                    f"or 'high', got '{value}'"
                )

    return errors


def get_valid_settings_help(model: str) -> str:
    """Get help text showing valid settings for a model.

    Args:
        model: Model string (e.g., 'openai:o4-mini')

    Returns:
        Formatted help text showing valid settings
    """
    provider = get_provider_from_model(model)
    valid_settings = MODEL_SPECIFIC_SETTINGS.get(provider, VALID_PYDANTIC_SETTINGS)

    help_text = f"Valid settings for {model}:\n"

    # Add provider-specific help
    if provider == "openai":
        if "openai_reasoning_effort" in valid_settings:
            help_text += (
                "  • openai_reasoning_effort: Thinking effort (low, medium, high)\n"
            )
        if "openai_reasoning_summary" in valid_settings:
            help_text += (
                "  • openai_reasoning_summary: Include reasoning summary in response\n"
            )

    elif provider == "anthropic":
        if "anthropic_thinking" in valid_settings:
            help_text += (
                "  • anthropic_thinking: Enable thinking mode for Anthropic models\n"
            )

    elif provider == "google":
        if "google_thinking_config" in valid_settings:
            help_text += (
                "  • google_thinking_config: Configure thinking for Google models\n"
            )

    # Add common settings
    if "temperature" in valid_settings:
        range_text = "(0-2)" if provider == "openai" else "(0-1)"
        help_text += f"  • temperature: Sampling temperature {range_text}\n"
    if "max_tokens" in valid_settings:
        help_text += "  • max_tokens: Maximum tokens to generate\n"
    if "timeout" in valid_settings:
        help_text += "  • timeout: Request timeout in seconds\n"
    if "seed" in valid_settings:
        help_text += "  • seed: Random seed for reproducibility\n"
    if "top_p" in valid_settings:
        help_text += "  • top_p: Nucleus sampling parameter (0-1)\n"

    return help_text
