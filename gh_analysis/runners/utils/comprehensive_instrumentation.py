"""Comprehensive instrumentation for PydanticAI agents with Phoenix.

This module provides proper tracking of:
- Context size on EVERY span (agent, LLM, tool calls)
- Token usage breakdowns
- Scoring results
- Tool call details
"""

import functools

from opentelemetry import trace
from pydantic_ai import Agent


class ComprehensiveInstrumentation:
    """Properly instrument PydanticAI agents for Phoenix visibility."""

    def __init__(self, agent: Agent, model_max_tokens: int = 200_000):
        """Initialize instrumentation for an agent.

        Args:
            agent: The PydanticAI agent to instrument
            model_max_tokens: Maximum context tokens for the model
        """
        self.agent = agent
        self.max_tokens = model_max_tokens
        self.current_context_size = 0
        self.message_count = 0

    def track_context(self, span: trace.Span | None = None) -> None:
        """Add context tracking to current or provided span.

        This adds context metrics that appear at the TOP of span attributes.
        """
        if span is None:
            span = trace.get_current_span()

        if not span or not span.is_recording():
            return

        # Calculate current context size
        if hasattr(self.agent, "_history") and self.agent._history:
            messages = self.agent._history
            total_chars = sum(len(str(msg)) for msg in messages)
            estimated_tokens = int(total_chars / 3.5)
            self.current_context_size = estimated_tokens
            self.message_count = len(messages)
        else:
            estimated_tokens = self.current_context_size

        usage_pct = round((estimated_tokens / self.max_tokens) * 100, 1)

        # Add at TOP with 0_ prefix (sorts before z_)
        span.set_attribute("0_ctx.tokens", estimated_tokens)
        span.set_attribute("0_ctx.usage%", usage_pct)
        span.set_attribute("0_ctx.messages", self.message_count)

        # Warning if near limit
        if usage_pct > 80:
            span.set_attribute("0_ctx.⚠️_NEAR_LIMIT", True)

    def instrument_agent_run(self):
        """Wrap agent.run() to add comprehensive tracking."""
        original_run = self.agent.run
        agent_self = self

        @functools.wraps(original_run)
        async def instrumented_run(*args, **kwargs):
            span = trace.get_current_span()

            # Track context BEFORE
            tokens_before = agent_self.current_context_size
            agent_self.track_context(span)

            # Run original
            result = await original_run(*args, **kwargs)

            # Track context AFTER and growth
            agent_self.track_context(span)
            tokens_after = agent_self.current_context_size
            growth = tokens_after - tokens_before

            if span and span.is_recording():
                span.set_attribute("0_ctx.growth", growth)

                # Add token usage from result
                if hasattr(result, "usage"):
                    usage = result.usage()
                    if usage:
                        # Add detailed breakdown at TOP
                        if hasattr(usage, "request_tokens"):
                            span.set_attribute("0_tokens.input", usage.request_tokens)
                        if hasattr(usage, "response_tokens"):
                            span.set_attribute("0_tokens.output", usage.response_tokens)
                        if hasattr(usage, "total_tokens"):
                            span.set_attribute("0_tokens.total", usage.total_tokens)

            return result

        self.agent.run = instrumented_run

    def instrument_tool_calls(self):
        """Add context tracking to tool calls."""
        if not hasattr(self.agent, "_toolsets"):
            return

        for toolset in self.agent._toolsets:
            if not hasattr(toolset, "_tools"):
                continue

            for tool_name, tool_def in toolset._tools.items():
                # Get the actual function
                if hasattr(tool_def, "func"):
                    original_func = tool_def.func
                elif callable(tool_def):
                    original_func = tool_def
                else:
                    continue

                agent_self = self

                @functools.wraps(original_func)
                async def instrumented_tool(*args, **kwargs):
                    # Create a span for this tool call
                    tracer = trace.get_tracer(__name__)
                    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                        # Add context tracking
                        agent_self.track_context(span)

                        # Mark as tool
                        span.set_attribute("tool.name", tool_name)
                        span.set_attribute("span.type", "tool_call")

                        # Run tool
                        result = await original_func(*args, **kwargs)

                        # Track result size
                        if isinstance(result, str):
                            span.set_attribute("tool.result_chars", len(result))
                            span.set_attribute(
                                "tool.result_tokens_est", int(len(result) / 3.5)
                            )

                        return result

                # Replace the function
                if hasattr(tool_def, "func"):
                    tool_def.func = instrumented_tool
                else:
                    toolset._tools[tool_name] = instrumented_tool

    def apply_all_instrumentation(self):
        """Apply all instrumentation to the agent."""
        self.instrument_agent_run()
        self.instrument_tool_calls()
        return self.agent


def fully_instrument_agent(agent: Agent, model_max_tokens: int = 200_000) -> Agent:
    """Fully instrument a PydanticAI agent for Phoenix.

    Args:
        agent: The agent to instrument
        model_max_tokens: Max context tokens for the model

    Returns:
        The instrumented agent
    """
    instrumentation = ComprehensiveInstrumentation(agent, model_max_tokens)
    return instrumentation.apply_all_instrumentation()


def add_score_to_span(scores: dict[str, float], span: trace.Span | None = None) -> None:
    """Add scoring results to span in a visible way.

    Args:
        scores: Dictionary of metric_name -> score
        span: The span to add to (current if None)
    """
    if span is None:
        span = trace.get_current_span()

    if not span or not span.is_recording():
        return

    # Add scores at TOP with 0_ prefix
    for metric, score in scores.items():
        span.set_attribute(f"0_score.{metric}", score)

    # Add overall if present
    if "overall" in scores:
        overall = scores["overall"]
        if overall >= 0.8:
            span.set_attribute("0_score.⭐_rating", "Excellent")
        elif overall >= 0.6:
            span.set_attribute("0_score.⭐_rating", "Good")
        else:
            span.set_attribute("0_score.⭐_rating", "Needs Improvement")
