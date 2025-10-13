#!/usr/bin/env python3
"""Test script for gh-analysis Temporal workflow.

Run after start_services.py is running.
"""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from src.gh_analysis.temporal.models import AnalysisRequest
from src.gh_analysis.workflows import GitHubAnalysisWorkflow


async def main():
    """Run single workflow test."""
    print("📡 Connecting to Temporal...")

    client = await Client.connect(
        "localhost:7233",
        namespace="default",
        data_converter=pydantic_data_converter,
    )
    print("✅ Connected to Temporal")

    # Test with exp05's test case
    request = AnalysisRequest(
        repo_owner="replicated-collab",
        repo_name="knime-replicated",
        issue_number=358,
        agent_type="gpt5_mini_medium",
        comment_limit=2,
    )

    workflow_id = f"gh-analysis-test-{request.repo_owner}-{request.repo_name}-{request.issue_number}"

    print(f"\n🚀 Starting workflow: {workflow_id}")
    print(f"   Issue: {request.repo_owner}/{request.repo_name}#{request.issue_number}")

    handle = await client.start_workflow(
        GitHubAnalysisWorkflow.run,
        request,
        id=workflow_id,
        task_queue="gh-analysis-queue",
    )

    print("📋 Workflow started")
    print(f"🔗 View in UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")

    print("\n⏳ Waiting for completion...")
    while True:
        try:
            status = await handle.query(GitHubAnalysisWorkflow.get_status)
            elapsed = status.get("elapsed_seconds", 0)
            print(f"\r   ⏱️  Elapsed: {elapsed:.0f}s", end="", flush=True)

            result = await asyncio.wait_for(handle.result(), timeout=2.0)
            break
        except asyncio.TimeoutError:
            await asyncio.sleep(2)

    print("\n\n✅ Workflow completed!")
    print(f"   Total time: {result.execution_time_seconds:.2f}s")
    print("\n📊 Analysis Result:")
    print(f"   Status: {result.analysis.status}")
    if hasattr(result.analysis, "root_cause"):
        print(f"   Root Cause: {result.analysis.root_cause[:150]}...")

    print("\n🎉 Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
