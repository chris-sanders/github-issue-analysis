"""
MCP (Model Context Protocol) instrumentation for Phoenix tracing.

This module provides comprehensive MCP tool call instrumentation that integrates
seamlessly with Phoenix tracing and OpenInference semantic conventions.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from openinference.semconv.trace import SpanAttributes, ToolCallAttributes
from opentelemetry import trace
from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def instrument_mcp_agent(agent: Agent) -> bool:
    """Instrument an MCP-enabled PydanticAI agent for comprehensive Phoenix tracing.

    Args:
        agent: PydanticAI agent with MCP tools

    Returns:
        True if instrumentation successful, False otherwise
    """
    if not agent:
        return False

    try:
        # Enable PydanticAI's built-in instrumentation
        agent.instrument = True

        # Add MCP-specific tool instrumentation
        _instrument_mcp_tools(agent)

        logger.info(f"✅ MCP instrumentation enabled for agent: {agent.name}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to instrument MCP agent: {e}")
        return False


def _instrument_mcp_tools(agent: Agent) -> None:
    """Add comprehensive MCP tool call instrumentation to an agent.

    Args:
        agent: The agent to instrument
    """
    if not hasattr(agent, "_toolsets") or not agent._toolsets:
        logger.debug("No toolsets found for MCP instrumentation")
        return

    tool_count = 0
    for toolset in agent._toolsets:
        if hasattr(toolset, "_tools") and toolset._tools:
            for tool_name, tool_func in toolset._tools.items():
                # Wrap tool with Phoenix-aware instrumentation
                wrapped = _create_phoenix_tool_wrapper(tool_func, tool_name, agent.name)
                toolset._tools[tool_name] = wrapped
                tool_count += 1

    if tool_count > 0:
        logger.info(f"✅ Instrumented {tool_count} MCP tools for Phoenix tracing")
    else:
        logger.debug("No MCP tools found to instrument")


def _create_phoenix_tool_wrapper(
    tool_func: Callable, tool_name: str, agent_name: str
) -> Callable:
    """Create a Phoenix-aware wrapper for an MCP tool call.

    Args:
        tool_func: Original tool function
        tool_name: Name of the tool
        agent_name: Name of the agent using the tool

    Returns:
        Wrapped tool function with Phoenix instrumentation
    """

    @wraps(tool_func)
    async def phoenix_tool_wrapper(*args, **kwargs):
        tracer = trace.get_tracer(__name__)

        # Create dedicated span for this tool call
        span_name = f"tool_{tool_name}"

        with tracer.start_as_current_span(span_name) as span:
            try:
                # Set OpenInference tool call attributes using proper semantic conventions
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "TOOL")
                span.set_attribute(
                    ToolCallAttributes.TOOL_CALL_FUNCTION_NAME, tool_name
                )

                # Use standard OpenInference attributes that Phoenix recognizes
                span.set_attribute("tool.name", tool_name)  # Standard tool name
                span.set_attribute("agent.name", agent_name)  # Standard agent name
                span.set_attribute("tool.type", "mcp")

                # Add tool arguments (safely) - prioritize key arguments for visibility
                _add_tool_arguments_enhanced(span, args, kwargs, tool_name)

                # Execute the tool with timeout to prevent hanging
                import asyncio

                result = await asyncio.wait_for(
                    tool_func(*args, **kwargs),
                    timeout=120,  # 2 minutes max per MCP tool call
                )

                # Add result information
                _add_tool_result(span, result, tool_name)

                # Mark as successful
                span.set_attribute("tool.status", "success")

                return result

            except TimeoutError as e:
                # Mark as timeout and add timeout info
                span.set_attribute("tool.status", "timeout")
                span.set_attribute("tool.timeout_seconds", 120)
                span.set_attribute(
                    "tool.error", "MCP tool call timed out after 120 seconds"
                )
                span.record_exception(e)
                raise
            except Exception as e:
                # Mark as failed and add error info
                span.set_attribute("tool.status", "error")
                span.set_attribute("tool.error", str(e)[:200])  # Limit error length
                span.record_exception(e)
                raise

    return phoenix_tool_wrapper


def _add_tool_arguments_enhanced(
    span: trace.Span, args: tuple, kwargs: dict, tool_name: str
) -> None:
    """Add tool arguments to span attributes with better Phoenix UI visibility.

    Args:
        span: OpenTelemetry span
        args: Tool positional arguments
        kwargs: Tool keyword arguments
        tool_name: Name of the tool
    """
    try:
        # Use OpenInference semantic conventions for better Phoenix recognition
        span.set_attribute("tool.call.arg_count", len(args))
        span.set_attribute("tool.call.kwarg_count", len(kwargs))

        # Add individual key arguments using semantic conventions
        for key, value in kwargs.items():
            if _is_safe_to_log(key, value):
                if isinstance(value, int | float | bool):
                    span.set_attribute(f"tool.parameter.{key}", value)
                elif isinstance(value, str):
                    # Truncate long strings but make them visible
                    display_value = value[:200] + "..." if len(value) > 200 else value
                    span.set_attribute(f"tool.parameter.{key}", display_value)
                elif isinstance(value, list):
                    span.set_attribute(f"tool.parameter.{key}_count", len(value))

        # Still include the full JSON for complete details (but not prioritized)
        safe_kwargs = {}
        for key, value in kwargs.items():
            if _is_safe_to_log(key, value):
                if isinstance(value, int | float | bool | str):
                    safe_kwargs[key] = (
                        value
                        if isinstance(value, str) and len(value) <= 200
                        else str(value)[:200]
                    )
                elif isinstance(value, list):
                    safe_kwargs[f"{key}_count"] = len(value)

        if safe_kwargs:
            import json

            span.set_attribute(
                ToolCallAttributes.TOOL_CALL_FUNCTION_ARGUMENTS_JSON,
                json.dumps(safe_kwargs, default=str)[:1000],  # Increased limit
            )

    except Exception as e:
        logger.debug(f"Failed to add tool arguments: {e}")


def _add_tool_arguments(
    span: trace.Span, args: tuple, kwargs: dict, tool_name: str
) -> None:
    """Legacy function - calls enhanced version."""
    _add_tool_arguments_enhanced(span, args, kwargs, tool_name)


def _add_tool_result(span: trace.Span, result: Any, tool_name: str) -> None:
    """Add tool result information to span.

    Args:
        span: OpenTelemetry span
        result: Tool execution result
        tool_name: Name of the tool
    """
    try:
        # Add result type
        span.set_attribute(f"tool.{tool_name}.result_type", type(result).__name__)

        # Add result characteristics
        if isinstance(result, str):
            span.set_attribute(f"tool.{tool_name}.result_length", len(result))
            span.set_attribute(
                f"tool.{tool_name}.result_tokens_est", int(len(result) / 3.5)
            )

            # Add truncated result for debugging
            span.set_attribute(
                "tool.result_preview",
                result[:200] + "..." if len(result) > 200 else result,
            )

        elif isinstance(result, list | tuple):
            span.set_attribute(f"tool.{tool_name}.result_items", len(result))

        elif isinstance(result, dict):
            span.set_attribute(f"tool.{tool_name}.result_keys", len(result.keys()))
            # Add key names for structure insight
            key_names = list(result.keys())[:5]  # First 5 keys
            span.set_attribute(f"tool.{tool_name}.result_key_names", key_names)

        elif hasattr(result, "__dict__"):
            span.set_attribute(f"tool.{tool_name}.result_fields", len(result.__dict__))

    except Exception as e:
        logger.debug(f"Failed to add tool result info: {e}")


def _is_safe_to_log(key: str, value: Any) -> bool:
    """Check if a parameter is safe to log (not sensitive).

    Args:
        key: Parameter name
        value: Parameter value

    Returns:
        True if safe to log, False otherwise
    """
    # Skip potentially sensitive keys
    sensitive_keys = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "key",
        "token",
        "auth",
        "credential",
        "private",
        "confidential",
        "api_key",
    }

    key_lower = key.lower()
    if any(sensitive in key_lower for sensitive in sensitive_keys):
        return False

    # Skip very large values
    if isinstance(value, str) and len(value) > 1000:
        return False

    if isinstance(value, list | dict) and len(str(value)) > 1000:
        return False

    return True


def create_mcp_session_span(
    session_name: str, server_info: dict[str, Any] | None = None
) -> trace.Span | None:
    """Create a span to track an MCP session.

    Args:
        session_name: Name/identifier for the MCP session
        server_info: Optional server information

    Returns:
        MCP session span or None if tracing not available
    """
    try:
        tracer = trace.get_tracer(__name__)
        span = tracer.start_as_current_span(f"mcp_session_{session_name}")

        # Set OpenInference attributes
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute("mcp.session.name", session_name)
        span.set_attribute("mcp.session.type", "tool_provider")

        # Add server information if available
        if server_info:
            for key, value in server_info.items():
                if isinstance(value, str | int | float | bool) and key != "password":
                    span.set_attribute(f"mcp.server.{key}", value)

        return span

    except Exception as e:
        logger.warning(f"Failed to create MCP session span: {e}")
        return None


def track_mcp_tool_performance(span: trace.Span, tool_stats: dict[str, Any]) -> None:
    """Track MCP tool performance metrics in a span.

    Args:
        span: Span to annotate with performance data
        tool_stats: Dictionary of tool performance statistics
    """
    if not span or not span.is_recording():
        return

    try:
        # Add performance metrics using standard semantic conventions
        for metric, value in tool_stats.items():
            if isinstance(value, int | float):
                span.set_attribute(f"tool.performance.{metric}", value)

        # Add summary statistics
        if "total_calls" in tool_stats:
            span.set_attribute(
                "tool.performance.summary.total_calls", tool_stats["total_calls"]
            )

        if "avg_duration_ms" in tool_stats:
            span.set_attribute(
                "tool.performance.summary.avg_duration_ms",
                tool_stats["avg_duration_ms"],
            )

    except Exception as e:
        logger.warning(f"Failed to track MCP performance: {e}")


def get_mcp_tool_metrics(agent: Agent) -> dict[str, Any]:
    """Extract MCP tool usage metrics from an agent.

    Args:
        agent: PydanticAI agent with MCP tools

    Returns:
        Dictionary of tool metrics
    """
    metrics = {"total_tools": 0, "tool_names": [], "toolsets": 0}

    try:
        if hasattr(agent, "_toolsets") and agent._toolsets:
            metrics["toolsets"] = len(agent._toolsets)

            for toolset in agent._toolsets:
                if hasattr(toolset, "_tools") and toolset._tools:
                    for tool_name in toolset._tools.keys():
                        metrics["total_tools"] += 1
                        metrics["tool_names"].append(tool_name)

        # Limit tool names list size
        if len(metrics["tool_names"]) > 20:
            metrics["tool_names"] = metrics["tool_names"][:20]

    except Exception as e:
        logger.warning(f"Failed to get MCP tool metrics: {e}")

    return metrics
