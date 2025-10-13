"""Troubleshooting CLI command using Temporal workflows."""

import asyncio
import subprocess
import sys

import typer
from rich.console import Console

from gh_analysis.temporal.models import AnalysisRequest

app = typer.Typer(help="Troubleshoot GitHub issues with AI (Temporal)")
console = Console()


@app.command()
def run(
    org: str = typer.Option(..., "--org", "-o", help="GitHub organization"),
    repo: str = typer.Option(..., "--repo", "-r", help="Repository name"),
    issue: int = typer.Option(..., "--issue", "-n", help="Issue number"),
    agent: str = typer.Option("gpt5_mini_medium", "--agent", "-a", help="Agent type"),
    comment_limit: int = typer.Option(
        None, "--comment-limit", "-c", help="Limit comments"
    ),
) -> None:
    """Run troubleshooting analysis via Temporal workflow.

    This starts all services inline, runs the workflow, and shuts down cleanly.
    """
    asyncio.run(_run_troubleshoot(org, repo, issue, agent, comment_limit))


async def _run_troubleshoot(
    org: str, repo: str, issue: int, agent: str, comment_limit: int | None
) -> None:
    """Execute troubleshooting with inline service management."""
    from temporalio.client import Client
    from temporalio.contrib.pydantic import pydantic_data_converter

    console.print(
        f"\n[cyan]🔍 Troubleshooting {org}/{repo}#{issue} with {agent}[/cyan]\n"
    )

    # Start services
    console.print("🚀 Starting services...")
    services = subprocess.Popen(
        ["uv", "run", "python", "-m", "gh_analysis.temporal.start_services"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    await asyncio.sleep(15)  # Wait for services
    console.print("✓ Services ready\n")

    try:
        # Connect and run workflow
        from gh_analysis.workflows import GitHubAnalysisWorkflow

        client = await Client.connect(
            "localhost:7233",
            namespace="default",
            data_converter=pydantic_data_converter,
        )

        request = AnalysisRequest(
            repo_owner=org,
            repo_name=repo,
            issue_number=issue,
            agent_type=agent,
            comment_limit=comment_limit,
        )

        workflow_id = f"troubleshoot-{org}-{repo}-{issue}"
        console.print(f"📋 Starting workflow: {workflow_id}\n")

        handle = await client.start_workflow(
            GitHubAnalysisWorkflow.run,
            request,
            id=workflow_id,
            task_queue="gh-analysis-queue",
        )

        console.print("⏳ Waiting for analysis...")
        result = await handle.result()

        console.print(
            f"\n[green]✅ Complete ({result.execution_time_seconds:.1f}s)[/green]\n"
        )
        console.print(f"Status: {result.analysis.status}")
        if hasattr(result.analysis, "root_cause"):
            console.print(f"Root Cause: {result.analysis.root_cause[:200]}...")
        console.print()

    finally:
        # Shutdown services
        console.print("🛑 Shutting down services...")
        services.terminate()
        try:
            services.wait(timeout=5)
        except subprocess.TimeoutExpired:
            services.kill()
        console.print("✓ Services stopped\n")
