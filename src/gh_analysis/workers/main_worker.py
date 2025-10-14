#!/usr/bin/env python3
"""
Temporal worker for exp05_temporal GitHub analysis.

This worker registers workflows and activities for processing GitHub issues
with AI agents.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from pydantic_ai.durable_exec.temporal import AgentPlugin, PydanticAIPlugin
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

# Import observability
from framework.temporal.observability import (
    flush_traces,
    get_temporal_interceptor,
    init_observability,
)

# Import workflows and activities (relative imports within exp05_temporal)
from gh_analysis.activities import (
    cleanup_mcp_bundles,
    fetch_github_issue,
    run_agent_analysis,
)
from gh_analysis.agents.troubleshoot import gpt5_mini_medium_agent
from gh_analysis.workflows.troubleshoot import GitHubAnalysisWorkflow

logger = logging.getLogger(__name__)


class Exp05Worker:
    """Worker for exp05_temporal workflows."""

    def __init__(self):
        self.logger = self._setup_logging()
        self.client: Optional[Client] = None
        self.worker: Optional[Worker] = None
        self._shutdown_event = asyncio.Event()

        # Configuration
        self.temporal_host = os.getenv("TEMPORAL_HOST", "localhost:7233")
        self.temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
        self.task_queue = os.getenv("TASK_QUEUE", "gh-analysis-queue")
        self.max_concurrent_activities = int(
            os.getenv("MAX_CONCURRENT_ACTIVITIES", "5")
        )
        self.max_concurrent_workflows = int(os.getenv("MAX_CONCURRENT_WORKFLOWS", "3"))

    def _setup_logging(self) -> logging.Logger:
        """Configure logging."""
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        return logging.getLogger(__name__)

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.logger.info(f"Received {signal_name}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _connect_to_temporal(self) -> Client:
        """Connect to Temporal server with tracing."""
        self.logger.info(f"Connecting to Temporal at {self.temporal_host}")

        try:
            # Get Temporal interceptor for tracing
            temporal_interceptor = get_temporal_interceptor()
            interceptors = [temporal_interceptor] if temporal_interceptor else []

            client = await Client.connect(
                self.temporal_host,
                namespace=self.temporal_namespace,
                data_converter=pydantic_data_converter,
                plugins=[PydanticAIPlugin()],  # Required for TemporalAgent
                interceptors=interceptors,  # Add tracing interceptor
            )
            if temporal_interceptor:
                self.logger.info(
                    "Successfully connected to Temporal with PydanticAI plugin and tracing"
                )
            else:
                self.logger.info(
                    "Successfully connected to Temporal with PydanticAI plugin (no tracing)"
                )
            return client
        except Exception as e:
            self.logger.error(f"Failed to connect to Temporal: {e}")
            raise

    def _create_worker(self, client: Client) -> Worker:
        """Create Temporal worker."""
        self.logger.info(
            "Creating Temporal worker with TemporalAgent and persistent storage..."
        )

        # TemporalAgent must be registered via AgentPlugin at worker startup
        # Uses shared bundle storage - MCP server manages multiple bundles
        worker = Worker(
            client,
            task_queue=self.task_queue,
            workflows=[GitHubAnalysisWorkflow],
            activities=[
                cleanup_mcp_bundles,  # Clean bundles first
                fetch_github_issue,
                run_agent_analysis,  # For v1 agents
            ],
            plugins=[
                AgentPlugin(
                    gpt5_mini_medium_agent
                ),  # Registers UV-based MCP activities
            ],
            max_concurrent_activities=self.max_concurrent_activities,
            max_concurrent_workflow_tasks=self.max_concurrent_workflows,
            workflow_runner=UnsandboxedWorkflowRunner(),
        )

        self.logger.info(
            "Worker created with TemporalAgent using UV + persistent bundle storage"
        )
        return worker

    def _log_configuration(self):
        """Log worker configuration."""
        self.logger.info("=== Exp05 Temporal Worker Configuration ===")
        self.logger.info(f"Temporal Server: {self.temporal_host}")
        self.logger.info(f"Namespace: {self.temporal_namespace}")
        self.logger.info(f"Task Queue: {self.task_queue}")
        self.logger.info(f"Max Concurrent Activities: {self.max_concurrent_activities}")
        self.logger.info(f"Max Concurrent Workflows: {self.max_concurrent_workflows}")
        self.logger.info("")
        self.logger.info("Registered Workflows:")
        self.logger.info("  - GitHubAnalysisWorkflow (supports v1 and v2)")
        self.logger.info("")
        self.logger.info("Registered Activities:")
        self.logger.info("  - fetch_github_issue")
        self.logger.info("  - run_agent_analysis (for v1 agents)")
        self.logger.info("")
        self.logger.info("TemporalAgents (v2 - with persistent bundle storage):")
        self.logger.info("  - gpt5_mini_medium (UV + shared /tmp/mcp-bundles/)")
        self.logger.info("  - MCP server manages multiple bundles in shared storage")
        self.logger.info("===========================================")

    async def start(self):
        """Start the worker."""
        self.logger.info("🚀 Starting Exp05 Temporal Worker...")

        # Initialize Phoenix observability FIRST (before any Temporal operations)
        init_observability(project_name="gh-analysis")

        self._setup_signal_handlers()

        try:
            self.client = await self._connect_to_temporal()
            self.worker = self._create_worker(self.client)
            self._log_configuration()

            self.logger.info("✅ Worker is ready")
            self.logger.info(f"📋 Listening on task queue: {self.task_queue}")
            self.logger.info("")
            self.logger.info("Press Ctrl+C to stop...")

            # Run worker with shutdown handling
            worker_task = asyncio.create_task(self.worker.run())
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())

            done, pending = await asyncio.wait(
                [worker_task, shutdown_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except KeyboardInterrupt:
            self.logger.info("🛑 Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"❌ Worker failed: {e}")
            raise
        finally:
            # Flush traces before shutdown
            self.logger.info("📤 Flushing traces...")
            flush_traces(timeout_seconds=5)
            self.logger.info("✅ Worker shutdown complete")


async def main():
    """Main entry point."""
    worker = Exp05Worker()
    try:
        await worker.start()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


def run_worker():
    """Entry point for running the worker."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_worker()
