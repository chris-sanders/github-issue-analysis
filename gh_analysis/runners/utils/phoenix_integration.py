"""
Simplified Phoenix integration following best practices.

This module provides a clean Phoenix integration that:
1. Uses automatic instrumentation properly
2. Integrates seamlessly with PydanticEvals
3. Provides proper context tracking
4. Captures tool calls hierarchically
5. Uses OpenInference semantic conventions correctly
"""

import logging
import os
from typing import Any

import pandas as pd
import phoenix as px
from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from openinference.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanProcessor
from phoenix.trace import SpanEvaluations

logger = logging.getLogger(__name__)


class SpanRenamerProcessor(SpanProcessor):
    """Custom span processor that renames 'agent run' spans to use agent name."""

    def __init__(self, next_processor: SpanProcessor):
        self.next_processor = next_processor

    def on_start(self, span: ReadableSpan, parent_context) -> None:
        self.next_processor.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        # Check if this is an "agent run" span with an agent_name attribute
        if span.name == "agent run":
            attributes = span.attributes or {}
            agent_name = attributes.get("agent_name")
            if agent_name:
                # Rename the span to use agent name
                # Judge spans already have "judge_" prefix, don't add "eval_"
                if agent_name.lower().startswith("judge_"):
                    new_name = agent_name.replace(" ", "_").lower()
                elif "eval_" in agent_name.lower():
                    new_name = agent_name.replace(" ", "_").lower()
                else:
                    new_name = f"eval_{agent_name.replace(' ', '_').lower()}"
                span._name = new_name
                logger.debug(f"📝 Renamed span from 'agent run' to '{new_name}'")

        self.next_processor.on_end(span)

    def shutdown(self) -> None:
        return self.next_processor.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.next_processor.force_flush(timeout_millis)


class PhoenixIntegration:
    """Simplified Phoenix integration with automatic instrumentation."""

    def __init__(self, experiment_name: str = "experiment"):
        self.experiment_name = experiment_name
        self.client = None
        self._instrumented = False

    def setup_tracing(self) -> bool:
        """Set up Phoenix tracing with proper automatic instrumentation.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create resource with Phoenix project name
            resource = Resource(
                attributes={
                    ResourceAttributes.PROJECT_NAME: self.experiment_name,
                    "service.name": self.experiment_name,
                    "service.version": "1.0.0",
                    "deployment.environment": os.getenv("ENVIRONMENT", "development"),
                }
            )

            # Create tracer provider
            tracer_provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(tracer_provider)

            # Set up OTLP exporter to Phoenix
            endpoint = os.getenv("PHOENIX_ENDPOINT", "http://localhost:4317")
            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                timeout=30,
            )

            # Use batch processor for better performance
            batch_processor = BatchSpanProcessor(
                exporter,
                max_queue_size=2048,
                max_export_batch_size=512,
                schedule_delay_millis=2000,  # Export every 2 seconds for faster feedback
            )

            # Wrap batch processor with span renamer to fix "agent run" naming
            span_processor = SpanRenamerProcessor(batch_processor)
            tracer_provider.add_span_processor(span_processor)

            logger.info(
                f"✅ Phoenix OpenTelemetry configured for project: {self.experiment_name}"
            )
            logger.info(f"📡 Sending traces to: {endpoint}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup Phoenix tracing: {e}")
            return False

    def instrument_pydantic_ai(self) -> bool:
        """Instrument PydanticAI for automatic tracing.

        Returns:
            True if successful, False otherwise
        """
        if self._instrumented:
            logger.warning("PydanticAI already instrumented")
            return True

        try:
            # Get the tracer provider that was set up
            tracer_provider = trace.get_tracer_provider()

            # Add OpenInference span processor for PydanticAI tracing
            openinference_processor = OpenInferenceSpanProcessor()
            tracer_provider.add_span_processor(openinference_processor)

            self._instrumented = True
            logger.info("✅ PydanticAI OpenInference instrumentation enabled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to instrument PydanticAI: {e}")
            return False

    def init_client(self) -> bool:
        """Initialize Phoenix client for dataset and evaluation operations.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client = px.Client()
            logger.info("✅ Phoenix client initialized")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Phoenix client initialization failed: {e}")
            self.client = None
            return False

    def upload_dataset(
        self, cases: list[dict[str, Any]], name: str | None = None
    ) -> str | None:
        """Upload evaluation cases as a Phoenix dataset.

        Args:
            cases: List of test case dictionaries
            name: Optional dataset name

        Returns:
            Dataset ID if successful, None otherwise
        """
        if not self.client:
            logger.warning("Phoenix client not available for dataset upload")
            return None

        try:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dataset_name = name or f"{self.experiment_name}_dataset_{timestamp}"

            # Convert cases to Phoenix dataset format with better structure
            records = []
            for i, case in enumerate(cases):
                # Create a more structured record for Phoenix
                case_id = case.get("case_id", case.get("name", f"case_{i}"))

                # Handle inputs - convert complex objects to strings
                inputs_data = case.get("inputs", {})
                if isinstance(inputs_data, dict):
                    # For GitHub issues, extract key information
                    if "title" in inputs_data and "body" in inputs_data:
                        inputs_str = f"Title: {inputs_data['title']}\nBody: {inputs_data['body'][:200]}..."
                    else:
                        inputs_str = str(inputs_data)[:500]
                else:
                    inputs_str = str(inputs_data)[:500]

                # Handle expected output
                expected_data = case.get("expected_output", {})
                if isinstance(expected_data, dict):
                    expected_str = str(expected_data)[:500]
                else:
                    expected_str = str(expected_data)[:500]

                # Handle metadata
                metadata_data = case.get("metadata", {})
                metadata_str = str(metadata_data) if metadata_data else "{}"

                record = {
                    "case_id": case_id,
                    "inputs": inputs_str,
                    "expected_output": expected_str,
                    "metadata": metadata_str,
                }
                records.append(record)

            # Create DataFrame and upload
            df = pd.DataFrame(records)
            dataset = self.client.upload_dataset(
                dataframe=df,
                dataset_name=dataset_name,
                input_keys=["inputs"],
                output_keys=["expected_output"],
                metadata_keys=["metadata"],
            )

            logger.info(f"✅ Uploaded dataset '{dataset_name}' with {len(cases)} cases")
            return dataset.id

        except Exception as e:
            logger.error(f"❌ Failed to upload dataset: {e}")
            return None

    def log_evaluations(
        self,
        evaluations: list[dict[str, Any]],
        eval_name: str,
        dataset_id: str | None = None,
    ) -> bool:
        """Log evaluation results to Phoenix.

        Args:
            evaluations: List of evaluation results with span_id and scores
            eval_name: Name for the evaluation

        Returns:
            True if successful, False otherwise
        """
        if not self.client or not evaluations:
            logger.warning("Phoenix client not available or no evaluations to log")
            return False

        try:
            # Convert evaluations to DataFrame
            rows = []
            for eval_data in evaluations:
                row = {
                    "span_id": eval_data["span_id"],
                    "score": eval_data.get("score", 0.0),
                    "label": eval_data.get("label", ""),
                }

                # Add any additional metadata
                for key, value in eval_data.get("metadata", {}).items():
                    if isinstance(value, int | float | str | bool):
                        row[key] = value

                rows.append(row)

            if rows:
                df = pd.DataFrame(rows).set_index("span_id")
                evaluation = SpanEvaluations(dataframe=df, eval_name=eval_name)
                self.client.log_evaluations(evaluation)
                logger.info(f"✅ Logged {len(rows)} evaluations for {eval_name}")
                return True
            else:
                logger.warning("No valid evaluation rows to log")
                return False

        except Exception as e:
            logger.error(f"❌ Failed to log evaluations: {e}")
            return False


def setup_phoenix_tracing(
    experiment_name: str = "experiment",
) -> PhoenixIntegration | None:
    """Set up Phoenix tracing with best practices.

    Args:
        experiment_name: Name of the experiment/project

    Returns:
        PhoenixIntegration instance if successful, None otherwise
    """
    phoenix = PhoenixIntegration(experiment_name)

    # Set up tracing infrastructure
    if not phoenix.setup_tracing():
        logger.error("Failed to setup Phoenix tracing infrastructure")
        return None

    # Instrument PydanticAI for automatic tracing
    if not phoenix.instrument_pydantic_ai():
        logger.error("Failed to instrument PydanticAI")
        return None

    # Initialize client for dataset/evaluation operations
    phoenix.init_client()  # This can fail but we still return the integration

    logger.info("🔭 Phoenix integration complete")
    logger.info("📊 Features: automatic instrumentation, datasets, evaluations")

    return phoenix


def enhance_agent_for_phoenix(agent, context_info: dict[str, Any] | None = None):
    """Enhance a PydanticAI agent for better Phoenix tracing.

    Args:
        agent: PydanticAI Agent instance
        context_info: Optional context information to add to traces
    """
    # Set instrument=True for automatic Phoenix integration
    agent.instrument = True

    # Add context information if provided
    if context_info:
        # Store context info that can be accessed during tracing
        agent._phoenix_context = context_info

    logger.debug(f"✅ Enhanced agent '{agent.name}' for Phoenix tracing")


def create_context_span(
    name: str, context_data: dict[str, Any], parent_span: trace.Span | None = None
) -> trace.Span:
    """Create a span with rich context information using OpenInference conventions.

    Args:
        name: Span name
        context_data: Context information to add
        parent_span: Optional parent span

    Returns:
        New span with context attributes
    """
    from openinference.semconv.trace import SpanAttributes

    tracer = trace.get_tracer(__name__)

    # Create span
    if parent_span:
        span = tracer.start_as_current_span(name, parent_span)
    else:
        span = tracer.start_as_current_span(name)

    # Add OpenInference attributes
    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")

    # Add context data using semantic conventions
    for key, value in context_data.items():
        if isinstance(value, int | float | str | bool):
            span.set_attribute(f"context.{key}", value)
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            for i, item in enumerate(value[:10]):  # Limit to first 10 items
                span.set_attribute(f"context.{key}.{i}", item)

    return span


def track_evaluation_in_phoenix(
    span_id: str,
    scores: dict[str, float],
    phoenix_integration: PhoenixIntegration,
    eval_name: str = "agent_evaluation",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Track evaluation results in Phoenix.

    Args:
        span_id: ID of the span being evaluated
        scores: Dictionary of metric names to scores
        phoenix_integration: Phoenix integration instance
        eval_name: Name for the evaluation
        metadata: Optional additional metadata

    Returns:
        True if successful, False otherwise
    """
    try:
        evaluations = []
        for metric_name, score in scores.items():
            evaluation = {
                "span_id": span_id,
                "score": score,
                "label": metric_name,
                "metadata": metadata or {},
            }
            evaluations.append(evaluation)

        # Log each metric as a separate evaluation for better Phoenix visualization
        for evaluation in evaluations:
            metric_eval_name = f"{eval_name}_{evaluation['label']}"
            phoenix_integration.log_evaluations([evaluation], metric_eval_name)

        return True

    except Exception as e:
        logger.error(f"❌ Failed to track evaluation in Phoenix: {e}")
        return False


def flush_phoenix_traces(timeout_seconds: int = 5) -> bool:
    """Flush any pending Phoenix traces.

    Args:
        timeout_seconds: Timeout for flushing

    Returns:
        True if successful, False otherwise
    """
    try:
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "force_flush"):
            success = tracer_provider.force_flush(
                timeout_seconds * 1000
            )  # Convert to ms
            if success:
                logger.info("✅ Phoenix traces flushed successfully")
                return True
            else:
                logger.warning("⚠️ Phoenix trace flush timed out")
                return False
        else:
            logger.warning("⚠️ Tracer provider doesn't support force_flush")
            return False

    except Exception as e:
        logger.error(f"❌ Failed to flush Phoenix traces: {e}")
        return False
