"""Base class for agent runners with common execution logic."""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

# Default timeout for agent execution (can be overridden)
AGENT_EXECUTION_TIMEOUT = 1920  # 32 minutes (30 min LLM timeout + 2 min buffer)

T = TypeVar("T", bound=BaseModel)


class BaseAgentRunner(ABC):
    """Generic base class for agent runners.

    Contains all the execution logic including:
    - Retry logic for MALFORMED_FUNCTION_CALL errors
    - MCP server lifecycle management
    - Logging setup and error handling

    Subclasses must implement:
    - _build_context: Convert input data to string context
    - agent configuration
    """

    def __init__(self, name: str, agent: Agent, experiment_name: str = "experiment"):
        self.name = name
        self.agent = agent
        self.experiment_name = experiment_name
        self._last_span_id = None  # For Phoenix SpanEvaluations

        # Apply patches based on the model type being used
        self._apply_model_specific_patches()

    def get_last_span_id(self) -> str | None:
        """Get the span ID from the last execution (Phoenix backend only)."""
        return self._last_span_id

    def get_model_info(self) -> str:
        """Get model information for this runner."""
        if self.agent and hasattr(self.agent, "model"):
            model = self.agent.model
            # Extract model name using existing logic (similar to lines 278-290 in Phoenix span method)
            if hasattr(model, "model_name"):
                return model.model_name
            elif hasattr(model, "_model_name"):
                return model._model_name
            elif hasattr(model, "name"):
                return model.name
            else:
                # For OpenAI models, try to extract from string representation
                model_str = str(model)
                if "gpt-5-mini" in model_str:
                    return "gpt-5-mini"
                elif "gpt-5" in model_str:
                    return "gpt-5"
                elif "claude" in model_str.lower():
                    return "claude"
                else:
                    return f"unknown-{model.__class__.__name__}"
        return "unknown"

    async def analyze(self, input_data) -> T:
        """Execute analysis with full error handling and retry logic.

        Args:
            input_data: Raw input data (format depends on subclass)

        Returns:
            Structured analysis result using the Agent's configured output_type
        """
        run_id = f"{self.name}-{self._get_logging_id(input_data)}"
        print(f"🤖 Starting {self.name} run: {run_id}...")

        # Set up logging
        logger = self._setup_logging(run_id)
        logger.info(f"Starting {self.name} run")

        # Build context (subclass-specific)
        context = self._build_context(input_data)
        logger.info(f"Context size: {len(context)} chars")

        try:
            logger.info("Using pre-configured agent with MCP toolsets")

            async with self.agent:
                logger.info("MCP server connections established")

                user_message = self._build_user_message(context)
                logger.info(f"User message size: {len(user_message)} chars")
                logger.info("Starting agent.run()")

                max_retries = 2
                retry_count = 0

                while retry_count <= max_retries:
                    try:
                        # Wrap agent.run() with custom span naming for better Phoenix tracing
                        result_data = await self._run_agent_with_custom_span(
                            user_message, UsageLimits(request_limit=150)
                        )

                        # Handle Phoenix backend returning (result, span_id) tuple
                        import os

                        backend = os.getenv("TRACING_BACKEND", "file").lower()
                        if backend == "phoenix" and isinstance(result_data, tuple):
                            result, self._last_span_id = result_data
                        else:
                            result = result_data
                            self._last_span_id = None

                        logger.info("Run completed successfully")
                        break
                    except Exception as e:
                        # Log detailed exception information including TaskGroup errors
                        logger.error(f"Exception caught: {type(e).__name__}: {str(e)}")

                        # Check for TaskGroup errors and try to extract the underlying exception
                        if "TaskGroup" in str(e):
                            logger.error(
                                "TaskGroup error detected - attempting to extract underlying exceptions"
                            )
                            # Try to get the underlying exception from TaskGroup
                            if hasattr(e, "__cause__") and e.__cause__:
                                logger.error(
                                    f"Underlying cause: {type(e.__cause__).__name__}: {e.__cause__}"
                                )
                            if hasattr(e, "__context__") and e.__context__:
                                logger.error(
                                    f"Exception context: {type(e.__context__).__name__}: {e.__context__}"
                                )
                            if hasattr(e, "exceptions"):
                                logger.error(
                                    f"TaskGroup exceptions: {[str(ex) for ex in e.exceptions]}"
                                )
                            # For TaskGroup, also try to access the task exceptions
                            try:
                                import asyncio

                                if isinstance(e, asyncio.exceptions.ExceptionGroup):
                                    logger.error(
                                        f"ExceptionGroup with {len(e.exceptions)} exceptions:"
                                    )
                                    for i, ex in enumerate(e.exceptions):
                                        logger.error(
                                            f"  Exception {i}: {type(ex).__name__}: {ex}"
                                        )
                            except Exception as extract_error:
                                logger.error(
                                    f"Failed to extract TaskGroup exceptions: {extract_error}"
                                )

                        if (
                            "MALFORMED_FUNCTION_CALL" in str(e)
                            and retry_count < max_retries
                        ):
                            retry_count += 1
                            logger.warning(
                                f"Retry {retry_count}: Gemini returned malformed function call, retrying..."
                            )
                            continue
                        else:
                            raise e

                # Log message history info
                if hasattr(result, "_message_history") or hasattr(result, "messages"):
                    messages = getattr(
                        result, "_message_history", getattr(result, "messages", [])
                    )
                    total_chars = sum(len(str(msg)) for msg in messages)
                    logger.info(
                        f"Final message history size: {total_chars:,} chars across {len(messages)} messages"
                    )

            logger.info("MCP server connections closed")
            return result.output

        except Exception as e:
            error_msg = f"{self.name} run failed: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full exception details:")

            if "context_length_exceeded" in str(e):
                logger.error(
                    "Context limit exceeded - agent made too many tool calls or "
                    "tools returned too much data. Consider using stricter limits "
                    "on grep_files and list_files."
                )

            raise RuntimeError(error_msg) from e

    @abstractmethod
    def _build_context(self, input_data) -> str:
        """Build context string from input data. Subclasses must implement."""
        pass

    def _get_logging_id(self, input_data) -> str:
        """Extract identifier from input data for logging purposes. Override for custom IDs."""
        return "task"

    def _build_user_message(self, context: str) -> str:
        """Build user message from context. Override for domain-specific formatting."""
        return context

    def _setup_logging(self, run_id: str):
        """Set up run-specific logging."""
        log_file = Path(
            f"data/results/{self.experiment_name}/execution/{run_id}_{self.name}.log"
        )
        log_file.parent.mkdir(parents=True, exist_ok=True)

        logger = logging.getLogger(f"{self.name}_{run_id}")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        return logger

    def _apply_model_specific_patches(self):
        """Apply patches only for the model type this agent uses.

        PATCHES CURRENTLY APPLIED:
        - GeminiModel: MALFORMED_FUNCTION_CALL handling + _auth initialization
        - OpenAIResponsesModel: Tool call ID synchronization with Chat Completions API

        This ensures we only apply patches needed for the specific model,
        avoiding unnecessary modifications to unused model classes.
        """
        if self.agent is None:
            # Skip patches for SDK-based runners that don't use PydanticAI agents
            return

        model = self.agent.model
        model_type = type(model).__name__

        if model_type == "GeminiModel":
            from .gemini_patches import apply_gemini_patches

            apply_gemini_patches()

        elif model_type == "OpenAIResponsesModel":
            self._apply_openai_responses_patch()

    def _apply_openai_responses_patch(self):
        """Apply OpenAI Responses API tool call ID synchronization patch.

        Fixes inconsistency between Chat Completions and Responses API tool call handling
        by applying the same guard_tool_call_id logic to Responses API.
        """
        from pydantic_ai._utils import guard_tool_call_id as _guard_tool_call_id
        from pydantic_ai.messages import ToolCallPart
        from pydantic_ai.models.openai import OpenAIResponsesModel

        original_process_response = OpenAIResponsesModel._process_response

        def patched_process_response(self, response):
            """Patched version that applies guard_tool_call_id like Chat Completions API does."""
            result = original_process_response(self, response)

            # Apply guard_tool_call_id to all ToolCallPart items for consistency
            for item in result.parts:
                if isinstance(item, ToolCallPart):
                    item.tool_call_id = _guard_tool_call_id(item)

            return result

        OpenAIResponsesModel._process_response = patched_process_response

    async def _run_agent_with_custom_span(self, user_message: str, usage_limits):
        """Run agent with custom span naming for Phoenix and run naming for MLflow."""
        import os

        backend = os.getenv("TRACING_BACKEND", "file").lower()

        if backend == "mlflow":
            return await self._run_agent_with_mlflow_naming(user_message, usage_limits)
        elif backend == "phoenix":
            # Phoenix returns (result, span_id)
            return await self._run_agent_with_phoenix_span(user_message, usage_limits)
        else:
            # File backend uses Phoenix span method but we only need the result
            result_and_span = await self._run_agent_with_phoenix_span(
                user_message, usage_limits
            )
            return result_and_span[0]  # Return just the result for file backend

    async def _run_agent_with_phoenix_span(self, user_message: str, usage_limits):
        """Run agent with enhanced OpenTelemetry span for Phoenix tracing."""
        from openinference.semconv.trace import SpanAttributes
        from opentelemetry import trace

        # Import new Phoenix integration utilities
        try:
            from .context_tracking import (
                add_message_history_to_span,
            )
            from .mcp_instrumentation import (
                get_mcp_tool_metrics,
                instrument_mcp_agent,
            )

            phoenix_integration_available = True
        except ImportError:
            phoenix_integration_available = False

        tracer = trace.get_tracer(__name__)
        span_name = f"{self.name.replace(' ', '_').lower()}"

        # Instrument MCP agent if Phoenix integration is available
        if phoenix_integration_available and self.agent:
            instrument_mcp_agent(self.agent)

            # Get MCP tool metrics for span annotations
            mcp_metrics = get_mcp_tool_metrics(self.agent)

        with tracer.start_as_current_span(span_name) as span:
            # Capture span ID for Phoenix SpanEvaluations
            span_id_int = span.get_span_context().span_id
            span_id_hex = format(span_id_int, "016x")

            # Set comprehensive attributes using OpenInference semantic conventions
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")

            # Extract detailed model information
            model_info = "unknown"
            model_class = "unknown"
            if hasattr(self.agent, "model"):
                model_class = self.agent.model.__class__.__name__
                # Try to get more specific model info
                if hasattr(self.agent.model, "model_name"):
                    model_info = self.agent.model.model_name
                elif hasattr(self.agent.model, "_model_name"):
                    model_info = self.agent.model._model_name
                elif hasattr(self.agent.model, "name"):
                    model_info = self.agent.model.name
                else:
                    model_info = model_class

            # Use proper OpenInference semantic conventions that Phoenix understands
            span.set_attribute("agent.name", self.name)
            span.set_attribute("agent.type", "agent")
            span.set_attribute(SpanAttributes.LLM_MODEL_NAME, model_info)
            span.set_attribute("llm.model.class", model_class)
            span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "text/plain")
            span.set_attribute("input.message_length", len(user_message))

            # Add MCP tool information to span
            if phoenix_integration_available and "mcp_metrics" in locals():
                for key, value in mcp_metrics.items():
                    if isinstance(value, int | float | str | bool):
                        span.set_attribute(f"mcp.{key}", value)
                    elif isinstance(value, list) and len(value) <= 10:
                        # Add list items for small lists
                        for i, item in enumerate(value):
                            if isinstance(item, str):
                                span.set_attribute(f"mcp.{key}.{i}", item)

            # Add input message as proper OpenInference attribute
            span.set_attribute(
                SpanAttributes.INPUT_VALUE, user_message[:1000]
            )  # First 1000 chars

            # Import context tracking utilities
            from .context_tracking import (
                add_context_attributes,
                get_model_max_tokens,
                track_context_growth,
            )

            try:
                # Track context size before running
                total_chars_before = 0
                if hasattr(self.agent, "_history") and self.agent._history:
                    total_chars_before = sum(
                        len(str(msg)) for msg in self.agent._history
                    )
                    message_count = len(self.agent._history)

                    # Get model-specific token limit
                    model_name = ""
                    if hasattr(self.agent, "model") and hasattr(
                        self.agent.model, "__class__"
                    ):
                        model_name = self.agent.model.__class__.__name__
                    max_tokens = get_model_max_tokens(model_name)

                    # Add context attributes with standard semantic conventions
                    estimated_tokens = int(total_chars_before / 3.5)
                    usage_ratio = estimated_tokens / max_tokens

                    # Use proper OpenInference semantic conventions
                    span.set_attribute("context.estimated_tokens", estimated_tokens)
                    span.set_attribute(
                        "context.usage_percent", round(usage_ratio * 100, 1)
                    )
                    span.set_attribute("context.near_limit", usage_ratio > 0.8)
                    span.set_attribute("context.message_count", message_count)

                    # Add detailed tracking with normal prefix
                    add_context_attributes(
                        span=span,
                        message_count=message_count,
                        total_chars=total_chars_before,
                        max_tokens=max_tokens,
                    )

                result = await asyncio.wait_for(
                    self.agent.run(user_message, usage_limits=usage_limits),
                    timeout=AGENT_EXECUTION_TIMEOUT,  # 32 minutes
                )

                # Track context size after running
                if hasattr(self.agent, "_history") and self.agent._history:
                    total_chars_after = sum(
                        len(str(msg)) for msg in self.agent._history
                    )
                    message_count_after = len(self.agent._history)

                    # Add after metrics and growth
                    add_context_attributes(
                        span=span,
                        prefix="context_after",
                        message_count=message_count_after,
                        total_chars=total_chars_after,
                        max_tokens=max_tokens if "max_tokens" in locals() else 200_000,
                    )

                    # Track growth
                    if total_chars_before > 0:
                        track_context_growth(
                            before_chars=total_chars_before,
                            after_chars=total_chars_after,
                            span=span,
                        )

                        # Add top-level growth summary
                        tokens_growth = int(
                            (total_chars_after - total_chars_before) / 3.5
                        )
                        span.set_attribute(
                            "context.tokens_added_this_call", tokens_growth
                        )

                # Set success status using OpenTelemetry standard with priority visibility
                from opentelemetry.trace import Status, StatusCode

                span.set_status(Status(StatusCode.OK))
                span.set_attribute("agent.execution.status", "success")
                span.set_attribute("execution.outcome", "SUCCESS")

                # Add result attributes
                if hasattr(result, "output"):
                    span.set_attribute("result.type", type(result.output).__name__)

                    # Add output value for Phoenix
                    if isinstance(result.output, str):
                        span.set_attribute(
                            SpanAttributes.OUTPUT_VALUE, result.output[:1000]
                        )
                    else:
                        span.set_attribute(
                            SpanAttributes.OUTPUT_VALUE, str(result.output)[:1000]
                        )

                # Add comprehensive token usage metrics
                if hasattr(result, "usage"):
                    usage = result.usage()
                    if usage:
                        # Standard OpenInference attributes for token counts
                        if hasattr(usage, "total_tokens"):
                            span.set_attribute(
                                SpanAttributes.LLM_TOKEN_COUNT_TOTAL, usage.total_tokens
                            )

                        if hasattr(usage, "request_tokens"):
                            span.set_attribute(
                                SpanAttributes.LLM_TOKEN_COUNT_PROMPT,
                                usage.request_tokens,
                            )
                        elif hasattr(usage, "input_tokens"):
                            span.set_attribute(
                                SpanAttributes.LLM_TOKEN_COUNT_PROMPT,
                                usage.input_tokens,
                            )

                        if hasattr(usage, "response_tokens"):
                            span.set_attribute(
                                SpanAttributes.LLM_TOKEN_COUNT_COMPLETION,
                                usage.response_tokens,
                            )
                        elif hasattr(usage, "output_tokens"):
                            span.set_attribute(
                                SpanAttributes.LLM_TOKEN_COUNT_COMPLETION,
                                usage.output_tokens,
                            )

                # Add output metrics
                if isinstance(result.output, str):
                    span.set_attribute("output.length", len(result.output))
                    span.set_attribute("output.word_count", len(result.output.split()))
                elif hasattr(result.output, "__dict__"):
                    # Log structured output fields
                    try:
                        for key, value in result.output.__dict__.items():
                            if isinstance(value, int | float):
                                span.set_attribute(f"output.{key}", value)
                            elif isinstance(value, str) and len(value) < 100:
                                span.set_attribute(f"output.{key}", value)
                            elif isinstance(value, list):
                                span.set_attribute(f"output.{key}.count", len(value))
                    except Exception:
                        pass

                # Add message history if available
                if phoenix_integration_available and hasattr(
                    result, "_message_history"
                ):
                    messages = [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": str(result.output)},
                    ]
                    add_message_history_to_span(span, messages, max_messages=5)

            except Exception as e:
                # Set error status using OpenTelemetry standard with priority visibility
                from opentelemetry.trace import Status, StatusCode

                span.set_status(Status(StatusCode.ERROR, str(e)[:200]))
                span.set_attribute("agent.execution.status", "error")
                span.set_attribute("execution.outcome", "ERROR")
                span.set_attribute("agent.execution.error", str(e)[:200])
                span.record_exception(e)
                raise

            # Return both result and span ID for Phoenix SpanEvaluations
            return (result, span_id_hex)

    async def _run_agent_with_mlflow_naming(self, user_message: str, usage_limits):
        """Run agent with child run for metrics while master collects traces."""
        import os
        import time

        import mlflow
        from mlflow import MlflowClient

        # Create a clean run name
        run_name = self.name.replace(" ", "_").replace("(", "").replace(")", "").lower()

        start_time = time.time()

        # Get the master run ID that was created in setup_tracing
        master_run_id = os.environ.get("MLFLOW_MASTER_RUN_ID")

        if not master_run_id:
            # Fallback: No master means we're not in MLflow mode properly
            print(f"⚠️ No master run found for {self.name}")
            # Just run without MLflow tracking
            result = await asyncio.wait_for(
                self.agent.run(user_message, usage_limits=usage_limits),
                timeout=AGENT_EXECUTION_TIMEOUT,  # 32 minutes
            )
            return result

        # Create a child run using MlflowClient (doesn't change active run)
        client = MlflowClient()
        active_run = mlflow.active_run()

        child_run = client.create_run(
            experiment_id=active_run.info.experiment_id,
            run_name=run_name,
            tags={
                "mlflow.parentRunId": master_run_id,
                "agent.name": self.name,
                "agent.family": self.name.split()[0].lower(),
                "message.length": str(len(user_message)),
            },
        )

        child_run_id = child_run.info.run_id

        try:
            import mlflow
            from mlflow import MlflowClient

            # No need to track traces - custom naming handles identification

            # Create wrapper with custom trace name
            @mlflow.trace(name=self.name)
            async def run_agent_with_custom_trace_name():
                return await asyncio.wait_for(
                    self.agent.run(user_message, usage_limits=usage_limits),
                    timeout=AGENT_EXECUTION_TIMEOUT,  # 32 minutes
                )

            # Run the agent with custom trace name
            result = await run_agent_with_custom_trace_name()

            # Trace naming is handled by the @mlflow.trace decorator
            print(f"✅ Completed {self.name} with custom trace name")

            execution_time = time.time() - start_time
            mlflow.set_tag(
                f"agent.{self.name}.execution_time", f"{execution_time:.2f}s"
            )

            # Log metrics to the CHILD run for this specific agent
            client.log_metric(child_run_id, "execution_time_seconds", execution_time)
            client.set_tag(child_run_id, "status", "success")

            # Log result metadata to child run
            if hasattr(result, "output"):
                client.set_tag(
                    child_run_id, "result.type", type(result.output).__name__
                )

                # Log token usage if available
                if hasattr(result, "usage"):
                    usage = result.usage()  # Call the method to get usage stats
                    if usage and hasattr(usage, "total_tokens"):
                        client.log_metric(
                            child_run_id, "tokens.total", usage.total_tokens
                        )

                    # PydanticAI uses different field names than OpenAI
                    if usage and hasattr(usage, "request_tokens"):
                        client.log_metric(
                            child_run_id, "tokens.input", usage.request_tokens
                        )
                    elif usage and hasattr(usage, "input_tokens"):
                        client.log_metric(
                            child_run_id, "tokens.input", usage.input_tokens
                        )

                    if usage and hasattr(usage, "response_tokens"):
                        client.log_metric(
                            child_run_id, "tokens.output", usage.response_tokens
                        )
                    elif usage and hasattr(usage, "output_tokens"):
                        client.log_metric(
                            child_run_id, "tokens.output", usage.output_tokens
                        )

                # Log output metrics
                if isinstance(result.output, str):
                    client.log_metric(child_run_id, "output.length", len(result.output))
                    client.log_metric(
                        child_run_id, "output.word_count", len(result.output.split())
                    )
                elif hasattr(result.output, "__dict__"):
                    # Log structured output fields
                    try:
                        for key, value in result.output.__dict__.items():
                            if isinstance(value, int | float):
                                client.log_metric(child_run_id, f"output.{key}", value)
                            elif isinstance(value, str) and len(value) < 100:
                                client.set_tag(child_run_id, f"output.{key}", value)
                    except Exception:
                        pass

            # Mark child run as finished
            client.set_terminated(child_run_id, status="FINISHED")

        except Exception as e:
            execution_time = time.time() - start_time

            # Log error info to master run for this agent
            mlflow.set_tag(
                f"agent.{self.name}.execution_time", f"{execution_time:.2f}s"
            )
            mlflow.set_tag(f"agent.{self.name}.error", str(e)[:100])

            # Log error to child run
            client.log_metric(child_run_id, "execution_time_seconds", execution_time)
            client.set_tag(child_run_id, "status", "failed")
            client.set_tag(child_run_id, "error.type", type(e).__name__)
            client.set_tag(child_run_id, "error.message", str(e)[:200])
            client.set_terminated(child_run_id, status="FAILED")
            raise

        return result
