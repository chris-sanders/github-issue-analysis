"""Context tracking utilities for Phoenix tracing using OpenInference conventions."""

from opentelemetry import trace
from typing import Optional, List, Dict, Any
from openinference.semconv.trace import SpanAttributes, MessageAttributes


def add_context_attributes(
    span: Optional[trace.Span] = None,
    prefix: str = "context",
    message_count: Optional[int] = None,
    total_chars: Optional[int] = None,
    estimated_tokens: Optional[int] = None,
    max_tokens: int = 200_000,
) -> None:
    """Add context tracking attributes to a span using OpenInference conventions.

    Args:
        span: The span to add attributes to (uses current if None)
        prefix: Prefix for attribute names (e.g., "context" or "tool_context")
        message_count: Number of messages in context
        total_chars: Total characters in context
        estimated_tokens: Estimated token count
        max_tokens: Maximum token limit for the model
    """
    if span is None:
        span = trace.get_current_span()

    if not span or not span.is_recording():
        return

    # Use OpenInference semantic conventions where appropriate
    if message_count is not None:
        if prefix == "context":
            # Use standard OpenInference attribute for message count
            span.set_attribute("llm.conversation.message_count", message_count)
        else:
            span.set_attribute(f"{prefix}.message_count", message_count)

    if total_chars is not None:
        span.set_attribute(f"{prefix}.total_chars", total_chars)

        # Auto-calculate estimated tokens if not provided
        if estimated_tokens is None:
            estimated_tokens = int(total_chars / 3.5)

    if estimated_tokens is not None:
        # Use OpenInference token counting conventions
        if prefix == "context":
            span.set_attribute(SpanAttributes.LLM_TOKEN_COUNT_PROMPT, estimated_tokens)
        else:
            span.set_attribute(f"{prefix}.estimated_tokens", estimated_tokens)

        # Calculate usage ratio with standard semantic conventions
        usage_ratio = estimated_tokens / max_tokens
        span.set_attribute(f"{prefix}.usage_percent", round(usage_ratio * 100, 1))
        span.set_attribute(f"{prefix}.near_limit", usage_ratio > 0.8)
        span.set_attribute(f"{prefix}.max_tokens", max_tokens)


def track_context_growth(
    before_chars: int,
    after_chars: int,
    span: Optional[trace.Span] = None,
    prefix: str = "context",
) -> None:
    """Track context growth between before and after states.

    Args:
        before_chars: Character count before operation
        after_chars: Character count after operation
        span: The span to add attributes to (uses current if None)
        prefix: Prefix for attribute names
    """
    if span is None:
        span = trace.get_current_span()

    if not span or not span.is_recording():
        return

    chars_growth = after_chars - before_chars
    tokens_growth = int(chars_growth / 3.5)

    span.set_attribute(f"{prefix}.chars_growth", chars_growth)
    span.set_attribute(f"{prefix}.tokens_growth", tokens_growth)

    # Add growth percentage if significant
    if before_chars > 0:
        growth_pct = (chars_growth / before_chars) * 100
        span.set_attribute(f"{prefix}.growth_percent", round(growth_pct, 1))


def get_model_max_tokens(model_name: str) -> int:
    """Get the maximum token limit for a model.

    Args:
        model_name: The model class name or identifier

    Returns:
        Maximum token limit for the model
    """
    if "Gemini" in model_name:
        return 1_000_000
    elif "Claude" in model_name:
        return 200_000
    elif "GPT5" in model_name or "GPT-5" in model_name:
        return 400_000
    elif "GPT4" in model_name or "GPT-4" in model_name:
        return 128_000
    else:
        return 200_000  # Conservative default


def add_message_history_to_span(
    span: trace.Span, messages: List[Dict[str, Any]], max_messages: int = 10
) -> None:
    """Add message history to span using OpenInference semantic conventions.

    Args:
        span: The span to annotate
        messages: List of message dictionaries with role and content
        max_messages: Maximum number of messages to include (for span size)
    """
    if not span or not span.is_recording():
        return

    try:
        # Limit messages to avoid span size issues
        messages_to_include = (
            messages[-max_messages:] if len(messages) > max_messages else messages
        )

        for i, msg in enumerate(messages_to_include):
            # Use OpenInference message semantic conventions
            span.set_attribute(
                f"{MessageAttributes.MESSAGE_ROLE}.{i}", msg.get("role", "unknown")
            )

            # Truncate content for span attributes
            content = str(msg.get("content", ""))[:500]  # Limit to 500 chars
            span.set_attribute(f"{MessageAttributes.MESSAGE_CONTENT}.{i}", content)

        # Add summary statistics
        span.set_attribute("llm.conversation.total_messages", len(messages))
        span.set_attribute(
            "llm.conversation.included_messages", len(messages_to_include)
        )

        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        span.set_attribute("llm.conversation.total_chars", total_chars)

    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to add message history: {e}")


def track_tool_usage(span: trace.Span, tool_calls: List[Dict[str, Any]]) -> None:
    """Track tool usage in a span using OpenInference conventions.

    Args:
        span: The span to annotate
        tool_calls: List of tool call information
    """
    if not span or not span.is_recording() or not tool_calls:
        return

    try:
        # Add tool usage summary
        span.set_attribute("tools.total_calls", len(tool_calls))

        # Count calls by tool type
        tool_counts = {}
        for call in tool_calls:
            tool_name = call.get("name", "unknown")
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # Add individual tool counts
        for tool_name, count in tool_counts.items():
            span.set_attribute(f"tools.{tool_name}.count", count)

        # Add tool types used
        span.set_attribute(
            "tools.types_used", list(tool_counts.keys())[:5]
        )  # Limit to 5
        span.set_attribute("tools.unique_types", len(tool_counts))

    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to track tool usage: {e}")


def create_context_summary_span(
    name: str, agent_name: str, context_data: Dict[str, Any]
) -> Optional[trace.Span]:
    """Create a dedicated context summary span for better Phoenix visibility.

    Args:
        name: Span name
        agent_name: Name of the agent
        context_data: Context information to include

    Returns:
        Context span or None if tracing not available
    """
    try:
        tracer = trace.get_tracer(__name__)
        span = tracer.start_as_current_span(f"context_{name}")

        # Set OpenInference attributes
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("context.type", "summary")

        # Add context data
        for key, value in context_data.items():
            if isinstance(value, (int, float, str, bool)):
                span.set_attribute(f"context.{key}", value)
            elif isinstance(value, list):
                span.set_attribute(f"context.{key}.count", len(value))
                # Add first few items if they're simple types
                for i, item in enumerate(value[:3]):
                    if isinstance(item, str) and len(item) < 100:
                        span.set_attribute(f"context.{key}.{i}", item)

        return span

    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Failed to create context span: {e}")
        return None
