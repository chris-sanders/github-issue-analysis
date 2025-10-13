"""
Phoenix evaluation upload using native SpanEvaluations.

This module replaces the manual summary span approach with Phoenix's native
SpanEvaluations API for better visualization and time-series tracking.
"""

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import phoenix as px
from phoenix.trace import SpanEvaluations

logger = logging.getLogger(__name__)


def upload_evaluation_results_to_phoenix(
    detailed_scores: dict[str, Any],
    case_to_agent: dict[str, str],
    span_id_mapping: dict[str, str],
    case_to_runner: dict[str, Any],
    experiment_name: str,
) -> bool:
    """Upload structured evaluation results directly to Phoenix using SpanEvaluations.

    Args:
        detailed_scores: Dictionary of case_name -> AnalysisScore objects
        case_to_agent: Dictionary mapping case_name -> agent_name
        span_id_mapping: Dictionary mapping case_name -> span_id_hex
        case_to_runner: Dictionary mapping case_name -> runner objects
        experiment_name: Name of the experiment

    Returns:
        True if successful, False otherwise
    """
    try:
        if not detailed_scores:
            logger.warning("No detailed scores to upload")
            return False

        # Convert detailed scores to Phoenix SpanEvaluations format
        evaluation_rows = []

        for case_name, score_obj in detailed_scores.items():
            agent_name = case_to_agent.get(case_name, "unknown_agent")
            span_id = span_id_mapping.get(case_name)

            if not span_id:
                logger.warning(f"No span_id found for case {case_name}, skipping")
                continue

            # Create evaluation row with Phoenix-required columns
            # Phoenix SpanEvaluations requires 'score', 'label', and optionally 'explanation'
            row = {
                "span_id": span_id,
                "score": round(score_obj.overall_score, 3)
                if hasattr(score_obj, "overall_score")
                else 0.0,
                "label": f"{agent_name}_evaluation",
                "explanation": f"Agent: {agent_name}, Case: {case_name}",
            }

            # Add metadata as additional columns (Phoenix may accept these)
            row.update(
                {
                    "agent_name": agent_name,
                    "case_name": case_name,
                    "experiment": experiment_name,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Add detailed scores as metadata
            if hasattr(score_obj, "technical_accuracy"):
                row["technical_accuracy"] = round(
                    score_obj.technical_accuracy.score / 100.0, 3
                )
                row["technical_reasoning"] = score_obj.technical_accuracy.reasoning[
                    :200
                ]

            if hasattr(score_obj, "root_cause"):
                row["root_cause"] = round(score_obj.root_cause.score / 100.0, 3)
                row["root_cause_reasoning"] = score_obj.root_cause.reasoning[:200]

            if hasattr(score_obj, "solution_quality"):
                row["solution_quality"] = round(
                    score_obj.solution_quality.score / 100.0, 3
                )
                row["solution_reasoning"] = score_obj.solution_quality.reasoning[:200]

            evaluation_rows.append(row)

        if not evaluation_rows:
            logger.warning("No valid evaluation rows to upload")
            return False

        # Group evaluation rows by agent for separate uploads
        agent_groups = {}
        for row in evaluation_rows:
            agent_name = row["agent_name"]
            if agent_name not in agent_groups:
                agent_groups[agent_name] = []
            agent_groups[agent_name].append(row)

        # Upload separate evaluation for each agent with concise names
        try:
            client = px.Client()
            logger.debug("Phoenix client created successfully")
        except Exception as e:
            logger.error(f"Failed to create Phoenix client: {e}")
            return False

        upload_success = True

        for agent_name, agent_rows in agent_groups.items():
            # Use runner's code_name if available, otherwise fallback to processing
            agent_code = None

            # Try to find the runner for this agent from case_to_runner mapping
            for case_name in detailed_scores.keys():
                if case_to_agent.get(case_name) == agent_name:
                    runner = case_to_runner.get(case_name)
                    if runner:
                        agent_code = runner.name
                        break

            # Fallback to basic processing if no runner found
            if not agent_code:
                agent_code = agent_name.replace(" ", "_").lower()
                if agent_code.startswith("claude_"):
                    agent_code = agent_code.replace("claude_", "")
                if agent_code.startswith("gpt_"):
                    agent_code = agent_code.replace("gpt_", "")

            # Agent name only - no timestamp (Phoenix tracks time automatically)
            eval_name = agent_code

            # Create DataFrame for this agent
            df = pd.DataFrame(agent_rows).set_index("span_id")

            try:
                span_evaluations = SpanEvaluations(
                    dataframe=df,
                    eval_name=eval_name,
                )
                client.log_evaluations(span_evaluations)
                logger.info(
                    f"✅ Uploaded {agent_name} as '{eval_name}' ({len(agent_rows)} cases)"
                )
            except Exception as e:
                logger.error(f"❌ Failed to upload {agent_name}: {e}")
                upload_success = False

        logger.info(f"📊 Uploaded {len(agent_groups)} separate agent evaluations")

        return upload_success

    except Exception as e:
        logger.error(f"❌ Failed to upload evaluation results to Phoenix: {e}")
        return False


def upload_agent_comparison_to_phoenix(
    detailed_scores: dict[str, Any],
    case_to_agent: dict[str, str],
    case_to_runner: dict[str, Any],
    experiment_name: str,
) -> bool:
    """Upload agent comparison summary to Phoenix for time-series tracking.

    Args:
        detailed_scores: Dictionary of case_name -> AnalysisScore objects
        case_to_agent: Dictionary mapping case_name -> agent_name
        case_to_runner: Dictionary mapping case_name -> runner objects
        experiment_name: Name of the experiment

    Returns:
        True if successful, False otherwise
    """
    try:
        # Organize results by agent
        agent_results = {}

        for case_name, score_obj in detailed_scores.items():
            agent_name = case_to_agent.get(case_name, "unknown_agent")

            if agent_name not in agent_results:
                agent_results[agent_name] = {
                    "technical_accuracy": [],
                    "root_cause": [],
                    "solution_quality": [],
                    "overall_score": [],
                }

            # Collect scores for this agent
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

        # Calculate agent averages
        comparison_rows = []
        timestamp = datetime.now().strftime("%m%d_%H%M")

        for agent_name, metrics in agent_results.items():
            # Calculate overall average score for Phoenix-required 'score' field
            overall_scores = metrics.get("overall_score", [])
            avg_overall = (
                sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
            )

            # Use runner's code_name if available, otherwise fallback to processing
            agent_code = None

            # Try to find the runner for this agent from case_to_runner mapping
            for case_name in detailed_scores.keys():
                if case_to_agent.get(case_name) == agent_name:
                    runner = case_to_runner.get(case_name)
                    if runner:
                        agent_code = runner.name
                        break

            # Fallback to basic processing if no runner found
            if not agent_code:
                agent_code = agent_name.replace(" ", "_").lower()
                if agent_code.startswith("claude_"):
                    agent_code = agent_code.replace("claude_", "")
                if agent_code.startswith("gpt_"):
                    agent_code = agent_code.replace("gpt_", "")

            row = {
                "span_id": f"summary_{agent_code}_{timestamp}",
                "score": round(avg_overall, 3),
                "label": agent_code,  # Just the agent name for the key
                "explanation": f"{agent_name}: {len(overall_scores)} cases, avg={avg_overall:.3f}",
            }

            # Add metadata
            row.update(
                {
                    "agent_name": agent_name,
                    "experiment": experiment_name,
                    "timestamp": datetime.now().isoformat(),
                    "total_cases": len(overall_scores),
                }
            )

            # Calculate averages for each metric as metadata
            for metric, scores in metrics.items():
                if scores:
                    row[f"{metric}_avg"] = round(sum(scores) / len(scores), 3)
                    row[f"{metric}_min"] = round(min(scores), 3)
                    row[f"{metric}_max"] = round(max(scores), 3)

            comparison_rows.append(row)

        if not comparison_rows:
            logger.warning("No agent comparison data to upload")
            return False

        # Create DataFrame for agent comparison
        df = pd.DataFrame(comparison_rows).set_index("span_id")

        # Upload agent comparison to Phoenix with concise name
        client = px.Client()
        eval_name = f"comparison_{timestamp}"

        span_evaluations = SpanEvaluations(
            dataframe=df,
            eval_name=eval_name,
        )

        client.log_evaluations(span_evaluations)

        logger.info(
            f"✅ Successfully uploaded agent comparison to Phoenix as '{eval_name}'"
        )
        logger.info(f"📊 Compared {len(comparison_rows)} agents")

        # Log summary stats
        best_agent = max(comparison_rows, key=lambda x: x.get("overall_score_avg", 0))
        logger.info(
            f"🏆 Best performing agent: {best_agent['agent_name']} ({best_agent.get('overall_score_avg', 0):.3f})"
        )

        return True

    except Exception as e:
        logger.error(f"❌ Failed to upload agent comparison to Phoenix: {e}")
        return False


def create_span_id_mapping_from_context(
    evaluation_contexts: list[dict[str, Any]],
) -> dict[str, str]:
    """Create mapping from case names to span IDs from evaluation contexts.

    Args:
        evaluation_contexts: List of evaluation context dictionaries

    Returns:
        Dictionary mapping case_name -> span_id_hex
    """
    span_mapping = {}

    for context in evaluation_contexts:
        case_name = context.get("case_name")
        span_id = context.get("span_id")

        if case_name and span_id:
            # Convert span_id to hex format if needed
            if isinstance(span_id, int):
                span_id_hex = format(span_id, "016x")
            else:
                span_id_hex = str(span_id)

            span_mapping[case_name] = span_id_hex

    return span_mapping


def get_phoenix_client() -> px.Client | None:
    """Get Phoenix client with error handling.

    Returns:
        Phoenix client if available, None otherwise
    """
    try:
        client = px.Client()
        logger.debug("✅ Phoenix client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"❌ Failed to initialize Phoenix client: {e}")
        return None
