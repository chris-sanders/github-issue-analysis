"""History management utilities for agent conversations."""

from collections.abc import Callable

from pydantic_ai.messages import ModelMessage


def _preserve_tool_pairs(
    messages: list[ModelMessage], target_keep_count: int
) -> list[ModelMessage]:
    """Preserve tool call/tool return pairs when trimming message history.

    This ensures that ToolCallPart and ToolReturnPart blocks are kept together
    to avoid API errors about orphaned tool calls or returns.

    Args:
        messages: List of conversation messages (excluding system message)
        target_keep_count: Target number of messages to keep

    Returns:
        Trimmed messages list with tool pairs preserved
    """
    if len(messages) <= target_keep_count:
        return messages

    # Helper function to check if a message contains tool returns
    def has_tool_returns(msg) -> bool:
        if hasattr(msg, "parts"):
            return any(
                hasattr(part, "part_kind") and part.part_kind == "tool-return"
                for part in msg.parts
            )
        return False

    # Helper function to check if a message contains tool calls
    def has_tool_calls(msg) -> bool:
        if hasattr(msg, "parts"):
            return any(
                hasattr(part, "part_kind") and part.part_kind == "tool-call"
                for part in msg.parts
            )
        return False

    # Start from the end and work backwards, ensuring tool pairs stay together
    keep_messages = []
    i = len(messages) - 1

    while i >= 0 and len(keep_messages) < target_keep_count:
        message = messages[i]

        # Check if this message contains tool returns
        if has_tool_returns(message):
            # This is a tool return message, we need to find its corresponding tool call
            # Look backwards to find the tool call message(s)
            tool_call_found = False
            j = i - 1

            # Keep looking for the corresponding tool call
            while j >= 0 and not tool_call_found:
                if has_tool_calls(messages[j]):
                    tool_call_found = True
                    # Keep both messages as a pair
                    if len(keep_messages) + 2 <= target_keep_count:
                        keep_messages.insert(0, message)  # tool return
                        keep_messages.insert(0, messages[j])  # tool call
                        i = j - 1  # Skip past the tool call we just processed
                    else:
                        # Not enough space for the pair, stop here
                        break
                else:
                    j -= 1

            if not tool_call_found:
                # No matching tool call found, just add this message
                keep_messages.insert(0, message)
                i -= 1
        else:
            # Regular message, just add it
            keep_messages.insert(0, message)
            i -= 1

    return keep_messages


def create_history_trimmer(
    max_tokens: int = 200_000,
    critical_ratio: float = 0.9,
    high_ratio: float = 0.8,
    chars_per_token: float = 3.5,
) -> Callable[[list[ModelMessage]], list[ModelMessage]]:
    """Create a history trimmer function with configurable parameters.

    This creates a function that progressively trims message history to stay
    within token limits while preserving context effectively.

    Args:
        max_tokens: Maximum token limit for the model
        critical_ratio: At what ratio of max_tokens to start aggressive trimming (drop 20%)
        high_ratio: At what ratio of max_tokens to start moderate trimming (drop 10%)
        chars_per_token: Conservative character-to-token ratio for estimation

    Returns:
        A function that takes a list of ModelMessage and returns trimmed list

    Example:
        # For o3 with 200k context
        o3_trimmer = create_history_trimmer(max_tokens=200_000)

        # For Gemini with 1M context (more generous thresholds)
        gemini_trimmer = create_history_trimmer(
            max_tokens=1_000_000,
            critical_ratio=0.95,
            high_ratio=0.9
        )

        # Use in Agent
        agent = Agent(
            model=model,
            history_processors=[o3_trimmer],
            ...
        )
    """
    critical_threshold = int(max_tokens * critical_ratio)
    high_threshold = int(max_tokens * high_ratio)

    def history_trimmer(messages: list[ModelMessage]) -> list[ModelMessage]:
        """Trim message history based on configured thresholds."""
        # Conservative token estimation
        total_chars = sum(len(str(msg)) for msg in messages)
        estimated_tokens = total_chars / chars_per_token

        # Track truncation for observability
        from opentelemetry import trace

        current_span = trace.get_current_span()

        if current_span and current_span.is_recording():
            # Add SIMPLIFIED context metrics at TOP with z_ prefix
            usage_pct = round((estimated_tokens / max_tokens) * 100, 1)

            # These appear at the TOP of any span (agent or tool call)
            current_span.set_attribute("z_ctx.tokens", int(estimated_tokens))
            current_span.set_attribute("z_ctx.usage_pct", usage_pct)
            current_span.set_attribute("z_ctx.msgs", len(messages))

            # Detailed metrics with normal prefix
            current_span.set_attribute(
                "context.estimated_tokens", int(estimated_tokens)
            )
            current_span.set_attribute("context.total_chars", total_chars)
            current_span.set_attribute("context.message_count", len(messages))
            current_span.set_attribute("context.max_tokens", max_tokens)
            current_span.set_attribute(
                "context.usage_ratio", estimated_tokens / max_tokens
            )

        # Never drop the system message (instructions) or if too few messages
        if len(messages) <= 5:
            return messages

        system_msg = messages[0]
        conversation = messages[1:]

        if estimated_tokens > critical_threshold:
            # Critical - drop oldest 20%
            keep_count = max(3, int(len(conversation) * 0.8))
            trimmed_conversation = _preserve_tool_pairs(conversation, keep_count)

            if current_span:
                current_span.set_attribute("context.truncation_triggered", True)
                current_span.set_attribute("context.truncation_level", "critical")
                current_span.set_attribute(
                    "context.messages_dropped",
                    len(conversation) - len(trimmed_conversation),
                )
                current_span.set_attribute(
                    "context.messages_kept", len(trimmed_conversation)
                )

            return [system_msg] + trimmed_conversation
        elif estimated_tokens > high_threshold:
            # High - drop oldest 10%
            keep_count = max(4, int(len(conversation) * 0.9))
            trimmed_conversation = _preserve_tool_pairs(conversation, keep_count)

            if current_span:
                current_span.set_attribute("context.truncation_triggered", True)
                current_span.set_attribute("context.truncation_level", "high")
                current_span.set_attribute(
                    "context.messages_dropped",
                    len(conversation) - len(trimmed_conversation),
                )
                current_span.set_attribute(
                    "context.messages_kept", len(trimmed_conversation)
                )

            return [system_msg] + trimmed_conversation

        if current_span:
            current_span.set_attribute("context.truncation_triggered", False)

        return messages

    return history_trimmer
