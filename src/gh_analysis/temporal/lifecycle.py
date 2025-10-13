"""CLI-managed Temporal server and worker lifecycle.

Allows single-command CLI usage by managing Temporal infrastructure automatically.
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Any

from pydantic_ai.durable_exec.temporal import PydanticAIPlugin
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

logger = logging.getLogger(__name__)


class TemporalManager:
    """Manages Temporal server and worker lifecycle for CLI usage."""

    def __init__(
        self,
        task_queue: str = "gh-analysis-queue",
        temporal_host: str = "localhost:7233",
        namespace: str = "default",
    ):
        self.task_queue = task_queue
        self.temporal_host = temporal_host
        self.namespace = namespace

        self.server_process: subprocess.Popen | None = None
        self.worker_process: subprocess.Popen | None = None
        self.client: Client | None = None

    async def __aenter__(self) -> "TemporalManager":
        """Start Temporal server and worker."""
        logger.info("🚀 Starting Temporal infrastructure...")

        await self._start_temporal_server()
        await self._connect_client()
        self._start_worker_subprocess()

        logger.info("✅ Temporal infrastructure ready")
        return self

    async def __aexit__(self, *args):
        """Shutdown Temporal server and worker."""
        logger.info("🛑 Shutting down...")

        if self.worker_process:
            self.worker_process.terminate()
            try:
                self.worker_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.worker_process.kill()
            logger.info("✓ Worker stopped")

        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            logger.info("✓ Temporal stopped")

    async def _start_temporal_server(self):
        """Start Temporal dev server."""
        logger.info("Starting Temporal server...")

        self.server_process = subprocess.Popen(
            ["temporal", "server", "start-dev", "--ip", "0.0.0.0", "--port", "7233"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for Temporal to be actually ready
        await asyncio.sleep(5)

        # Poll until connection works
        for i in range(30):
            try:
                test_proc = subprocess.Popen(
                    ["temporal", "operator", "namespace", "list"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                test_proc.wait()
                if test_proc.returncode == 0:
                    logger.info("✓ Temporal server ready")
                    return
            except:
                pass
            await asyncio.sleep(1)

        logger.warning("Temporal may not be ready, continuing anyway...")

    async def _connect_client(self):
        """Connect Temporal client."""
        logger.info("Connecting to Temporal...")

        self.client = await Client.connect(
            self.temporal_host,
            namespace=self.namespace,
            data_converter=pydantic_data_converter,
            plugins=[PydanticAIPlugin()],
        )

        logger.info("✓ Connected")

    def _start_worker_subprocess(self):
        """Start worker as subprocess."""
        logger.info("Starting worker (subprocess)...")

        self.worker_process = subprocess.Popen(
            ["uv", "run", "python", "-m", "gh_analysis.workers.main_worker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )

        # Give worker time to connect and register
        time.sleep(5)

        logger.info("✓ Worker subprocess started")
