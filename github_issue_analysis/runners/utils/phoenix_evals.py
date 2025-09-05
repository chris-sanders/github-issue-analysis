"""
Phoenix evaluation integration for PydanticEvals.

This module provides seamless integration between PydanticEvals and Phoenix,
ensuring evaluation results are properly tracked and visualized in Phoenix.
"""

import logging
import os
from typing import Any

from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace
from pydantic_evals.evaluators import Evaluator

logger = logging.getLogger(__name__)


class PhoenixEvaluator(Evaluator):
    """Base evaluator that automatically integrates with Phoenix tracing.

    This evaluator wrapper ensures that evaluation results are properly
    captured in Phoenix traces with the correct span attributes and
    semantic conventions.
    """

    def __init__(self, wrapped_evaluator: Evaluator, metric_name: str = "score"):
        """Initialize Phoenix-aware evaluator.

        Args:
            wrapped_evaluator: The actual evaluator to wrap
            metric_name: Name of the metric being evaluated
        """
        self.wrapped_evaluator = wrapped_evaluator
        self.metric_name = metric_name

    async def evaluate(self, ctx):
        """Evaluate with Phoenix trace integration."""
        # Get current span for annotation
        span = trace.get_current_span()

        # Run the wrapped evaluator
        score = await self.wrapped_evaluator.evaluate(ctx)

        # Add evaluation results to the current span
        if span and span.is_recording():
            self._add_evaluation_attributes(span, ctx, score)

        return score

    def _add_evaluation_attributes(self, span: trace.Span, ctx, score: float):
        """Add evaluation attributes to the Phoenix span."""
        try:
            # Use OpenInference semantic conventions
            span.set_attribute(f"eval.{self.metric_name}.score", score)
            span.set_attribute(
                f"eval.{self.metric_name}.evaluator",
                self.wrapped_evaluator.__class__.__name__,
            )

            # Add case information
            if hasattr(ctx, "inputs") and ctx.inputs:
                case_name = ctx.inputs.get("case_name", "unknown")
                span.set_attribute("eval.case_name", case_name)

            # Add output information
            if hasattr(ctx, "output") and ctx.output:
                if isinstance(ctx.output, str):
                    span.set_attribute("eval.output_length", len(ctx.output))
                elif hasattr(ctx.output, "__dict__"):
                    span.set_attribute("eval.output_type", type(ctx.output).__name__)

            # Add expected output info
            if hasattr(ctx, "expected_output") and ctx.expected_output:
                if isinstance(ctx.expected_output, dict):
                    span.set_attribute(
                        "eval.expected_fields", len(ctx.expected_output.keys())
                    )

            logger.debug(f"Added evaluation attributes for {self.metric_name}: {score}")

        except Exception as e:
            logger.warning(f"Failed to add evaluation attributes: {e}")


def create_phoenix_evaluator(
    evaluator: Evaluator, metric_name: str = "score"
) -> PhoenixEvaluator:
    """Create a Phoenix-aware wrapper around an existing evaluator.

    Args:
        evaluator: The evaluator to wrap
        metric_name: Name of the metric

    Returns:
        Phoenix-integrated evaluator
    """
    return PhoenixEvaluator(evaluator, metric_name)


def create_evaluation_span(
    case_name: str, agent_name: str, evaluator_name: str
) -> trace.Span | None:
    """Create a dedicated evaluation span in Phoenix.

    Args:
        case_name: Name of the test case
        agent_name: Name of the agent being evaluated
        evaluator_name: Name of the evaluator

    Returns:
        Evaluation span or None if tracing not available
    """
    try:
        tracer = trace.get_tracer(__name__)

        # Use just eval_<agent_name> for concise span naming
        agent_code = agent_name.replace(" ", "_").lower()
        span_name = f"eval_{agent_code}"
        span = tracer.start_span(span_name)

        # Set proper OpenInference attributes for evaluation spans
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "EVALUATION")

        # Use semantic conventions that Phoenix understands for evaluations
        span.set_attribute("evaluation.name", f"{evaluator_name}_{case_name}")
        span.set_attribute("evaluation.case_name", case_name)
        span.set_attribute("evaluation.agent_name", agent_name)
        span.set_attribute("evaluation.evaluator", evaluator_name)
        span.set_attribute("agent.name", agent_name)  # Standard agent name

        # Add experiment context
        experiment_name = os.getenv("PHOENIX_EXPERIMENT_NAME", "unknown")
        span.set_attribute("evaluation.experiment", experiment_name)

        return span

    except Exception as e:
        logger.warning(f"Failed to create evaluation span: {e}")
        return None


def log_detailed_scores(
    span: trace.Span,
    scores: dict[str, float],
    reasoning: dict[str, str] | None = None,
):
    """Log detailed evaluation scores to a Phoenix span.

    Args:
        span: Phoenix span to annotate
        scores: Dictionary of metric names to scores
        reasoning: Optional reasoning for each score
    """
    if not span or not span.is_recording():
        return

    try:
        # Add evaluation scores using proper semantic conventions
        overall = (
            sum(scores.values()) / len(scores)
            if len(scores) > 1
            else list(scores.values())[0]
        )

        # Use standard evaluation score attributes that Phoenix recognizes
        span.set_attribute("evaluation.result.score", round(overall, 3))

        # Add individual metric scores with semantic naming
        for metric, score in scores.items():
            span.set_attribute(f"evaluation.metric.{metric}", round(score, 3))

        # Add reasoning if provided
        if reasoning:
            for metric, reason in reasoning.items():
                if len(reason) <= 200:  # Limit length for span attributes
                    span.set_attribute(f"eval.{metric}.reasoning", reason)

        # Add overall score with secondary prefix too
        if len(scores) > 1:
            span.set_attribute("0_eval.00_overall", overall)

        logger.debug(f"Logged {len(scores)} evaluation scores to span")

    except Exception as e:
        logger.warning(f"Failed to log detailed scores: {e}")


def track_evaluation_context(
    span: trace.Span, input_data: Any, expected_output: Any, actual_output: Any
):
    """Track evaluation context in Phoenix span.

    Args:
        span: Phoenix span to annotate
        input_data: Input data for the evaluation
        expected_output: Expected output
        actual_output: Actual output from the agent
    """
    if not span or not span.is_recording():
        return

    try:
        # Track input characteristics
        if isinstance(input_data, dict):
            if "issue" in input_data and isinstance(input_data["issue"], dict):
                issue = input_data["issue"]
                span.set_attribute("context.issue_title", issue.get("title", "")[:100])
                span.set_attribute("context.issue_number", issue.get("number", 0))
                span.set_attribute(
                    "context.issue_body_length", len(str(issue.get("body", "")))
                )

        # Track expected vs actual output characteristics
        if isinstance(expected_output, dict):
            span.set_attribute("context.expected_fields", len(expected_output.keys()))
            if "root_cause" in expected_output:
                span.set_attribute(
                    "context.expected_root_cause_length",
                    len(str(expected_output["root_cause"])),
                )

        if hasattr(actual_output, "__dict__"):
            span.set_attribute(
                "context.actual_output_type", type(actual_output).__name__
            )
            if hasattr(actual_output, "root_cause"):
                span.set_attribute(
                    "context.actual_root_cause_length",
                    len(str(actual_output.root_cause)),
                )
        elif isinstance(actual_output, str):
            span.set_attribute("context.actual_output_length", len(actual_output))
            span.set_attribute(
                "context.actual_is_error", actual_output.startswith("❌")
            )

        logger.debug("Tracked evaluation context in span")

    except Exception as e:
        logger.warning(f"Failed to track evaluation context: {e}")


def get_phoenix_integration():
    """Get the Phoenix integration instance if available.

    Returns:
        Phoenix integration instance or None
    """
    try:
        if os.getenv("PHOENIX_INTEGRATION_INITIALIZED") == "true":
            from .phoenix_integration import PhoenixIntegration

            experiment_name = os.getenv("PHOENIX_EXPERIMENT_NAME", "experiment")
            phoenix = PhoenixIntegration(experiment_name)
            phoenix.init_client()  # Initialize client for dataset operations
            return phoenix
        else:
            return None

    except Exception as e:
        logger.warning(f"Failed to get Phoenix integration: {e}")
        return None


def upload_evaluation_dataset(
    cases: list[dict[str, Any]], name: str | None = None
) -> str | None:
    """Upload evaluation cases as a Phoenix dataset.

    Args:
        cases: List of evaluation cases
        name: Optional dataset name

    Returns:
        Dataset ID if successful, None otherwise
    """
    phoenix = get_phoenix_integration()
    if phoenix:
        return phoenix.upload_dataset(cases, name)
    else:
        logger.warning("Phoenix integration not available for dataset upload")
        return None


def log_evaluation_results(evaluations: list[dict[str, Any]], eval_name: str) -> bool:
    """Log evaluation results to Phoenix.

    Args:
        evaluations: List of evaluation results
        eval_name: Name for the evaluation

    Returns:
        True if successful, False otherwise
    """
    phoenix = get_phoenix_integration()
    if phoenix:
        return phoenix.log_evaluations(evaluations, eval_name)
    else:
        logger.warning("Phoenix integration not available for logging evaluations")
        return False
