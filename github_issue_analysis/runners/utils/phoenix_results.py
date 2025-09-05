"""
Phoenix results tracking for experiment summary and comparison.

This module provides functions to create summary evaluations and comparisons
that are easily visible in Phoenix's Evaluations UI.
"""

import logging
from datetime import datetime
from typing import Any

from openinference.semconv.trace import SpanAttributes
from opentelemetry import trace

logger = logging.getLogger(__name__)


def create_experiment_summary_span(
    experiment_name: str, agent_results: dict[str, dict[str, float]]
) -> None:
    """Create a summary span for the entire experiment with agent comparisons.

    Args:
        experiment_name: Name of the experiment
        agent_results: Dictionary of {agent_name: {metric: score}}
    """
    try:
        tracer = trace.get_tracer(__name__)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        with tracer.start_as_current_span(f"summary_{timestamp}") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "EVALUATION")
            span.set_attribute("experiment.name", experiment_name)
            span.set_attribute("experiment.type", "agent_comparison")
            span.set_attribute("experiment.timestamp", timestamp)
            span.set_attribute("experiment.agent_count", len(agent_results))

            # Add summary scores for each agent
            for agent_name, scores in agent_results.items():
                overall_score = scores.get("overall_score", 0)
                span.set_attribute(
                    f"agent.{agent_name.replace(' ', '_')}.overall",
                    round(overall_score, 2),
                )

                for metric, score in scores.items():
                    if metric != "overall_score":
                        span.set_attribute(
                            f"agent.{agent_name.replace(' ', '_')}.{metric}",
                            round(score, 2),
                        )

            # Find best performing agent overall
            best_agent = max(
                agent_results.items(), key=lambda x: x[1].get("overall_score", 0)
            )
            span.set_attribute("experiment.best_agent", best_agent[0])
            span.set_attribute(
                "experiment.best_score", round(best_agent[1].get("overall_score", 0), 2)
            )

            # Add comparison metrics
            if len(agent_results) >= 2:
                scores_list = [
                    scores.get("overall_score", 0) for scores in agent_results.values()
                ]
                score_range = max(scores_list) - min(scores_list)
                span.set_attribute("experiment.score_range", round(score_range, 2))
                span.set_attribute(
                    "experiment.avg_score",
                    round(sum(scores_list) / len(scores_list), 2),
                )

            logger.info(f"✅ Created experiment summary span for {experiment_name}")

    except Exception as e:
        logger.error(f"❌ Failed to create experiment summary span: {e}")


def log_agent_comparison_evaluations(
    agent_results: dict[str, dict[str, float]], experiment_name: str
) -> bool:
    """Log agent comparison evaluations to Phoenix for easy tracking.

    Args:
        agent_results: Dictionary of {agent_name: {metric: score}}
        experiment_name: Name of the experiment

    Returns:
        True if successful, False otherwise
    """
    try:
        from .phoenix_evals import get_phoenix_integration

        phoenix_integration = get_phoenix_integration()
        if not phoenix_integration:
            logger.warning("Phoenix integration not available for results tracking")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create evaluations for overall agent comparison
        comparison_evaluations = []
        for agent_name, scores in agent_results.items():
            overall_score = scores.get("overall_score", 0)

            evaluation_data = {
                "span_id": f"agent_{agent_name.replace(' ', '_')}_{timestamp}",
                "score": round(overall_score, 2),
                "label": agent_name,
                "metadata": {
                    "agent": agent_name,
                    "experiment": experiment_name,
                    "timestamp": timestamp,
                    "metric_type": "overall_performance",
                },
            }
            comparison_evaluations.append(evaluation_data)

        # Log the overall comparison - try to get dataset_id from global if available
        try:
            # Try to get dataset_id from environment or global context
            dataset_id = None  # We don't have easy access to the dataset_id here
            success = phoenix_integration.log_evaluations(
                comparison_evaluations,
                f"{experiment_name}_agent_comparison",
                dataset_id=dataset_id,
            )
        except Exception:
            # Fallback without dataset_id
            success = phoenix_integration.log_evaluations(
                comparison_evaluations, f"{experiment_name}_agent_comparison"
            )

        if success:
            logger.info(f"✅ Logged agent comparison evaluations for {experiment_name}")
            return True
        else:
            logger.warning("⚠️ Failed to log agent comparison evaluations")
            return False

    except Exception as e:
        logger.error(f"❌ Error logging agent comparison evaluations: {e}")
        return False


def create_run_summary(
    detailed_scores: dict[str, Any],
    case_to_agent: dict[str, str],
    experiment_name: str = "exp03_mcp_agents",
) -> dict[str, Any]:
    """Create a summary of the experimental run for Phoenix tracking.

    Args:
        detailed_scores: Dictionary of case_name -> AnalysisScore objects
        case_to_agent: Dictionary mapping case_name -> agent_name
        experiment_name: Name of the experiment

    Returns:
        Summary data for the run
    """
    try:
        # Organize results by agent
        agent_results = {}

        for case_name, score_obj in detailed_scores.items():
            # Use the case_to_agent mapping for accurate agent names
            agent_name = case_to_agent.get(case_name, "unknown_agent")

            if agent_name not in agent_results:
                agent_results[agent_name] = {
                    "technical_accuracy": [],
                    "root_cause": [],
                    "solution_quality": [],
                    "overall_score": [],
                }

            # Add scores for this case
            if hasattr(score_obj, "technical_accuracy"):
                agent_results[agent_name]["technical_accuracy"].append(
                    score_obj.technical_accuracy.score / 100.0
                )
            if hasattr(score_obj, "root_cause"):
                agent_results[agent_name]["root_cause"].append(
                    score_obj.root_cause.score / 100.0
                )
            if hasattr(score_obj, "solution_quality"):
                agent_results[agent_name]["solution_quality"].append(
                    score_obj.solution_quality.score / 100.0
                )
            if hasattr(score_obj, "overall_score"):
                agent_results[agent_name]["overall_score"].append(
                    score_obj.overall_score
                )

        # Calculate averages for each agent
        agent_summaries = {}
        for agent_name, metrics in agent_results.items():
            agent_summaries[agent_name] = {}
            for metric, scores in metrics.items():
                if scores:  # Only if we have scores for this metric
                    agent_summaries[agent_name][metric] = sum(scores) / len(scores)

        # Create experiment summary span
        if agent_summaries:
            create_experiment_summary_span(experiment_name, agent_summaries)

            # Log comparison evaluations
            log_agent_comparison_evaluations(agent_summaries, experiment_name)

        return {
            "experiment": experiment_name,
            "timestamp": datetime.now().isoformat(),
            "agents": agent_summaries,
            "total_cases": len(detailed_scores),
        }

    except Exception as e:
        logger.error(f"❌ Error creating run summary: {e}")
        return {}
