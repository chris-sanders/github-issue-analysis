"""CLI-managed Temporal server and worker lifecycle.

Allows single-command CLI usage by managing Temporal infrastructure automatically.
"""

import asyncio
import logging
import subprocess
import time
from typing import Any

import httpx
from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

logger = logging.getLogger(__name__)


class TemporalManager:
    """Manages Temporal server and worker lifecycle for CLI usage.

    This allows CLI commands to be self-contained - users don't need to
    manually start Temporal server or workers. The manager:
    1. Starts Temporal dev server as subprocess
    2. Waits for server to be ready
    3. Starts worker in background task (same process)
    4. Provides client for workflow execution
    5. Cleanly shuts down worker and server when done

    Usage:
        async with TemporalManager(workflows=[MyWorkflow], activities=[my_activity]) as tm:
            result = await tm.execute_workflow(MyWorkflow.run, args=(...))
    """

    def __init__(
        self,
        workflows: list[type] | None = None,
        activities: list[Any] | None = None,
        task_queue: str = "gh-analysis-queue",
        temporal_host: str = "localhost:7233",
        namespace: str = "default",
    ):
        """Initialize Temporal manager.

        Args:
            workflows: List of workflow classes to register
            activities: List of activity functions to register
            task_queue: Temporal task queue name
            temporal_host: Temporal server address
            namespace: Temporal namespace
        """
        self.workflows = workflows or []
        self.activities = activities or []
        self.task_queue = task_queue
        self.temporal_host = temporal_host
        self.namespace = namespace

        self.server_process: subprocess.Popen | None = None
        self.worker: Worker | None = None
        self.worker_task: asyncio.Task | None = None
        self.client: Client | None = None

    async def __aenter__(self) -> "TemporalManager":
        """Start Temporal server and worker."""
        # Suppress noisy logging from MCP server and Temporal
        import logging as log

        log.getLogger("lifecycle").setLevel(log.ERROR)
        log.getLogger("bundle").setLevel(log.ERROR)
        log.getLogger("server").setLevel(log.ERROR)
        log.getLogger("temporalio").setLevel(log.WARNING)

        logger.info("🚀 Starting CLI-managed Temporal infrastructure...")

        # Step 1: Start Temporal dev server
        await self._start_temporal_server()

        # Step 2: Connect client
        await self._connect_client()

        # Step 3: Start worker
        await self._start_worker()

        logger.info("✅ Temporal infrastructure ready")
        return self

    async def __aexit__(self, *args):
        """Shutdown Temporal server and worker."""
        logger.info("🛑 Shutting down Temporal infrastructure...")

        # Step 1: Cancel worker
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
            logger.info("✓ Worker stopped")

        # Step 2: Shutdown Temporal server
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()
            logger.info("✓ Temporal server stopped")

        logger.info("✅ Temporal infrastructure shutdown complete")

    async def _start_temporal_server(self):
        """Start Temporal dev server as subprocess."""
        logger.info("Starting Temporal dev server...")

        # Start server in background with output suppressed
        self.server_process = subprocess.Popen(
            ["temporal", "server", "start-dev", "--ip", "0.0.0.0", "--port", "7233"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for server to be ready
        await self._wait_for_server_ready()
        logger.info("✓ Temporal server ready")

    async def _wait_for_server_ready(self, timeout: float = 30.0):
        """Poll Temporal server until ready."""
        import socket

        start = time.time()

        # Give server a moment to start
        await asyncio.sleep(2.0)

        # Poll port until it's open
        while time.time() - start < timeout:
            try:
                # Try to connect to port 7233
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                result = sock.connect_ex(("localhost", 7233))
                sock.close()

                if result == 0:  # Port is open
                    # Give it another second for HTTP to be ready
                    await asyncio.sleep(1.0)
                    return
            except Exception:
                pass

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Temporal server not ready after {timeout}s")

    async def _connect_client(self):
        """Connect Temporal client."""
        logger.info(f"Connecting to Temporal at {self.temporal_host}...")

        self.client = await Client.connect(
            self.temporal_host,
            namespace=self.namespace,
            data_converter=pydantic_data_converter,
            plugins=[PydanticAIPlugin()],  # Required for TemporalAgent
        )

        logger.info("✓ Connected to Temporal with PydanticAI plugin")

    async def _start_worker(self):
        """Start worker in background task."""
        if not self.client:
            raise RuntimeError("Client not connected")

        logger.info(f"Starting worker on task queue: {self.task_queue}")

        # Use worker factory if no workflows/activities provided
        if not self.workflows and not self.activities:
            from gh_analysis.workers.main_worker import create_worker

            self.worker = create_worker(self.client, self.task_queue)
        else:
            self.worker = Worker(
                self.client,
                task_queue=self.task_queue,
                workflows=self.workflows,
                activities=self.activities,
            )

        # Start worker in background
        self.worker_task = asyncio.create_task(self.worker.run())

        # Give worker time to start
        await asyncio.sleep(1.0)

        logger.info("✓ Worker started")

    async def execute_workflow(
        self,
        workflow_class: type,
        args: tuple[Any, ...],
        workflow_id: str | None = None,
    ) -> Any:
        """Execute a workflow and wait for result.

        Args:
            workflow_class: Workflow class to execute
            args: Workflow arguments
            workflow_id: Optional workflow ID (auto-generated if not provided)

        Returns:
            Workflow result
        """
        if not self.client:
            raise RuntimeError("Client not connected")

        result = await self.client.execute_workflow(
            workflow_class.run,
            args=args,
            id=workflow_id or f"cli-{time.time()}",
            task_queue=self.task_queue,
        )

        return result
