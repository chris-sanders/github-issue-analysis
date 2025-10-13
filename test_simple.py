#!/usr/bin/env python3
"""Simple test - connect to running services and run workflow."""

import asyncio
import time

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.gh_analysis.temporal.models import AnalysisRequest
from src.gh_analysis.workflows import GitHubAnalysisWorkflow


async def main():
    print("📡 Connecting to Temporal...")

    client = await Client.connect(
        "localhost:7233",
        namespace="default",
        data_converter=pydantic_data_converter,
    )
    print("✅ Connected")

    request = AnalysisRequest(
        repo_owner="replicated-collab",
        repo_name="knime-replicated",
        issue_number=358,
        agent_type="gpt5_mini_medium",
        comment_limit=2,
    )

    timestamp = int(time.time())
    workflow_id = f"test-{request.repo_owner}-{request.repo_name}-{request.issue_number}-{timestamp}"

    print(f"\n🚀 Starting workflow: {workflow_id}")

    handle = await client.start_workflow(
        GitHubAnalysisWorkflow.run,
        request,
        id=workflow_id,
        task_queue="gh-analysis-queue",
    )

    print("📋 Workflow started")
    print(f"🔗 http://localhost:8233/namespaces/default/workflows/{workflow_id}")
    print("\n⏳ Waiting for completion...\n")

    result = await handle.result()

    print(f"✅ Complete ({result.execution_time_seconds:.1f}s)")
    print(f"Status: {result.analysis.status}")
    if hasattr(result.analysis, "root_cause"):
        print(f"Root Cause: {result.analysis.root_cause[:200]}...")


if __name__ == "__main__":
    asyncio.run(main())
