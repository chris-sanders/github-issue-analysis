"""Store case summaries in Snowflake for closed issues."""

import asyncio
import json
from datetime import datetime
from typing import Any, Optional

import typer
from rich.console import Console

from ..github_client import GitHubClient
from ..runners.utils import checks
from ..runners.utils.snowflake_dev_client import SnowflakeDevClient

app = typer.Typer(
    help="Store case summaries in Snowflake",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def parse_github_url(url: str) -> tuple[str, str, int]:
    """Parse GitHub issue URL into org, repo, and issue number."""
    # Format: https://github.com/org/repo/issues/123
    parts = url.rstrip("/").split("/")
    if len(parts) < 7 or parts[-2] != "issues":
        raise ValueError(f"Invalid GitHub issue URL: {url}")

    org = parts[-4]
    repo = parts[-3]
    issue_number = int(parts[-1])

    return org, repo, issue_number


async def fetch_and_format_issue(org: str, repo: str, issue_number: int) -> dict:
    """Fetch issue from GitHub and format for processing."""
    console.print(f"📥 Fetching issue: {org}/{repo}#{issue_number}")

    github_client = GitHubClient()

    # Fetch issue with all details (includes comments)
    github_issue = await asyncio.to_thread(
        github_client.get_issue, org, repo, issue_number
    )

    # Format as expected by MultiSummaryRunner (matches context-experiments format)
    formatted = {
        "number": github_issue.number,
        "title": github_issue.title,
        "body": github_issue.body or "",
        "labels": [{"name": label.name} for label in github_issue.labels],
        "state": github_issue.state,
        "created_at": github_issue.created_at.isoformat()
        if github_issue.created_at
        else None,
        "closed_at": None,  # GitHubIssue doesn't track closed_at, only updated_at
        "html_url": f"https://github.com/{org}/{repo}/issues/{issue_number}",
        "comments": [
            {
                "user": {"login": comment.user.login},
                "body": comment.body,
                "created_at": comment.created_at.isoformat()
                if comment.created_at
                else None,
            }
            for comment in github_issue.comments
        ],
    }

    return formatted


async def generate_summary(issue_data: dict) -> dict:
    """Generate summary using vendored MultiSummaryRunner."""
    console.print(f"🤖 Generating summary using MultiSummaryRunner...")

    # Import MultiSummaryRunner from vendored code
    from ..runners.summary import MultiSummaryRunner

    # Create runner and generate summary
    runner = MultiSummaryRunner()
    summary_result = await runner.analyze(issue_data)

    # Check for error output
    if isinstance(summary_result, str) and summary_result.startswith("❌"):
        raise RuntimeError(f"Summary generation failed: {summary_result}")

    # Convert Pydantic model to dict if needed
    if hasattr(summary_result, "model_dump"):
        summary_dict = summary_result.model_dump()
    elif hasattr(summary_result, "dict"):
        summary_dict = summary_result.dict()
    else:
        summary_dict = summary_result

    return summary_dict


def save_to_snowflake(
    org: str,
    repo: str,
    issue_number: int,
    summary: dict,
    runner_name: str,
    model_name: str,
) -> None:
    """Save summary to Snowflake DEV_CRE.EXP05.SUMMARIES table."""
    console.print("❄️ Connecting to Snowflake...")

    # Initialize Snowflake client for EXP05 schema
    sf_client = SnowflakeDevClient(schema="EXP05")

    # Create table DDL (matches context-experiments schema)
    table_ddl = """
    CREATE TABLE IF NOT EXISTS SUMMARIES (
        ORG_NAME VARCHAR(255) NOT NULL,
        REPO_NAME VARCHAR(255) NOT NULL,
        ISSUE_NUMBER INT NOT NULL,
        SUMMARY_TIMESTAMP TIMESTAMP_NTZ NOT NULL,
        PRODUCT ARRAY,
        SYMPTOMS ARRAY,
        EVIDENCE ARRAY,
        CAUSE VARCHAR(16777216),
        FIX ARRAY,
        CONFIDENCE FLOAT,
        RUNNER_NAME VARCHAR(255),
        MODEL_NAME VARCHAR(255),
        CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (ORG_NAME, REPO_NAME, ISSUE_NUMBER)
    )
    """

    # Create table if needed
    sf_client.create_table("DEV_CRE.EXP05.SUMMARIES", table_ddl)

    # Prepare record for insertion
    record = {
        "ORG_NAME": org,
        "REPO_NAME": repo,
        "ISSUE_NUMBER": issue_number,
        "SUMMARY_TIMESTAMP": datetime.utcnow(),
        "PRODUCT": summary.get("product", []),
        "SYMPTOMS": summary.get("symptoms", []),
        "EVIDENCE": summary.get("evidence", []),
        "CAUSE": summary.get("cause", ""),
        "FIX": summary.get("fix", []),
        "CONFIDENCE": float(summary.get("confidence", 0.5)),
        "RUNNER_NAME": runner_name,
        "MODEL_NAME": model_name,
    }

    # Use upsert to handle re-runs
    rows_affected = sf_client.upsert_data(
        "DEV_CRE.EXP05.SUMMARIES", [record], ["ORG_NAME", "REPO_NAME", "ISSUE_NUMBER"]
    )

    console.print(f"✅ Summary saved to Snowflake ({rows_affected} rows affected)")


@app.command()
def store(
    url: str = typer.Option(
        ...,
        "--url",
        "-u",
        help="GitHub issue URL to process",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate summary but don't save to Snowflake",
    ),
) -> None:
    """Generate and store a case summary in Snowflake using MultiSummaryRunner."""

    try:
        # Parse URL
        org, repo, issue_number = parse_github_url(url)
        console.print(f"🔍 Processing: {org}/{repo}#{issue_number}")

        # Run async operations
        async def process():
            # Check environment
            if not dry_run:
                check_functions = [checks.snowflake]
                if not await checks.run_checks(check_functions):
                    console.print("[red]❌ Snowflake environment check failed[/red]")
                    raise typer.Exit(1)

            # Fetch issue
            issue_data = await fetch_and_format_issue(org, repo, issue_number)

            # Generate summary
            summary = await generate_summary(issue_data)

            if dry_run:
                console.print("\n[yellow]🔍 DRY RUN - Summary Generated:[/yellow]")
                console.print(json.dumps(summary, indent=2))
                console.print(
                    "\n[yellow]Would save to DEV_CRE.EXP05.SUMMARIES[/yellow]"
                )
            else:
                # Save to Snowflake
                save_to_snowflake(
                    org=org,
                    repo=repo,
                    issue_number=issue_number,
                    summary=summary,
                    runner_name="MultiSummaryRunner",
                    model_name="multi-agent",
                )

                console.print(
                    f"\n✅ Successfully processed {org}/{repo}#{issue_number}"
                )

        # Run the async function
        asyncio.run(process())

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
