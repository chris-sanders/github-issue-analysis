"""Comment generation system for GitHub issue label updates."""

from .change_detector import IssueUpdatePlan


class CommentGenerator:
    """Generates GitHub comments explaining AI-driven label changes."""

    def __init__(self) -> None:
        """Initialize the comment generator."""
        pass

    def generate_update_comment(self, plan: IssueUpdatePlan) -> str:
        """Generate a comment explaining label changes.

        Args:
            plan: The issue update plan with changes to explain

        Returns:
            Formatted comment text ready for posting to GitHub
        """
        if not plan.changes:
            return ""

        additions = [c for c in plan.changes if c.action == "add"]
        removals = [c for c in plan.changes if c.action == "remove"]

        # Create clean label transition format (old → new)
        lines = []

        # Generate title showing the label change
        if len(additions) == 1 and len(removals) == 1:
            old_label = removals[0].label.replace("product::", "")
            new_label = additions[0].label.replace("product::", "")
            lines.append(f"**Label Update: {old_label} → {new_label}**")
        else:
            lines.append("**Label Update**")

        lines.append("")

        # Create a concise reclassification message
        if len(additions) == 1 and len(removals) == 1:
            old_label = removals[0].label.replace("product::", "")
            new_label = additions[0].label.replace("product::", "")
            lines.append(
                f"Based on AI analysis, this issue has been reclassified from "
                f"`{old_label}` to `{new_label}`."
            )
        else:
            lines.append("Based on AI analysis, this issue has been reclassified.")
        lines.append("")

        # Add root cause analysis if available and meaningful
        if (
            plan.root_cause_analysis
            and plan.root_cause_analysis != "Root cause unclear"
        ):
            lines.append(f"**Root Cause Analysis**: {plan.root_cause_analysis}")
            lines.append("")
        elif (
            hasattr(plan, "ai_result")
            and plan.ai_result
            and hasattr(plan.ai_result, "root_cause_analysis")
            and plan.ai_result.root_cause_analysis
            and plan.ai_result.root_cause_analysis != "Root cause unclear"
        ):
            lines.append(
                f"**Root Cause Analysis**: {plan.ai_result.root_cause_analysis}"
            )
            lines.append("")
        elif plan.ai_reasoning:
            # Use the AI reasoning as the root cause
            lines.append(f"**Root Cause Analysis**: {plan.ai_reasoning}")
            lines.append("")
        elif len(additions) == 1:
            # Use the reasoning from the addition as the root cause
            lines.append(f"**Root Cause Analysis**: {additions[0].reason}")
            lines.append("")

        # Add reasoning for the change if available
        reasoning = None
        if plan.ai_reasoning:
            reasoning = plan.ai_reasoning
        elif (
            hasattr(plan, "ai_result")
            and plan.ai_result
            and hasattr(plan.ai_result, "reasoning")
            and plan.ai_result.reasoning
        ):
            reasoning = plan.ai_result.reasoning

        if reasoning:
            lines.append(f"**Reasoning**: {reasoning}")
            lines.append("")

        # Add confidence level
        lines.append(f"**Confidence Level**: {plan.overall_confidence:.0%}")

        # Add root cause confidence if available
        root_cause_confidence = None
        if (
            hasattr(plan, "ai_result")
            and plan.ai_result
            and hasattr(plan.ai_result, "root_cause_confidence")
            and plan.ai_result.root_cause_confidence is not None
        ):
            root_cause_confidence = plan.ai_result.root_cause_confidence

        if root_cause_confidence is not None:
            lines.append(f"**Root Cause Confidence**: {root_cause_confidence:.0%}")

        # Add image analysis context if available
        if (
            hasattr(plan, "ai_result")
            and plan.ai_result
            and hasattr(plan.ai_result, "image_impact")
        ):
            if plan.ai_result.image_impact:
                lines.append("")
                lines.append(f"**Analysis included**: {plan.ai_result.image_impact}")

        return "\n".join(lines)

    def generate_dry_run_summary(self, plans: list[IssueUpdatePlan]) -> str:
        """Generate a summary of planned changes for dry-run mode.

        Shows detailed information including reasoning for each change and
        the exact GitHub comment that would be posted.

        Args:
            plans: List of issue update plans

        Returns:
            Formatted summary text for console output
        """
        if not plans:
            return "No changes needed based on current confidence threshold."

        lines = []
        lines.append(f"Found {len(plans)} issue(s) that need label updates:")
        lines.append("")

        for plan in plans:
            issue_url = f"{plan.org}/{plan.repo}/issues/{plan.issue_number}"
            lines.append(f"**Issue #{plan.issue_number} ({issue_url})**")
            lines.append(f"Recommendation confidence: {plan.overall_confidence:.2f}")

            # Show root cause confidence if available
            root_cause_confidence = None
            if (
                hasattr(plan, "ai_result")
                and plan.ai_result
                and hasattr(plan.ai_result, "root_cause_confidence")
                and plan.ai_result.root_cause_confidence is not None
            ):
                root_cause_confidence = plan.ai_result.root_cause_confidence

            if root_cause_confidence is not None:
                lines.append(f"Root cause confidence: {root_cause_confidence:.2f}")

            # Show changes without individual confidence scores
            additions = [c for c in plan.changes if c.action == "add"]
            removals = [c for c in plan.changes if c.action == "remove"]

            if additions:
                lines.append("  Add:")
                for change in additions:
                    lines.append(f"    + {change.label} - {change.reason}")

            if removals:
                lines.append("  Remove:")
                for change in removals:
                    lines.append(f"    - {change.label} - {change.reason}")

            # Add GitHub comment preview
            comment = self.generate_update_comment(plan)
            if comment:
                lines.append("")
                lines.append("**GitHub Comment Preview:**")
                lines.append("---")
                lines.append(comment)
                lines.append("---")

            lines.append("")

        return "\n".join(lines)

    def generate_execution_summary(
        self,
        successful: list[IssueUpdatePlan],
        failed: list[tuple[IssueUpdatePlan, str]],
    ) -> str:
        """Generate a summary of execution results.

        Args:
            successful: List of successfully updated plans
            failed: List of (plan, error_message) tuples for failed updates

        Returns:
            Formatted summary text for console output
        """
        lines = []

        if successful:
            lines.append(f"✅ Successfully updated {len(successful)} issue(s):")
            for plan in successful:
                change_count = len(plan.changes)
                lines.append(
                    f"  - Issue #{plan.issue_number}: {change_count} change(s)"
                )
            lines.append("")

        if failed:
            lines.append(f"❌ Failed to update {len(failed)} issue(s):")
            for plan, error in failed:
                lines.append(f"  - Issue #{plan.issue_number}: {error}")
            lines.append("")

        if not successful and not failed:
            lines.append("No issues processed.")

        return "\n".join(lines)
