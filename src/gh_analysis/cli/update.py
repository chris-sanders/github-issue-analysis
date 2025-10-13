"""CLI commands for updating GitHub issue labels based on AI recommendations."""

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm

from ..ai.change_detector import ChangeDetector, IssueUpdatePlan
from ..ai.comment_generator import CommentGenerator
from ..github_client.client import GitHubClient
from ..recommendation.status_tracker import StatusTracker
from .options import (
    DATA_DIR_OPTION,
    DELAY_OPTION,
    DRY_RUN_OPTION,
    FORCE_OPTION,
    IGNORE_STATUS_OPTION,
    ISSUE_NUMBER_OPTION,
    MAX_ISSUES_OPTION,
    MIN_CONFIDENCE_OPTION,
    REPO_OPTION,
    SKIP_COMMENTS_OPTION,
)

console = Console()


def update_labels(
    org: str | None = typer.Option(
        None, "--org", "-o", help="Organization name (required)"
    ),
    repo: str | None = REPO_OPTION,
    issue_number: int | None = ISSUE_NUMBER_OPTION,
    min_confidence: float = MIN_CONFIDENCE_OPTION,
    dry_run: bool = DRY_RUN_OPTION,
    skip_comments: bool = SKIP_COMMENTS_OPTION,
    force: bool = FORCE_OPTION,
    max_issues: int | None = MAX_ISSUES_OPTION,
    delay: float = DELAY_OPTION,
    data_dir: str | None = DATA_DIR_OPTION,
    ignore_status: bool = IGNORE_STATUS_OPTION,
) -> None:
    """Update GitHub issue labels based on AI recommendations.

    This command analyzes AI recommendations and applies label changes to GitHub issues.
    It can process a single issue, all issues in a repository, or all issues across
    an organization (if no repo specified).

    By default, only processes recommendations with APPROVED status. Use --ignore-status
    to process all recommendations regardless of approval status.

    The --dry-run mode shows you exactly what changes will be made, including:
    - Which labels will be added/removed with confidence scores and reasoning
    - The exact GitHub comment that will be posted to each issue
    - Overall confidence assessment for each issue

    Examples:
        # Preview changes for specific issue (shows exact changes + comments)
        uv run github-analysis update-labels --org myorg --repo myrepo \
            --issue-number 123 --dry-run

        # Update all approved recommendations for a repository
        uv run github-analysis update-labels --org myorg --repo myrepo \
            --min-confidence 0.9

        # Update specific issue ignoring approval status
        uv run github-analysis update-labels --org myorg --repo myrepo \
            --issue-number 123 --ignore-status
    """
    # Validate arguments
    if repo and not org:
        console.print("❌ [red]Error: --org is required when --repo is specified[/red]")
        raise typer.Exit(1)

    if issue_number and not (org and repo):
        console.print(
            "❌ [red]Error: --org and --repo are required when "
            "--issue-number is specified[/red]"
        )
        raise typer.Exit(1)

    if not org:
        console.print("❌ [red]Error: --org is required[/red]")
        raise typer.Exit(1)

    # Set up paths
    base_data_dir = Path(data_dir) if data_dir else Path("data")
    if not base_data_dir.exists():
        console.print(
            f"❌ [red]Error: Data directory {base_data_dir} does not exist[/red]"
        )
        raise typer.Exit(1)

    # Apply force flag to confidence
    if force:
        min_confidence = 0.0
        console.print(
            "⚠️  [yellow]Force mode enabled - applying all changes "
            "regardless of confidence[/yellow]"
        )

    # Status filtering info
    if ignore_status:
        console.print(
            "⚠️  [yellow]Status filtering disabled - processing all "
            "recommendations[/yellow]"
        )
    else:
        console.print(
            "🔒 [blue]Only processing APPROVED recommendations "
            "(use --ignore-status to override)[/blue]"
        )

    console.print(
        f"🔍 [blue]Analyzing label changes with confidence threshold: "
        f"{min_confidence}[/blue]"
    )

    try:
        # Initialize components
        detector = ChangeDetector(
            min_confidence=min_confidence,
            ignore_status=ignore_status,
            data_dir=base_data_dir,
        )
        generator = CommentGenerator()

        # Use recommendation system as the authoritative source
        if not detector.status_tracker:
            console.print(
                "❌ [red]No recommendation status tracker available. "
                "Run 'recommendations discover' first.[/red]"
            )
            raise typer.Exit(1)

        # Get recommendations from status tracker
        from ..recommendation.models import RecommendationFilter

        filter_criteria = RecommendationFilter(
            org=org,
            repo=repo,
        )

        plans: list[IssueUpdatePlan] = []

        if issue_number and repo:
            # For single issue, get directly
            recommendation = detector.status_tracker.get_recommendation(
                org, repo, issue_number
            )
            if recommendation:
                plan = detector.create_plan_from_recommendation(recommendation)
                if plan:
                    plans.append(plan)
        else:
            # For multiple issues, query with filter
            recommendations = detector.status_tracker.query_recommendations(
                filter_criteria
            )
            for recommendation in recommendations:
                plan = detector.create_plan_from_recommendation(recommendation)
                if plan:
                    plans.append(plan)

        console.print(
            f"📁 [green]Found {len(plans)} recommendation(s) to process[/green]"
        )

        # Apply max_issues limit
        if max_issues and len(plans) > max_issues:
            plans = plans[:max_issues]
            console.print(
                f"⚠️  [yellow]Limited to {max_issues} issues as requested[/yellow]"
            )

        if not plans:
            console.print(
                "✅ [green]No label changes needed based on current "
                "confidence threshold[/green]"
            )
            return

        # Show dry run summary
        if dry_run:
            summary = generator.generate_dry_run_summary(plans)
            console.print("\n📋 [blue]Planned Changes:[/blue]")
            console.print(summary)
            return

        # Confirm before applying changes
        if not force and len(plans) > 1:
            summary = generator.generate_dry_run_summary(plans)
            console.print("\n📋 [blue]Planned Changes:[/blue]")
            console.print(summary)

            if not Confirm.ask("\nProceed with these changes?"):
                console.print("❌ [yellow]Operation cancelled by user[/yellow]")
                return

        # Apply changes
        successful, failed = _apply_label_changes(
            plans, generator, skip_comments, delay, detector.status_tracker
        )

        # Show execution summary
        summary = generator.generate_execution_summary(successful, failed)
        console.print("\n📊 [blue]Execution Summary:[/blue]")
        console.print(summary)

        if failed:
            raise typer.Exit(1)

    except KeyboardInterrupt:
        console.print("\n❌ [yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        raise typer.Exit(1)


def _apply_label_changes(
    plans: list[IssueUpdatePlan],
    generator: CommentGenerator,
    skip_comments: bool,
    delay: float,
    status_tracker: StatusTracker | None = None,
) -> tuple[list[IssueUpdatePlan], list[tuple[IssueUpdatePlan, str]]]:
    """Apply label changes to GitHub issues.

    Args:
        plans: List of update plans to execute
        generator: Comment generator for explanatory comments
        skip_comments: Whether to skip posting comments
        delay: Delay between API calls
        status_tracker: Optional status tracker to update recommendation status

    Returns:
        Tuple of (successful_plans, failed_plans_with_errors)
    """
    import time

    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError(
            "GitHub token required for label updates. "
            "Set GITHUB_TOKEN environment variable."
        )

    client = GitHubClient(token=github_token)
    successful: list[IssueUpdatePlan] = []
    failed: list[tuple[IssueUpdatePlan, str]] = []

    for i, plan in enumerate(plans):
        try:
            console.print(
                f"🏷️  [blue]Processing issue #{plan.issue_number} "
                f"({i + 1}/{len(plans)})[/blue]"
            )

            # Calculate new label set
            current_labels = set(
                client.get_issue_labels(plan.org, plan.repo, plan.issue_number)
            )
            new_labels = current_labels.copy()

            # Apply changes
            for change in plan.changes:
                if change.action == "add":
                    new_labels.add(change.label)
                elif change.action == "remove":
                    new_labels.discard(change.label)

            # Update labels if there are actual changes
            if new_labels != current_labels:
                client.update_issue_labels(
                    plan.org, plan.repo, plan.issue_number, list(new_labels)
                )

                # Add explanatory comment if not skipped
                if not skip_comments:
                    comment = generator.generate_update_comment(plan)
                    if comment:
                        client.add_issue_comment(
                            plan.org, plan.repo, plan.issue_number, comment
                        )

                successful.append(plan)
                console.print(
                    f"  ✅ [green]Updated {len(plan.changes)} label(s)[/green]"
                )

                # Update recommendation status to APPLIED
                if status_tracker:
                    recommendation = status_tracker.get_recommendation(
                        plan.org, plan.repo, plan.issue_number
                    )
                    if recommendation:
                        from datetime import datetime

                        from ..recommendation.models import RecommendationStatus

                        recommendation.status = RecommendationStatus.APPLIED
                        recommendation.status_updated_at = datetime.now()
                        status_tracker.save_recommendation(recommendation)
            else:
                console.print("  ⚠️  [yellow]No actual changes needed[/yellow]")
                successful.append(plan)

            # Rate limiting delay
            if delay > 0 and i < len(plans) - 1:
                time.sleep(delay)

        except Exception as e:
            error_msg = str(e)
            failed.append((plan, error_msg))
            console.print(f"  ❌ [red]Failed: {error_msg}[/red]")

            # Update recommendation status to FAILED
            if status_tracker:
                recommendation = status_tracker.get_recommendation(
                    plan.org, plan.repo, plan.issue_number
                )
                if recommendation:
                    from datetime import datetime

                    from ..recommendation.models import RecommendationStatus

                    recommendation.status = RecommendationStatus.FAILED
                    recommendation.status_updated_at = datetime.now()
                    status_tracker.save_recommendation(recommendation)
            continue

    return successful, failed
