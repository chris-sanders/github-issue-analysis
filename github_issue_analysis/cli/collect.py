"""CLI command for collecting GitHub issues."""

import typer
from rich.console import Console
from rich.table import Table

from ..github_client.attachments import AttachmentDownloader
from ..github_client.client import GitHubClient
from ..github_client.models import GitHubIssue
from ..github_client.search import GitHubSearcher, build_exclusion_list
from ..storage.manager import StorageManager
from ..utils.date_parser import format_datetime_for_github, validate_date_parameters

console = Console()
app = typer.Typer(help="Collect GitHub issues and store them locally")


@app.command()
def collect(
    org: str = typer.Option(..., "--org", "-o", help="GitHub organization name"),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub repository name (optional for org-wide search)",
    ),
    issue_number: int | None = typer.Option(
        None, "--issue-number", help="Specific issue number to collect"
    ),
    labels: list[str] | None = typer.Option(
        None, "--labels", "-l", help="Filter by labels (can be used multiple times)"
    ),
    limit: int = typer.Option(
        10, "--limit", help="Maximum number of issues to collect"
    ),
    state: str = typer.Option(
        "closed", "--state", help="Issue state: open, closed, or all"
    ),
    token: str | None = typer.Option(
        None, "--token", help="GitHub API token (defaults to GITHUB_TOKEN env var)"
    ),
    download_attachments: bool = typer.Option(
        True,
        "--download-attachments/--no-download-attachments",
        help="Download issue and comment attachments",
    ),
    max_attachment_size: int = typer.Option(
        10, "--max-attachment-size", help="Maximum attachment size in MB"
    ),
    # Date filtering options - absolute dates
    created_after: str | None = typer.Option(
        None, "--created-after", help="Filter issues created after date (YYYY-MM-DD)"
    ),
    created_before: str | None = typer.Option(
        None, "--created-before", help="Filter issues created before date (YYYY-MM-DD)"
    ),
    updated_after: str | None = typer.Option(
        None, "--updated-after", help="Filter issues updated after date (YYYY-MM-DD)"
    ),
    updated_before: str | None = typer.Option(
        None, "--updated-before", help="Filter issues updated before date (YYYY-MM-DD)"
    ),
    # Date filtering options - relative dates (convenience)
    last_days: int | None = typer.Option(
        None, "--last-days", help="Filter issues from last N days"
    ),
    last_weeks: int | None = typer.Option(
        None, "--last-weeks", help="Filter issues from last N weeks"
    ),
    last_months: int | None = typer.Option(
        None, "--last-months", help="Filter issues from last N months"
    ),
    # Repository exclusion options (for organization-wide searches)
    exclude_repo: list[str] | None = typer.Option(
        None,
        "--exclude-repo",
        "-x",
        help="Repository to exclude from organization-wide search "
        "(can be used multiple times)",
    ),
    exclude_repos: str | None = typer.Option(
        None,
        "--exclude-repos",
        help="Comma-separated list of repositories to exclude "
        "from organization-wide search",
    ),
) -> None:
    """Collect GitHub issues and save them locally.

    Collection modes:
    - Single issue: --org ORGNAME --repo REPONAME --issue-number NUMBER
    - Organization-wide: --org ORGNAME (searches all repos in org)
    - Repository-specific: --org ORGNAME --repo REPONAME (existing behavior)

    Date filtering examples:
        # Absolute date ranges
        github-analysis collect --org myorg --created-after 2024-01-01 \\
            --created-before 2024-06-30
        github-analysis collect --org myorg --repo myrepo --updated-after 2024-01-01

        # Relative date filtering (convenience options)
        github-analysis collect --org myorg --last-months 6
        github-analysis collect --org myorg --repo myrepo --last-weeks 2

        # Combined with existing filters
        github-analysis collect --org myorg --repo myrepo --labels bug --last-days 30

    Basic examples:
        github-analysis collect --org replicated-collab --repo pixee-replicated \\
            --issue-number 71
        github-analysis collect --org replicated-collab --limit 20
        github-analysis collect --org microsoft --repo vscode --labels bug --limit 5
    """
    # Date parameter validation
    try:
        created_after_dt, created_before_dt, updated_after_dt, updated_before_dt = (
            validate_date_parameters(
                created_after=created_after,
                created_before=created_before,
                updated_after=updated_after,
                updated_before=updated_before,
                last_days=last_days,
                last_weeks=last_weeks,
                last_months=last_months,
            )
        )
    except ValueError as e:
        console.print(f"❌ Date validation error: {e}")
        raise typer.Exit(1)

    # Parameter validation
    if issue_number is not None:
        # Single issue mode - requires both org and repo
        if repo is None:
            console.print(
                "❌ Error: --issue-number requires both --org and --repo parameters"
            )
            raise typer.Exit(1)
        collection_mode = "single_issue"
        console.print(f"🔍 Collecting single issue #{issue_number} from {org}/{repo}")
    elif repo is None:
        # Organization-wide mode - only org provided
        collection_mode = "organization"
        console.print(f"🔍 Collecting issues from organization {org}")
    else:
        # Repository-specific mode - both org and repo provided
        collection_mode = "repository"
        console.print(f"🔍 Collecting issues from {org}/{repo}")

    # Process repository exclusions for organization-wide search
    excluded_repositories: list[str] = []
    if collection_mode == "organization":
        excluded_repositories = build_exclusion_list(exclude_repo, exclude_repos)
        if excluded_repositories:
            console.print(
                f"📋 Excluding repositories: {', '.join(excluded_repositories)}"
            )

    # Show collection parameters
    params_table = Table(title="Collection Parameters")
    params_table.add_column("Parameter", style="cyan")
    params_table.add_column("Value", style="green")

    params_table.add_row("Mode", collection_mode.replace("_", " ").title())
    params_table.add_row("Organization", org)
    if repo:
        params_table.add_row("Repository", repo)
    if issue_number is not None:
        params_table.add_row("Issue Number", str(issue_number))
    params_table.add_row("Labels", ", ".join(labels) if labels else "All")
    params_table.add_row("State", state)
    if collection_mode != "single_issue":
        params_table.add_row("Limit", str(limit))
    if collection_mode == "organization" and excluded_repositories:
        params_table.add_row("Excluded Repos", ", ".join(excluded_repositories))

    # Add date filtering parameters if provided
    if created_after_dt:
        params_table.add_row("Created After", created_after_dt.strftime("%Y-%m-%d"))
    if created_before_dt:
        params_table.add_row("Created Before", created_before_dt.strftime("%Y-%m-%d"))
    if updated_after_dt:
        params_table.add_row("Updated After", updated_after_dt.strftime("%Y-%m-%d"))
    if updated_before_dt:
        params_table.add_row("Updated Before", updated_before_dt.strftime("%Y-%m-%d"))

    # Show relative date info if used
    if last_days:
        params_table.add_row("Time Range", f"Last {last_days} days")
    elif last_weeks:
        params_table.add_row("Time Range", f"Last {last_weeks} weeks")
    elif last_months:
        params_table.add_row("Time Range", f"Last {last_months} months")

    console.print(params_table)

    try:
        # Initialize GitHub client
        console.print("🔑 Initializing GitHub client...")
        client = GitHubClient(token=token)
        searcher = GitHubSearcher(client)

        # Collect issues based on mode
        console.print("🔎 Searching for issues...")
        if collection_mode == "single_issue":
            # Single issue collection
            assert repo is not None  # guaranteed by validation above
            assert issue_number is not None  # guaranteed by validation above
            issue = searcher.get_single_issue(org, repo, issue_number)
            issues = [issue]
        elif collection_mode == "organization":
            # Organization-wide search
            issues = searcher.search_organization_issues(
                org=org,
                labels=labels,
                state=state,
                limit=limit,
                created_after=(
                    format_datetime_for_github(created_after_dt)
                    if created_after_dt
                    else None
                ),
                created_before=(
                    format_datetime_for_github(created_before_dt)
                    if created_before_dt
                    else None
                ),
                updated_after=(
                    format_datetime_for_github(updated_after_dt)
                    if updated_after_dt
                    else None
                ),
                updated_before=(
                    format_datetime_for_github(updated_before_dt)
                    if updated_before_dt
                    else None
                ),
                excluded_repos=excluded_repositories,
            )
        else:
            # Repository-specific search
            assert repo is not None  # guaranteed by validation above
            issues = searcher.search_repository_issues(
                org=org,
                repo=repo,
                labels=labels,
                state=state,
                limit=limit,
                created_after=(
                    format_datetime_for_github(created_after_dt)
                    if created_after_dt
                    else None
                ),
                created_before=(
                    format_datetime_for_github(created_before_dt)
                    if created_before_dt
                    else None
                ),
                updated_after=(
                    format_datetime_for_github(updated_after_dt)
                    if updated_after_dt
                    else None
                ),
                updated_before=(
                    format_datetime_for_github(updated_before_dt)
                    if updated_before_dt
                    else None
                ),
            )

        if not issues:
            console.print("❌ No issues found matching the criteria")
            return

        console.print(f"✅ Found {len(issues)} issues")

        # Process attachments if enabled
        if download_attachments:
            console.print("🔗 Processing issue attachments...")
            if not client.token:
                console.print("❌ GitHub token required for attachment downloads")
                raise typer.Exit(1)
            downloader = AttachmentDownloader(
                github_token=client.token, max_size_mb=max_attachment_size
            )

            # Process each issue for attachments
            for i, issue in enumerate(issues):
                console.print(f"Processing attachments for issue #{issue.number}...")

                # Detect attachments
                issues[i] = downloader.process_issue_attachments(issue)

                # Download attachments if any were found
                if issues[i].attachments:
                    import asyncio
                    from pathlib import Path

                    base_dir = Path("data/attachments")
                    # For org-wide searches, use the repository name from the issue
                    repo_name = repo if repo is not None else issues[i].repository_name
                    if repo_name is None:
                        console.print(
                            f"Warning: No repository name available for issue "
                            f"#{issue.number}, skipping attachment download"
                        )
                        continue

                    issues[i] = asyncio.run(
                        downloader.download_issue_attachments(
                            issues[i], base_dir, org, repo_name
                        )
                    )

        # Initialize storage manager
        storage = StorageManager()

        # Save issues - for organization-wide search, group by repository
        console.print("💾 Saving issues to storage...")
        if collection_mode == "organization":
            # For organization-wide search, group issues by repository and save
            issues_by_repo: dict[str, list[GitHubIssue]] = {}
            for issue in issues:
                issue_repo = issue.repository_name or "unknown_repo"
                if issue_repo not in issues_by_repo:
                    issues_by_repo[issue_repo] = []
                issues_by_repo[issue_repo].append(issue)

            # Save issues grouped by repository
            saved_paths = []
            for repo_name, repo_issues in issues_by_repo.items():
                paths = storage.save_issues(org, repo_name, repo_issues)
                saved_paths.extend(paths)
        else:
            # Single issue or repository-specific - use the provided repo name
            assert repo is not None  # guaranteed by validation above
            saved_paths = storage.save_issues(org, repo, issues)

        # Show results
        results_table = Table(title="Collection Results")
        results_table.add_column("Issue #", style="cyan")
        if collection_mode == "organization":
            results_table.add_column("Repository", style="magenta")
        results_table.add_column("Title", style="white")
        results_table.add_column("State", style="green")
        results_table.add_column("Comments", justify="right", style="yellow")

        for issue in issues:
            row_data = [str(issue.number)]
            if collection_mode == "organization":
                row_data.append(issue.repository_name or "unknown")
            row_data.extend(
                [
                    issue.title[:50] + "..." if len(issue.title) > 50 else issue.title,
                    issue.state,
                    str(len(issue.comments)),
                ]
            )
            results_table.add_row(*row_data)

        console.print(results_table)

        # Show storage info
        stats = storage.get_storage_stats()
        console.print(f"📊 Total issues in storage: {stats['total_issues']}")
        console.print(f"💿 Storage size: {stats['total_size_mb']} MB")
        console.print(f"📁 Storage location: {stats['storage_path']}")

        console.print(f"✨ Successfully collected and saved {len(saved_paths)} issues!")

    except ValueError as e:
        console.print(f"❌ Error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Unexpected error: {e}")
        console.print("Please check your GitHub token and network connection.")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """Show storage status and statistics."""
    console.print("📊 Storage Status")

    storage = StorageManager()
    stats = storage.get_storage_stats()

    # Overall stats
    stats_table = Table(title="Storage Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")

    stats_table.add_row("Total Issues", str(stats["total_issues"]))
    stats_table.add_row("Storage Size", f"{stats['total_size_mb']} MB")
    stats_table.add_row("Storage Path", stats["storage_path"])

    console.print(stats_table)

    # Repository breakdown
    if stats["repositories"]:
        repo_table = Table(title="Issues by Repository")
        repo_table.add_column("Repository", style="cyan")
        repo_table.add_column("Issue Count", justify="right", style="green")

        for repo, count in sorted(stats["repositories"].items()):
            repo_table.add_row(repo, str(count))

        console.print(repo_table)
    else:
        console.print("No issues found in storage.")


if __name__ == "__main__":
    app()
