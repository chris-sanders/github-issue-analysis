"""Troubleshooting CLI command using Temporal workflows."""

import asyncio

import typer
from rich.console import Console

from gh_analysis.temporal import AnalysisRequest
from gh_analysis.temporal.lifecycle import TemporalManager
from gh_analysis.workflows import GitHubAnalysisWorkflow

app = typer.Typer(help="Troubleshoot GitHub issues with AI (Temporal)")
console = Console()


@app.command()
def run(
    org: str = typer.Option(..., "--org", "-o", help="GitHub organization"),
    repo: str = typer.Option(..., "--repo", "-r", help="Repository name"),
    issue: int = typer.Option(..., "--issue", "-n", help="Issue number"),
    agent: str = typer.Option("gpt5_mini_medium", "--agent", "-a", help="Agent type"),
    comment_limit: int = typer.Option(None, "--comment-limit", "-c", help="Limit comments"),
) -> None:
    """Run troubleshooting via Temporal (single command: start → run → stop)."""
    asyncio.run(_run(org, repo, issue, agent, comment_limit))


async def _run(org: str, repo: str, issue: int, agent: str, comment_limit: int | None) -> None:
    """Execute troubleshooting."""
    console.print(f"\n[cyan]🔍 Troubleshooting {org}/{repo}#{issue}[/cyan]\n")

    request = AnalysisRequest(
        repo_owner=org,
        repo_name=repo,
        issue_number=issue,
        agent_type=agent,
        comment_limit=comment_limit,
    )

    workflow_id = f"troubleshoot-{org}-{repo}-{issue}"

    async with TemporalManager() as manager:
        console.print("⏳ Running workflow...")

        handle = await manager.client.start_workflow(
            GitHubAnalysisWorkflow.run,
            request,
            id=workflow_id,
            task_queue="gh-analysis-queue",
        )

        result = await handle.result()

        console.print(f"\n[green]✅ Complete ({result.execution_time_seconds:.1f}s)[/green]\n")
        console.print(f"Status: {result.analysis.status}")
        if hasattr(result.analysis, "root_cause"):
            console.print(f"Root Cause: {result.analysis.root_cause[:200]}...")
        console.print()
