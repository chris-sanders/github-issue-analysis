"""Minimal compatibility classes for batch system only."""

from typing import Any

from pydantic import BaseModel


class AIModelConfig(BaseModel):
    """Minimal compatibility class for batch system."""

    model: str = "openai:gpt-4o"
    model_name: str = "openai:gpt-4o"  # Alias for compatibility
    thinking_effort: str | None = None
    thinking_budget: int | None = None
    temperature: float = 0.0
    include_images: bool = True

    def __init__(self, **kwargs: Any) -> None:
        # Ensure model_name and model are synchronized
        if "model" in kwargs and "model_name" not in kwargs:
            kwargs["model_name"] = kwargs["model"]
        elif "model_name" in kwargs and "model" not in kwargs:
            kwargs["model"] = kwargs["model_name"]
        super().__init__(**kwargs)


def build_ai_config(
    model_name: str = "openai:gpt-4o",
    thinking_effort: str | None = None,
    thinking_budget: int | None = None,
    temperature: float = 0.0,
) -> AIModelConfig:
    """Minimal compatibility function for batch system."""
    return AIModelConfig(
        model=model_name,
        thinking_effort=thinking_effort,
        thinking_budget=thinking_budget,
        temperature=temperature,
    )


def build_provider_specific_settings(config: AIModelConfig) -> dict[str, Any]:
    """Minimal compatibility function for batch system."""
    settings: dict[str, Any] = {
        "temperature": config.temperature,
    }

    # Pass through thinking settings without model detection
    if config.thinking_effort:
        settings["reasoning_effort"] = config.thinking_effort

    return settings
