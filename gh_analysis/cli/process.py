"""AI processing commands for GitHub issue analysis."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from pydantic_ai.settings import ModelSettings
from rich.console import Console
from rich.table import Table

from ..ai.settings_validator import get_valid_settings_help, validate_settings
from ..recommendation.manager import RecommendationManager

app = typer.Typer(
    help="AI processing commands",
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


@app.command()
def show_settings() -> None:
    """Display available model settings that can be configured."""
    # Use Pydantic's introspection on ModelSettings
    table = Table(title="Available Model Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Description", style="yellow")

    # Try to get field info from ModelSettings dynamically
    try:
        # Check if ModelSettings has schema method (Pydantic v2)
        if hasattr(ModelSettings, "model_json_schema"):
            schema = ModelSettings.model_json_schema()
            properties = schema.get("properties", {})
            for field_name, field_info in properties.items():
                field_type = field_info.get("type", "Any")
                if "anyOf" in field_info:
                    types = [
                        t.get("type", "") for t in field_info["anyOf"] if "type" in t
                    ]
                    field_type = " | ".join(types) if types else "Any"
                description = field_info.get("description", "No description available")
                table.add_row(field_name, field_type, description)
        else:
            # Fallback message if we can't introspect
            console.print(
                "[yellow]Unable to introspect ModelSettings dynamically.[/yellow]"
            )
            console.print(
                "Common settings: temperature, max_tokens, "
                "reasoning_effort, top_p, timeout, seed"
            )
            return
    except Exception as e:
        console.print(f"[yellow]Error introspecting ModelSettings: {e}[/yellow]")
        console.print(
            "Common settings: temperature, max_tokens, "
            "reasoning_effort, top_p, timeout, seed"
        )
        return

    console.print(table)

    # Add usage example
    console.print("\n[bold]Usage Example:[/bold]")
    console.print(
        "github-analysis process product-labeling --setting temperature=0.5 "
        "--setting reasoning_effort=high"
    )

    # Add model-specific notes
    console.print("\n[bold]Notes:[/bold]")
    console.print("• Not all settings are supported by all models")
    console.print("• PydanticAI will validate settings when you run the command")
    console.print("• Invalid settings will result in clear error messages")


@app.command()
def product_labeling(
    org: str = typer.Option(
        ...,
        "--org",
        "-o",
        help="GitHub organization name",
        rich_help_panel="Target Selection",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub repository name",
        rich_help_panel="Target Selection",
    ),
    issue_number: int | None = typer.Option(
        None,
        "--issue-number",
        "-i",
        help="Specific issue number",
        rich_help_panel="Target Selection",
    ),
    model: str = typer.Option(
        "openai:o4-mini",
        "--model",
        "-m",
        help="AI model to use",
        rich_help_panel="AI Configuration",
    ),
    settings: list[str] = typer.Option(
        [],
        "--setting",
        help="Model settings as key=value (e.g., --setting temperature=0.7)",
        rich_help_panel="AI Configuration",
    ),
    include_images: bool = typer.Option(
        True,
        "--include-images/--no-include-images",
        help="Include image analysis",
        rich_help_panel="Processing Options",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Preview changes without applying them",
        rich_help_panel="Processing Options",
    ),
    reprocess: bool = typer.Option(
        False,
        "--reprocess",
        help="Force reprocessing of items already processed",
        rich_help_panel="Processing Options",
    ),
    concurrency: int = typer.Option(
        20,
        "--concurrency",
        "-c",
        help="Number of concurrent processing tasks",
        rich_help_panel="Processing Options",
    ),
) -> None:
    """Analyze GitHub issues for product labeling recommendations.

    This command processes GitHub issues using AI to generate product labeling
    recommendations. You can target specific issues, repositories, or entire
    organizations. Processing is done concurrently for better performance.

    Examples:

        # Process a specific issue
        github-analysis process product-labeling --org myorg --repo myrepo \\
            --issue-number 123

        # Process all issues in a repository
        github-analysis process product-labeling --org myorg --repo myrepo

        # Process all issues in an organization
        github-analysis process product-labeling --org myorg

        # Process with custom concurrency (default: 20)
        github-analysis process product-labeling --org myorg --repo myrepo \\
            --concurrency 10

        # Preview changes without processing
        github-analysis process product-labeling --org myorg --repo myrepo --dry-run
    """
    try:
        # Parse settings into dict
        model_settings = {}
        for setting in settings:
            if "=" not in setting:
                console.print(
                    f"[red]❌ Invalid setting format '{setting}'. "
                    "Use key=value format.[/red]"
                )
                raise typer.Exit(1)
            key, value = setting.split("=", 1)
            # Try to parse as number if possible
            parsed_value: Any = value
            try:
                num_value = float(value)
                if num_value.is_integer():
                    parsed_value = int(num_value)
                else:
                    parsed_value = num_value
            except ValueError:
                pass  # Keep as string
            model_settings[key] = parsed_value

        # Validate settings BEFORE processing
        errors = validate_settings(model, model_settings)
        if errors:
            console.print("[red]❌ Invalid settings:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            console.print(f"\n{get_valid_settings_help(model)}")
            raise typer.Exit(1)

        asyncio.run(
            _run_product_labeling(
                org,
                repo,
                issue_number,
                model,
                model_settings,
                include_images,
                dry_run,
                reprocess,
                concurrency,
            )
        )
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)


async def _run_product_labeling(
    org: str,
    repo: str | None,
    issue_number: int | None,
    model: str,
    model_settings: dict[str, Any],
    include_images: bool,
    dry_run: bool,
    reprocess: bool,
    concurrency: int,
) -> None:
    """Run product labeling analysis."""

    # Find issue files to process
    # Allow override via environment variable for testing
    base_data_dir = Path(os.environ.get("GITHUB_ANALYSIS_DATA_DIR", "data"))
    data_dir = base_data_dir / "issues"
    if not data_dir.exists():
        console.print(
            "[red]No issues directory found. Run collect command first.[/red]"
        )
        return

    issue_files = []
    if issue_number:
        # Validate that repo is provided for specific issue
        if not repo:
            console.print(
                "[red]Error: --repo is required when specifying --issue-number[/red]"
            )
            return

        # Find specific issue file with org/repo/issue pattern
        expected_filename = f"{org}_{repo}_issue_{issue_number}.json"
        expected_path = data_dir / expected_filename

        if not expected_path.exists():
            console.print(
                f"[red]Issue #{issue_number} not found for {org}/{repo}.[/red]"
            )
            console.print(f"[red]Expected file: {expected_filename}[/red]")
            return
        issue_files = [expected_path]
    elif org and repo:
        # Process all issues for specific org/repo
        pattern = f"{org}_{repo}_issue_*.json"
        issue_files = list(data_dir.glob(pattern))
        if not issue_files:
            console.print(f"[red]No issues found for {org}/{repo}.[/red]")
            return
    elif org:
        # Process all issues for specific org (across all repos)
        pattern = f"{org}_*_issue_*.json"
        issue_files = list(data_dir.glob(pattern))
        if not issue_files:
            console.print(f"[red]No issues found for organization {org}.[/red]")
            return
    else:
        # Process all issues
        issue_files = list(data_dir.glob("*_issue_*.json"))

    if not issue_files:
        console.print("[yellow]No issue files found to process.[/yellow]")
        return

    console.print(f"[blue]Found {len(issue_files)} issue(s) to process[/blue]")

    if dry_run:
        for file_path in issue_files:
            console.print(f"Would process: {file_path.name}")
        return

    # Show configuration
    console.print(f"[blue]Using model: {model}[/blue]")
    if model_settings:
        console.print(f"[blue]Model settings: {model_settings}[/blue]")
    console.print(
        f"[blue]Image processing: {'enabled' if include_images else 'disabled'}[/blue]"
    )

    # Initialize recommendation manager for filtering
    recommendation_manager = RecommendationManager(base_data_dir)

    # Process each issue concurrently
    results_dir = base_data_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(concurrency)

    # Process files concurrently
    tasks = []
    for file_path in issue_files:
        task = asyncio.create_task(
            _process_single_issue(
                file_path,
                recommendation_manager,
                results_dir,
                model,
                model_settings,
                include_images,
                reprocess,
                semaphore,
            )
        )
        tasks.append(task)

    # Wait for all tasks to complete and collect results
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count successes and failures
    processed_count = 0
    skipped_count = 0
    failed_count = 0

    for result in results:
        if isinstance(result, Exception):
            failed_count += 1
        elif result == "processed":
            processed_count += 1
        elif result == "skipped":
            skipped_count += 1

    # Show summary
    total_count = len(issue_files)
    console.print(
        f"\n[blue]Summary: Processed {processed_count}/{total_count} issues "
        f"({skipped_count} skipped, {failed_count} failed)[/blue]"
    )


async def _process_single_issue(
    file_path: Path,
    recommendation_manager: RecommendationManager,
    results_dir: Path,
    model: str,
    model_settings: dict[str, Any],
    include_images: bool,
    reprocess: bool,
    semaphore: asyncio.Semaphore,
) -> str:
    """Process a single issue file.

    Returns:
        "processed" if successful, "skipped" if skipped, raises exception if failed
    """
    async with semaphore:
        try:
            # Load issue data to check if we should process it
            with open(file_path) as f:
                issue_data = json.load(f)

            # Check if issue should be reprocessed
            issue_org = issue_data["org"]
            issue_repo = issue_data["repo"]
            issue_num = issue_data["issue"]["number"]

            if not recommendation_manager.should_reprocess_issue(
                issue_org, issue_repo, issue_num, reprocess
            ):
                console.print(
                    f"[yellow]Skipping {file_path.name} - already reviewed "
                    "(use --reprocess to override)[/yellow]"
                )
                return "skipped"

            console.print(f"Processing {file_path.name}...")

            # Check for images if enabled
            if include_images:
                attachment_count = len(
                    [
                        att
                        for att in issue_data["issue"].get("attachments", [])
                        if att.get("downloaded")
                        and att.get("content_type", "").startswith("image/")
                    ]
                )
                if attachment_count > 0:
                    console.print(f"  Found {attachment_count} image(s) to analyze")

            # Use runner instead of direct agent
            from ..runners import get_runner

            runner = get_runner(
                "product-labeling", model_name=model, model_settings=model_settings
            )

            # Analyze using runner
            result: Any = await runner.analyze(issue_data)

            # Save result
            result_file = results_dir / f"{file_path.stem}_product-labeling.json"
            result_data = {
                "issue_reference": {
                    "file_path": str(file_path),
                    "org": issue_data["org"],
                    "repo": issue_data["repo"],
                    "issue_number": issue_data["issue"]["number"],
                },
                "processor": {
                    "name": "product-labeling",
                    "version": "3.0.0",  # Simplified agent interface version
                    "model": model,
                    "include_images": include_images,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                },
                "analysis": result.model_dump(),
            }

            with open(result_file, "w") as f:
                json.dump(result_data, f, indent=2)

            console.print(f"[green]✓ Saved results to {result_file.name}[/green]")
            return "processed"

        except Exception as e:
            console.print(f"[red]✗ Failed to process {file_path.name}: {e}[/red]")
            raise


@app.command()
def troubleshoot(
    org: str | None = typer.Option(
        None,
        "--org",
        "-o",
        help="GitHub organization name (or use --url)",
        rich_help_panel="Target Selection",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub repository name (or use --url)",
        rich_help_panel="Target Selection",
    ),
    issue_number: int | None = typer.Option(
        None,
        "--issue-number",
        "-i",
        help="Issue number to analyze (or use --url)",
        rich_help_panel="Target Selection",
    ),
    url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="GitHub issue URL (alternative to org/repo/issue-number)",
        rich_help_panel="Target Selection",
    ),
    agent: str = typer.Option(
        "gpt5_mini_medium_mt",
        "--agent",
        "-a",
        help="Troubleshoot agent to use (gpt5_mini_medium, gpt5_mini_high, "
        "gpt5_medium, gpt5_high, claude_sonnet_mt, claude_sonnet_4_5_mt, "
        "gpt5_mini_medium_mt, gpt5_mini_high_mt, gpt5_medium_mt, gpt5_high_mt, "
        "gemini_25_pro_mt)",
        rich_help_panel="AI Configuration",
    ),
    include_images: bool = typer.Option(
        True,
        "--include-images/--no-include-images",
        help="Include image analysis",
        rich_help_panel="Processing Options",
    ),
    limit_comments: int | None = typer.Option(
        None,
        "--limit-comments",
        help="Limit number of comments to process (for large issues)",
        rich_help_panel="Processing Options",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Preview changes without applying them",
        rich_help_panel="Processing Options",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Enter interactive mode after analysis for follow-up questions",
        rich_help_panel="Processing Options",
    ),
    slack_notifications: bool = typer.Option(
        False,
        "--slack-notifications",
        help="Send Slack notifications when analysis completes",
        rich_help_panel="Notifications",
    ),
) -> None:
    """Analyze GitHub issues using advanced troubleshooting agents with MCP tools.

    This command provides comprehensive technical troubleshooting analysis using
    sophisticated AI agents with access to specialized troubleshooting tools.
    Currently supports single-issue analysis for in-depth investigation.

    Agents available:
    - gpt5_mini_medium_mt: GPT-5 Mini (medium reasoning) with memory+tools (default,
      balanced speed and enhanced analysis with historical case retrieval)
    - gpt5_mini_high_mt: GPT-5 Mini (high reasoning) with memory+tools (slower but more thorough)
    - claude_sonnet_mt: Claude Sonnet 4 with memory+tools (alternative enhanced option)
    - claude_sonnet_4_5_mt: Claude Sonnet 4.5 with memory+tools (latest model with extended thinking)
    - gpt5_mini_medium: GPT-5 Mini with medium reasoning (basic, no memory)
    - gpt5_mini_high: GPT-5 Mini with high reasoning (basic, no memory)
    - gpt5_medium: GPT-5 with medium reasoning (basic, no memory)
    - gpt5_high: GPT-5 with high reasoning (basic, no memory)
    
    Memory+Tool agents (*_mt) provide enhanced analysis with:
    - Historical case retrieval from similar resolved issues
    - Dynamic evidence search during analysis
    - Improved root cause identification accuracy

    Required environment variables:
    - SBCTL_TOKEN: Required for all agents (MCP tool access)
    - OPENAI_API_KEY: Required for gpt5_* agents
    - ANTHROPIC_API_KEY: Required for claude_* agents
    - GOOGLE_API_KEY: Required for gemini_* agents
    
    Additional requirements for Memory+Tool agents (*_mt):
    - SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH: For historical case retrieval

    Examples:

        # Analyze using GitHub URL (automatically downloads if needed)
        github-analysis process troubleshoot \
            --url https://github.com/myorg/myrepo/issues/123

        # Analyze a specific issue with org/repo/number
        github-analysis process troubleshoot --org myorg --repo myrepo \
            --issue-number 123

        # Use high-reasoning GPT-5 agent for complex issues
        github-analysis process troubleshoot \
            --url https://github.com/myorg/myrepo/issues/456 --agent gpt5_high

        # Limit comments for large issues (only affects processing, not download)
        github-analysis process troubleshoot \
            --url https://github.com/myorg/myrepo/issues/789 --limit-comments 2

        # Preview analysis without processing
        github-analysis process troubleshoot \
            --url https://github.com/myorg/myrepo/issues/123 --dry-run
    """
    try:
        asyncio.run(
            _run_troubleshoot(
                org,
                repo,
                issue_number,
                url,
                agent,
                include_images,
                limit_comments,
                dry_run,
                interactive,
                slack_notifications,
            )
        )
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)


async def _run_troubleshoot(
    org: str | None,
    repo: str | None,
    issue_number: int | None,
    url: str | None,
    agent_name: str,
    include_images: bool,
    limit_comments: int | None,
    dry_run: bool,
    interactive: bool,
    slack_notifications: bool,
) -> None:
    """Run troubleshooting analysis."""
    import re

    # Parse URL if provided
    if url:
        # Extract org, repo, issue_number from GitHub URL
        github_url_pattern = r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)"
        match = re.match(github_url_pattern, url)
        if not match:
            raise ValueError(f"Invalid GitHub issue URL: {url}")
        org, repo, issue_number_str = match.groups()
        issue_number = int(issue_number_str)
        console.print(f"[blue]Parsed URL:[/blue] {org}/{repo}#{issue_number}")
    elif not (org and repo and issue_number):
        raise ValueError(
            "Either --url must be provided, or all of --org, --repo, and "
            "--issue-number must be specified"
        )

    # Validate environment variables
    sbctl_token = os.environ.get("SBCTL_TOKEN")
    if not sbctl_token:
        console.print("[red]❌ SBCTL_TOKEN environment variable is required[/red]")
        console.print("[yellow]This token is needed for MCP tool access[/yellow]")
        return

    # Validate agent-specific API keys
    if agent_name in [
        "gpt5_mini_medium",
        "gpt5_mini_high",
        "gpt5_medium",
        "gpt5_high",
        "gpt5_mini_medium_mt",
        "gpt5_mini_high_mt",
        "gpt5_medium_mt",
        "gpt5_high_mt",
    ]:
        if not os.environ.get("OPENAI_API_KEY"):
            console.print(
                "[red]❌ OPENAI_API_KEY environment variable is required "
                "for GPT-5 and O3 agents[/red]"
            )
            return
    elif agent_name.startswith("claude_"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            console.print(
                "[red]❌ ANTHROPIC_API_KEY environment variable is required "
                "for Claude agents[/red]"
            )
            return
    elif agent_name.startswith("gemini_"):
        if not os.environ.get("GOOGLE_API_KEY"):
            console.print(
                "[red]❌ GOOGLE_API_KEY environment variable is required "
                "for Gemini agents[/red]"
            )
            return
    else:
        console.print(
            f"[red]❌ Unknown agent: {agent_name}. Available: "
            f"gpt5_mini_medium, gpt5_mini_high, gpt5_medium, gpt5_high, "
            f"claude_sonnet_mt, claude_sonnet_4_5_mt, gpt5_mini_medium_mt, "
            f"gpt5_mini_high_mt, gpt5_medium_mt, gpt5_high_mt, gemini_25_pro_mt[/red]"
        )
        return

    # Validate Slack configuration if notifications are enabled
    if slack_notifications:
        from ..slack.config import SlackConfig

        slack_config = SlackConfig()
        if not slack_config.is_configured():
            console.print(
                "[red]❌ SLACK_BOT_TOKEN and SLACK_USER_TOKEN environment variables are required "
                "for Slack notifications[/red]"
            )
            console.print(
                "[yellow]SLACK_BOT_TOKEN: For posting messages (bot token with chat:write scope)[/yellow]"
            )
            console.print(
                "[yellow]SLACK_USER_TOKEN: For searching messages (user token with search:read scope)[/yellow]"
            )
            console.print(
                "[yellow]To disable notifications, remove --slack-notifications flag[/yellow]"
            )
            return

    # Validate that specific issue is provided (currently only supports single issue)
    if not issue_number:
        console.print(
            "[red]❌ --issue-number is required for troubleshoot analysis[/red]"
        )
        console.print(
            "[yellow]Troubleshoot currently supports single-issue "
            "analysis only[/yellow]"
        )
        return

    if not repo:
        console.print("[red]❌ --repo is required when specifying --issue-number[/red]")
        return

    # Use runner instead of create_troubleshooting_agent
    from ..runners import get_runner

    try:
        runner = get_runner(agent_name)
        console.print(f"[blue]✓ Created {agent_name} troubleshoot runner[/blue]")
    except ValueError as e:
        console.print(f"[red]❌ {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]❌ Failed to create runner: {e}[/red]")
        return

    # Find and load issue file (with auto-collection)
    base_data_dir = Path(os.environ.get("GITHUB_ANALYSIS_DATA_DIR", "data"))
    data_dir = base_data_dir / "issues"
    expected_filename = f"{org}_{repo}_issue_{issue_number}.json"
    issue_file = data_dir / expected_filename

    # Auto-collect if issue not found
    if not issue_file.exists() or not data_dir.exists():
        console.print(
            f"[yellow]Issue not cached, collecting {org}/{repo}#{issue_number}..."
            "[/yellow]"
        )

        # Import collection functionality
        from ..github_client.client import GitHubClient
        from ..github_client.search import GitHubSearcher
        from ..storage.manager import StorageManager

        try:
            github_client = GitHubClient()
            searcher = GitHubSearcher(github_client)
            storage = StorageManager()

            console.print("[blue]🔍 Collecting issue...[/blue]")
            issue = searcher.get_single_issue(org, repo, issue_number)
            issues = [issue]

            storage.save_issues(org, repo, issues)
            console.print("[green]✅ Issue collected and saved[/green]")

        except Exception as e:
            console.print(f"[red]❌ Failed to collect issue: {e}[/red]")
            console.print(
                f"[yellow]Try running: github-analysis collect --org {org} "
                f"--repo {repo} --issue-number {issue_number}[/yellow]"
            )
            return

    # Load issue data
    try:
        with open(issue_file) as f:
            issue_data = json.load(f)
        console.print(f"[blue]✓ Loaded issue data from {expected_filename}[/blue]")
    except Exception as e:
        console.print(f"[red]❌ Failed to load issue data: {e}[/red]")
        return

    if dry_run:
        console.print(
            f"[yellow]Would analyze issue #{issue_number} with "
            f"{agent_name} agent[/yellow]"
        )
        console.print(
            f"[yellow]Image processing: "
            f"{'enabled' if include_images else 'disabled'}[/yellow]"
        )
        return

    # Check for images if enabled
    if include_images:
        attachment_count = len(
            [
                att
                for att in issue_data["issue"].get("attachments", [])
                if att.get("downloaded")
                and att.get("content_type", "").startswith("image/")
            ]
        )
        if attachment_count > 0:
            console.print(f"[blue]Found {attachment_count} image(s) to analyze[/blue]")

    # Limit comments if specified (for processing only, not downloading)
    processed_issue_data = issue_data
    if limit_comments is not None:
        processed_issue_data = issue_data.copy()
        # Extract issue from StoredIssue dictionary format
        issue_model = issue_data["issue"]
        original_comments = issue_model.get("comments", [])
        if len(original_comments) > limit_comments:
            # Create a new dictionary with limited comments
            limited_issue = issue_model.copy()
            limited_issue["comments"] = original_comments[:limit_comments]
            processed_issue_data["issue"] = limited_issue
            console.print(
                f"[yellow]Limiting analysis to first {limit_comments} comment(s) "
                f"out of {len(original_comments)} total[/yellow]"
            )
        else:
            console.print(
                f"[blue]Processing all {len(original_comments)} comment(s)[/blue]"
            )

    # Run analysis
    console.print(f"[blue]🔍 Running {agent_name} analysis...[/blue]")
    start_time = datetime.utcnow()

    try:
        # Analyze using runner
        with console.status(
            "[dim]🤔 Analyzing issue with troubleshooting runner...[/dim]",
            spinner="dots",
        ):
            result: Any = await runner.analyze(processed_issue_data)

        # For interactive mode compatibility, create a simple agent_result-like object
        if interactive:
            # Create a minimal result object for interactive mode compatibility
            class SimpleAgentResult:
                def __init__(self, output: Any) -> None:
                    self.output = output

                def new_messages(self) -> list[Any]:
                    """Return empty message history for interactive mode compatibility."""
                    return []

            agent_result = SimpleAgentResult(result)
        else:
            agent_result = None

        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        # Processing time calculated but not stored in discriminated union

        console.print(f"[green]✓ Analysis completed in {processing_time:.1f}s[/green]")

    except Exception as e:
        console.print(f"[red]❌ Analysis failed: {e}[/red]")
        return

    # Display results based on discriminated union status
    console.print("\n[bold blue]🔍 Troubleshoot Analysis Results[/bold blue]")

    if result.status == "resolved":
        console.print("\n[bold green]✅ Root Cause Identified[/bold green]")
        console.print("\n[bold]Root Cause:[/bold]")
        console.print(result.root_cause)

        if result.evidence:
            console.print("\n[bold]Evidence:[/bold]")
            for i, evidence in enumerate(result.evidence, 1):
                console.print(f"{i}. {evidence}")

        console.print("\n[bold]Recommended Solution:[/bold]")
        console.print(result.solution)

        console.print("\n[bold]Analysis Validation:[/bold]")
        console.print(result.validation)

    elif result.status == "needs_data":
        console.print("\n[bold yellow]📋 Additional Data Needed[/bold yellow]")
        console.print("\n[bold]Current Hypothesis:[/bold]")
        console.print(result.current_hypothesis)

        if result.missing_evidence:
            console.print("\n[bold]Missing Evidence Needed:[/bold]")
            for i, missing in enumerate(result.missing_evidence, 1):
                console.print(f"{i}. {missing}")

        if result.next_steps:
            console.print("\n[bold]Next Steps:[/bold]")
            for i, step in enumerate(result.next_steps, 1):
                console.print(f"{i}. {step}")

        if result.eliminated:
            console.print("\n[bold]Ruled Out:[/bold]")
            for i, eliminated in enumerate(result.eliminated, 1):
                console.print(f"{i}. {eliminated}")

    # Save results
    results_dir = base_data_dir / "results" / "troubleshoot"
    results_dir.mkdir(parents=True, exist_ok=True)

    result_filename = (
        f"{org}_{repo}_issue_{issue_number}_troubleshoot_{agent_name}.json"
    )
    result_file = results_dir / result_filename

    result_data = {
        "issue_reference": {
            "file_path": str(issue_file),
            "org": org,
            "repo": repo,
            "issue_number": issue_number,
        },
        "processor": {
            "name": "troubleshoot",
            "version": "1.0.0",
            "agent": agent_name,
            "include_images": include_images,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
        "analysis": result.model_dump(),
    }

    try:
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)
        console.print(f"\n[green]✓ Results saved to {result_file.name}[/green]")
    except Exception as e:
        console.print(f"\n[red]❌ Failed to save results: {e}[/red]")

    # Send Slack notification if enabled
    if slack_notifications:
        try:
            from ..slack.client import SlackClient
            from ..slack.config import SlackConfig

            slack_config = SlackConfig()
            slack_client = SlackClient(slack_config)

            # Build the issue URL
            if url:
                issue_url = url
            else:
                issue_url = f"https://github.com/{org}/{repo}/issues/{issue_number}"

            # Get issue title from the issue data
            issue_title = issue_data["issue"].get("title", f"Issue #{issue_number}")

            console.print("[blue]📤 Sending Slack notification...[/blue]")

            success = slack_client.notify_analysis_complete(
                issue_url=issue_url,
                issue_title=issue_title,
                analysis_results=result.model_dump(),
                agent_name=agent_name,
            )

            if success:
                console.print(
                    f"[green]✓ Slack notification sent to {slack_config.channel}[/green]"
                )
            else:
                console.print(
                    "[yellow]⚠️ Failed to send Slack notification (check logs)[/yellow]"
                )

        except Exception as e:
            console.print(f"[yellow]⚠️ Slack notification failed: {e}[/yellow]")
            console.print(
                "[dim]Analysis completed successfully, but notification failed[/dim]"
            )

    # Start interactive session if requested
    if interactive:
        from ..ai.interactive import run_interactive_session

        await run_interactive_session(
            runner.agent,  # Access the internal agent from runner
            agent_result,  # The RunResult from initial analysis
            processed_issue_data,
            include_images=include_images,
        )


if __name__ == "__main__":
    app()
