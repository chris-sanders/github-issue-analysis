"""Observability Manager for data collection and backend uploads.

This module provides a clean interface for collecting evaluation data and uploading
to various backends (Phoenix, MLflow, file) without using global variables.
"""

import os
from typing import Any

from utils.phoenix_evaluation_upload import (
    upload_agent_comparison_to_phoenix,
    upload_evaluation_results_to_phoenix,
)
from utils.phoenix_results import create_run_summary


class ObservabilityManager:
    """Manages evaluation data collection and uploads for experiments."""

    def __init__(self, experiment_name: str, backend: str | None = None):
        """Initialize observability manager.

        Args:
            experiment_name: Name of the experiment (e.g., "exp03_mcp_agents")
            backend: Backend to use (phoenix, mlflow, file). If None, uses TRACING_BACKEND env var.
        """
        self.experiment_name = experiment_name
        self.backend = backend or os.getenv("TRACING_BACKEND", "file").lower()

        # Data storage - replaces global variables
        self.evaluation_results: dict[str, Any] = {}  # Case name -> evaluation scores
        self.span_mappings: dict[str, str] = {}  # Case name -> span ID
        self.runner_mappings: dict[str, Any] = {}  # Case name -> runner object
        self.agent_mappings: dict[str, str] = {}  # Case name -> agent name

    def collect_evaluation(
        self,
        case_name: str,
        runner: Any,
        agent_name: str,
        scores: Any,
        span_id: str | None = None,
    ):
        """Collect evaluation data with span mapping.

        Args:
            case_name: Name of the evaluation case
            runner: Runner object that performed the evaluation
            agent_name: Name of the agent (for grouping)
            scores: Evaluation scores object
            span_id: Optional span ID for Phoenix SpanEvaluations
        """
        self.evaluation_results[case_name] = scores
        self.runner_mappings[case_name] = runner
        self.agent_mappings[case_name] = agent_name

        if span_id:
            self.span_mappings[case_name] = span_id

    async def finalize_experiment(self) -> bool:
        """Upload evaluation data based on backend configuration.

        Returns:
            True if uploads succeeded, False otherwise
        """
        if self.backend == "phoenix":
            return await self._upload_to_phoenix()
        elif self.backend == "mlflow":
            return await self._upload_to_mlflow()
        elif self.backend == "file":
            return await self._upload_to_file()
        else:
            # Unknown backend - treat as file backend
            print(f"⚠️ Unknown backend '{self.backend}', treating as file backend")
            return await self._upload_to_file()

    async def _upload_to_phoenix(self) -> bool:
        """Upload evaluation data to Phoenix using SpanEvaluations API.

        Returns:
            True if both uploads succeeded, False otherwise
        """
        if not self.evaluation_results:
            print("⚠️ No evaluation results to upload to Phoenix")
            return False

        print("📊 Uploading evaluation results to Phoenix using SpanEvaluations...")

        # Upload detailed evaluation results
        upload_success = upload_evaluation_results_to_phoenix(
            self.evaluation_results,
            self.agent_mappings,
            self.span_mappings,
            self.runner_mappings,
            self.experiment_name,
        )

        if upload_success:
            print("✅ Successfully uploaded detailed evaluation results to Phoenix")
        else:
            print("❌ Failed to upload detailed evaluation results to Phoenix")

        # Upload agent comparison summary
        comparison_success = upload_agent_comparison_to_phoenix(
            self.evaluation_results,
            self.agent_mappings,
            self.runner_mappings,
            self.experiment_name,
        )

        if comparison_success:
            print("✅ Successfully uploaded agent comparison to Phoenix")
        else:
            print("❌ Failed to upload agent comparison to Phoenix")

        # If both uploads failed, try fallback summary trace
        if not upload_success and not comparison_success:
            print("🔄 SpanEvaluations failed, falling back to summary trace...")
            summary = create_run_summary(
                self.evaluation_results, self.agent_mappings, self.experiment_name
            )
            if summary and summary.get("agents"):
                agent_count = len(summary["agents"])
                case_count = summary.get("total_cases", 0)
                print(
                    f"✅ Created fallback summary trace with {agent_count} agents, {case_count} cases"
                )
                return True  # Fallback succeeded

        final_success = upload_success and comparison_success
        return final_success

    async def _upload_to_mlflow(self) -> bool:
        """Upload evaluation data to MLflow.

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.evaluation_results:
            print("⚠️ No evaluation results to upload to MLflow")
            return False

        print("📊 Uploading evaluation results to MLflow...")

        try:
            import mlflow

            # Log experiment-level metrics if we have a run
            master_run_id = os.environ.get("MLFLOW_MASTER_RUN_ID")
            if master_run_id:
                # Log summary metrics for each agent
                agent_summary = self.get_agent_summary()
                for agent_name, data in agent_summary.items():
                    mlflow.log_metric(
                        f"{agent_name.lower().replace(' ', '_')}_avg_score",
                        data["average_score"],
                    )
                    mlflow.log_metric(
                        f"{agent_name.lower().replace(' ', '_')}_case_count",
                        data["case_count"],
                    )

                # Log overall experiment metrics
                total_cases = sum(data["case_count"] for data in agent_summary.values())
                mlflow.log_metric("total_cases", total_cases)
                mlflow.log_metric("agents_count", len(agent_summary))

                print(
                    f"✅ Successfully logged {total_cases} cases across {len(agent_summary)} agents to MLflow"
                )
                return True
            else:
                print("⚠️ No MLflow master run found, cannot log experiment results")
                return False

        except ImportError:
            print("❌ MLflow not available for upload")
            return False
        except Exception as e:
            print(f"❌ Failed to upload to MLflow: {e}")
            return False

    async def _upload_to_file(self) -> bool:
        """Upload evaluation data to file backend.

        For file backend, no remote uploads are needed since results are already
        saved locally by the experiment output functions.

        Returns:
            True always (file backend doesn't need uploads)
        """
        if self.evaluation_results:
            total_cases = len(self.evaluation_results)
            agent_count = len(set(self.agent_mappings.values()))
            print(
                f"📁 File backend: {total_cases} cases across {agent_count} agents saved locally"
            )
        else:
            print("📁 File backend: No evaluation results to save")

        return True

    def get_agent_summary(self) -> dict[str, Any]:
        """Get summary of agent performance for display.

        Returns:
            Dictionary with agent names as keys and performance data as values
        """
        if not self.evaluation_results or not self.agent_mappings:
            return {}

        agent_results = {}
        for case_name, score_obj in self.evaluation_results.items():
            agent_name = self.agent_mappings.get(case_name, "unknown_agent")
            if agent_name not in agent_results:
                agent_results[agent_name] = []
            agent_results[agent_name].append(score_obj.overall_score)

        # Calculate averages
        summary = {}
        for agent_name, scores in agent_results.items():
            avg_score = sum(scores) / len(scores) if scores else 0
            summary[agent_name] = {
                "average_score": avg_score,
                "case_count": len(scores),
                "scores": scores,
            }

        return summary

    def clear(self):
        """Clear all stored data for fresh experiment run."""
        self.evaluation_results.clear()
        self.span_mappings.clear()
        self.runner_mappings.clear()
        self.agent_mappings.clear()
