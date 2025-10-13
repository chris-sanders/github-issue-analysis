"""CLI commands for managing AI recommendation review workflow."""

import builtins
import json
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from ..recommendation.manager import RecommendationManager
from ..recommendation.models import (
    RecommendationFilter,
    RecommendationMetadata,
    RecommendationStatus,
)
from ..recommendation.review_session import ReviewSession

console = Console()
app = typer.Typer(
    help="Manage AI recommendation review workflow. Use 'discover' to find new "
    "recommendations, 'list' to view them, 'summary' for statistics, and "
    "'review-session' for interactive review.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def discover(
    force_refresh: bool = typer.Option(
        False,
        "--force-refresh",
        help="Force refresh all recommendations. Re-evaluates status based on "
        "current labels.",
    ),
    data_dir: str = typer.Option("data", help="Data directory path"),
) -> None:
    """Discover new AI recommendations and initialize tracking.

    Scans the results directory for AI analysis files and creates recommendation
    metadata. Sets status to NO_CHANGE_NEEDED if recommended labels match current
    labels, otherwise PENDING.
    """

    manager = RecommendationManager(Path(data_dir))

    with console.status("[bold green]Scanning for recommendations..."):
        recommendations = manager.discover_recommendations(force_refresh)

    console.print(f"[green]✓[/green] Found {len(recommendations)} recommendations")

    # Show summary
    if recommendations:
        summary(data_dir=data_dir)


@app.command(name="list")
def list_recommendations(
    org: str | None = typer.Option(None, help="Filter by organization"),
    repo: str | None = typer.Option(None, help="Filter by repository"),
    status: list[str] | None = typer.Option(
        None,
        help="Filter by status (pending, no_change_needed, approved, rejected, etc.)",
    ),
    product: list[str] | None = typer.Option(
        None,
        help="Filter by product (kots, vendor, troubleshoot, embedded-cluster, etc.)",
    ),
    min_confidence: float | None = typer.Option(
        None, help="Minimum confidence threshold (0.0-1.0)"
    ),
    confidence_tier: list[str] | None = typer.Option(
        None, help="Filter by confidence tier: high (≥0.9), medium (≥0.7), low (<0.7)"
    ),
    limit: int | None = typer.Option(20, help="Maximum number of results"),
    format: str = typer.Option("table", help="Output format: table, json, summary"),
    include_no_change: bool = typer.Option(
        False,
        "--include-no-change",
        help="Include recommendations where no label change is needed "
        "(NO_CHANGE_NEEDED status)",
    ),
    data_dir: str = typer.Option("data", help="Data directory path"),
) -> None:
    """List recommendations with filtering options.

    By default, excludes NO_CHANGE_NEEDED recommendations. Use --include-no-change
    to see all recommendations including those where current labels match
    recommendations.
    """

    manager = RecommendationManager(Path(data_dir))

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = [RecommendationStatus(s) for s in status]
        except ValueError as e:
            console.print(f"[red]Invalid status value: {e}[/red]")
            return

    filter_criteria = RecommendationFilter(
        org=org,
        repo=repo,
        status=status_filter,
        product=product,
        min_confidence=min_confidence,
        confidence_tier=confidence_tier,
        limit=limit,
    )

    # Add NO_CHANGE_NEEDED to status filter unless explicitly requested
    if not include_no_change:
        if filter_criteria.status:
            # Don't add NO_CHANGE_NEEDED to existing status filter
            pass
        else:
            # Exclude NO_CHANGE_NEEDED by default - show all other statuses
            all_statuses = list(RecommendationStatus)
            all_statuses.remove(RecommendationStatus.NO_CHANGE_NEEDED)
            filter_criteria.status = all_statuses

    recommendations = manager.get_recommendations(filter_criteria)

    if format == "json":
        rprint(
            json.dumps(
                [rec.model_dump() for rec in recommendations], indent=2, default=str
            )
        )
    elif format == "summary":
        _display_recommendations_summary(recommendations)
    else:
        _display_recommendations_table(recommendations)


@app.command()
def summary(
    data_dir: str = typer.Option("data", help="Data directory path"),
) -> None:
    """Show recommendation dashboard with statistics.

    Displays:
    - Total recommendations count
    - Pending high confidence count
    - No change needed count
    - Breakdown by status
    - Breakdown by product (top 10)
    """

    manager = RecommendationManager(Path(data_dir))
    summary_data = manager.get_recommendation_summary()

    # Main statistics panel
    stats_table = Table(title="Recommendation Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Count", style="white")

    stats_table.add_row(
        "Total Recommendations", str(summary_data["total_recommendations"])
    )
    stats_table.add_row(
        "Pending High Confidence", str(summary_data["pending_high_confidence"])
    )
    stats_table.add_row("No Change Needed", str(summary_data["no_change_needed"]))
    stats_table.add_row("Recently Applied", str(summary_data["recently_applied"]))

    console.print(stats_table)

    # Status breakdown
    if summary_data["by_status"]:
        status_table = Table(title="By Status")
        status_table.add_column("Status", style="cyan")
        status_table.add_column("Count", style="white")

        for status, count in summary_data["by_status"].items():
            status_table.add_row(status.title(), str(count))

        console.print(status_table)

    # Product breakdown
    if summary_data["by_product"]:
        product_table = Table(title="By Product")
        product_table.add_column("Product", style="cyan")
        product_table.add_column("Count", style="white")

        for product, count in sorted(
            summary_data["by_product"].items(), key=lambda x: x[1], reverse=True
        )[:10]:
            product_table.add_row(product, str(count))

        console.print(product_table)


@app.command()
def review_session(
    org: str | None = typer.Option(None, help="Limit to specific organization"),
    repo: str | None = typer.Option(None, help="Limit to specific repository"),
    status: builtins.list[str] | None = typer.Option(
        ["pending"],
        help="Filter by status (default: pending). NO_CHANGE_NEEDED always excluded.",
    ),
    min_confidence: float | None = typer.Option(
        None, help="Minimum confidence threshold (0.0-1.0)"
    ),
    product: builtins.list[str] | None = typer.Option(
        None, help="Filter by product (kots, vendor, troubleshoot, etc.)"
    ),
    data_dir: str = typer.Option("data", help="Data directory path"),
) -> None:
    """Start interactive review session for recommendations.

    Presents recommendations one by one for review. Actions available:
    1. Approve - Mark as approved for application
    2. Reject - Mark as rejected
    3. Modify - Adjust confidence score
    4. Request changes - Mark as needs_modification
    5. Skip - Move to next without changing
    6. Quit - Exit session

    Note: NO_CHANGE_NEEDED recommendations are automatically excluded from review.
    """

    manager = RecommendationManager(Path(data_dir))
    review_session = ReviewSession(manager)

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = [RecommendationStatus(s) for s in status]
        except ValueError as e:
            console.print(f"[red]Invalid status value: {e}[/red]")
            console.print(
                "Valid statuses: pending, approved, rejected, needs_modification"
            )
            return

    filter_criteria = RecommendationFilter(
        org=org,
        repo=repo,
        status=status_filter,
        min_confidence=min_confidence,
        product=product,
    )

    # Start the interactive review session
    results = review_session.start_session(filter_criteria)

    if results["reviewed"] > 0:
        console.print(
            f"\n[green]✓[/green] Session complete. "
            f"Reviewed {results['reviewed']} recommendations"
        )
    else:
        console.print("\n[yellow]No recommendations were reviewed[/yellow]")


def _display_recommendations_table(
    recommendations: builtins.list[RecommendationMetadata],
) -> None:
    """Display recommendations in a table format."""
    if not recommendations:
        console.print("[yellow]No recommendations found[/yellow]")
        return

    table = Table()
    table.add_column("Issue", style="cyan")
    table.add_column("Current Labels", style="dim")
    table.add_column("Recommended Labels", style="green")
    table.add_column("Confidence", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Reviewed", style="dim")

    for rec in recommendations:
        confidence_display = f"{(rec.review_confidence or rec.original_confidence):.2f}"

        # Format current product labels only
        current_product_labels = [
            label for label in rec.current_labels if label.startswith("product::")
        ]
        current_labels_display = (
            ", ".join(current_product_labels[:2]) if current_product_labels else "none"
        )
        if len(current_product_labels) > 2:
            current_labels_display += "..."

        # Format recommended labels
        recommended_labels_display = ", ".join(rec.recommended_labels[:2])
        if len(rec.recommended_labels) > 2:
            recommended_labels_display += "..."

        reviewed_display = ""
        if rec.reviewed_at:
            reviewed_display = rec.reviewed_at.strftime("%m/%d")

        table.add_row(
            f"{rec.repo}/issues/{rec.issue_number}",
            current_labels_display,
            recommended_labels_display,
            confidence_display,
            rec.status.value,
            reviewed_display,
        )

    console.print(table)


def _display_recommendations_summary(
    recommendations: builtins.list[RecommendationMetadata],
) -> None:
    """Display summary statistics for recommendations."""
    if not recommendations:
        console.print("[yellow]No recommendations found[/yellow]")
        return

    # Calculate statistics
    by_status: dict[str, int] = {}
    by_product: dict[str, int] = {}
    by_confidence: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for rec in recommendations:
        # Status
        status = rec.status.value
        by_status[status] = by_status.get(status, 0) + 1

        # Product
        product = rec.primary_product or "unknown"
        by_product[product] = by_product.get(product, 0) + 1

        # Confidence
        by_confidence[rec.confidence_tier] += 1

    # Display summary
    console.print(f"\n[bold]Summary of {len(recommendations)} recommendations:[/bold]")

    console.print("\nBy Status:")
    for status, count in by_status.items():
        console.print(f"  {status}: {count}")

    console.print("\nBy Product:")
    for product, count in sorted(by_product.items(), key=lambda x: x[1], reverse=True)[
        :5
    ]:
        console.print(f"  {product}: {count}")

    console.print("\nBy Confidence:")
    for tier, count in by_confidence.items():
        console.print(f"  {tier}: {count}")
