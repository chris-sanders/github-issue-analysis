"""Interactive recommendation review session."""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .manager import RecommendationManager
from .models import RecommendationFilter, RecommendationMetadata, RecommendationStatus

console = Console()


class ReviewSession:
    """Interactive recommendation review session."""

    def __init__(self, manager: RecommendationManager):
        self.manager = manager
        self.session_stats = {
            "reviewed": 0,
            "approved": 0,
            "rejected": 0,
            "needs_modification": 0,
            "skipped": 0,
        }

    def start_session(self, filter_criteria: RecommendationFilter) -> dict[str, int]:
        """Start interactive review session."""

        # Get recommendations to review
        # Ensure we don't review NO_CHANGE_NEEDED items
        if filter_criteria.status:
            # Remove NO_CHANGE_NEEDED if it's in the list
            filter_criteria.status = [
                s
                for s in filter_criteria.status
                if s != RecommendationStatus.NO_CHANGE_NEEDED
            ]
        else:
            # Default to all statuses except NO_CHANGE_NEEDED
            all_statuses = list(RecommendationStatus)
            all_statuses.remove(RecommendationStatus.NO_CHANGE_NEEDED)
            filter_criteria.status = all_statuses

        recommendations = self.manager.get_recommendations(filter_criteria)

        if not recommendations:
            console.print("[yellow]No recommendations found matching criteria[/yellow]")
            return self.session_stats

        # Show session overview
        self._display_session_overview(recommendations)

        if not Confirm.ask(f"Start reviewing {len(recommendations)} recommendations?"):
            console.print("Review session cancelled")
            return self.session_stats

        # Review each recommendation
        for i, rec in enumerate(recommendations, 1):
            console.print(
                f"\n[bold blue]--- Reviewing {i} of {len(recommendations)} "
                "---[/bold blue]"
            )

            action = self._review_single_recommendation(rec)

            if action == "quit":
                console.print(
                    f"\n[yellow]Session ended. Reviewed "
                    f"{self.session_stats['reviewed']} recommendations.[/yellow]"
                )
                break
            elif action == "skip":
                self.session_stats["skipped"] += 1
            else:
                self.session_stats["reviewed"] += 1
                self.session_stats[action] += 1

        # Show final summary
        self._display_session_summary()
        return self.session_stats

    def _display_session_overview(
        self, recommendations: list[RecommendationMetadata]
    ) -> None:
        """Display overview of recommendations to be reviewed."""

        # Count by product
        by_product: dict[str, int] = {}
        by_confidence: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

        for rec in recommendations:
            product = rec.primary_product or "unknown"
            by_product[product] = by_product.get(product, 0) + 1
            by_confidence[rec.confidence_tier] += 1

        overview = f"""
[bold]Review Session Overview[/bold]

Total recommendations: {len(recommendations)}

By Product:
{chr(10).join(f"  {product}: {count}" for product, count in by_product.items())}

By Confidence:
  High (≥0.9): {by_confidence["high"]}
  Medium (0.7-0.9): {by_confidence["medium"]}
  Low (<0.7): {by_confidence["low"]}
"""
        console.print(Panel(overview))

    def _review_single_recommendation(self, rec: RecommendationMetadata) -> str:
        """Review a single recommendation interactively."""

        # Display recommendation details
        self._display_recommendation_details(rec)

        # Get user action
        console.print("\n[bold]Actions:[/bold]")
        console.print("  1. Approve")
        console.print("  2. Reject")
        console.print("  3. Needs Modification")
        console.print("  4. Skip (review later)")
        console.print("  5. Quit session")

        choice = Prompt.ask(
            "Choose action", choices=["1", "2", "3", "4", "5"], default="4"
        )

        action_map = {
            "1": ("approved", RecommendationStatus.APPROVED),
            "2": ("rejected", RecommendationStatus.REJECTED),
            "3": ("needs_modification", RecommendationStatus.NEEDS_MODIFICATION),
            "4": ("skip", None),
            "5": ("quit", None),
        }

        action_name, new_status = action_map[choice]

        if action_name in ["skip", "quit"]:
            return action_name

        # Get review notes
        notes = Prompt.ask("Review notes (optional)", default="")

        # Update recommendation status
        assert new_status is not None  # Type guard - we know it's not None here
        rec.status = new_status
        rec.status_updated_at = datetime.now()
        rec.reviewed_at = datetime.now()
        rec.review_notes = notes if notes else None

        self.manager.status_tracker.save_recommendation(rec)

        console.print(f"[green]✓[/green] Recommendation {action_name}")
        return action_name

    def _display_recommendation_details(self, rec: RecommendationMetadata) -> None:
        """Display detailed view of recommendation."""

        # Create labels table
        labels_table = Table(title="Label Changes")
        labels_table.add_column("Action", style="cyan")
        labels_table.add_column("Label", style="white")
        labels_table.add_column("Current", style="dim")

        # Show labels to be added (recommended but not currently present)
        for label in rec.recommended_labels:
            is_current = label in rec.current_labels
            labels_table.add_row("ADD", label, "Yes" if is_current else "No")

        # Show labels to be removed
        for label in rec.labels_to_remove:
            labels_table.add_row("REMOVE", label, "Yes")

        # Main details panel
        current_labels_str = (
            ", ".join(rec.current_labels) if rec.current_labels else "none"
        )

        # Build root cause section if available
        root_cause_section = ""
        if rec.root_cause_analysis:
            confidence_str = (
                f" (confidence: {rec.root_cause_confidence:.2f})"
                if rec.root_cause_confidence
                else ""
            )
            root_cause_section = f"""
[bold]Root Cause Analysis:[/bold]{confidence_str}
{rec.root_cause_analysis}
"""

        details = f"""
[bold]Issue:[/bold] {rec.org}/{rec.repo}/issues/{rec.issue_number}
[bold]Current Labels:[/bold] {current_labels_str}
[bold]Confidence:[/bold] {rec.original_confidence:.2f} ({rec.confidence_tier})
[bold]Primary Product:[/bold] {rec.primary_product or "unknown"}{root_cause_section}
[bold]AI Reasoning:[/bold]
{rec.ai_reasoning}
"""

        console.print(Panel(details, title="Recommendation Details"))
        console.print(labels_table)

    def _display_session_summary(self) -> None:
        """Display final session summary."""

        summary_table = Table(title="Review Session Summary")
        summary_table.add_column("Action", style="cyan")
        summary_table.add_column("Count", style="white")

        summary_table.add_row("Approved", str(self.session_stats["approved"]))
        summary_table.add_row("Rejected", str(self.session_stats["rejected"]))
        summary_table.add_row(
            "Needs Modification", str(self.session_stats["needs_modification"])
        )
        summary_table.add_row("Skipped", str(self.session_stats["skipped"]))
        summary_table.add_row("Total Reviewed", str(self.session_stats["reviewed"]))

        console.print(summary_table)
