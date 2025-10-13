"""CLI command for exporting GitHub issues in human-readable formats."""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from ..github_client.models import StoredIssue
from ..storage.manager import StorageManager
from .options import ISSUE_NUMBER_OPTION, ORG_OPTION, REPO_OPTION

console = Console()

app = typer.Typer(
    help="Export GitHub issues in human-readable formats",
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command()
def export(
    org: str = ORG_OPTION,
    repo: str | None = REPO_OPTION,
    issue_number: int | None = ISSUE_NUMBER_OPTION,
    format: str = typer.Option(
        "pretty-json",
        "--format",
        "-f",
        help="Export format: pretty-json or yaml",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Output file path (default: print to stdout)",
    ),
) -> None:
    """Export stored GitHub issues in human-readable formats.

    Export modes:
    - Single issue: --org ORGNAME --repo REPONAME --issue-number NUMBER
    - Repository: --org ORGNAME --repo REPONAME (all issues from repo)
    - Organization: --org ORGNAME (all issues from org)

    Supported formats:
    - pretty-json: JSON with indentation and readable formatting
    - yaml: YAML format (requires PyYAML)

    Examples:
        # Export single issue as pretty JSON
        github-analysis export --org myorg --repo myrepo --issue-number 123

        # Export all issues from a repository as YAML
        github-analysis export --org myorg --repo myrepo --format yaml

        # Export to file
        github-analysis export --org myorg --repo myrepo --output issues.json
    """
    # Validate format
    if format not in ["pretty-json", "yaml"]:
        console.print(
            f"❌ Error: Unsupported format '{format}'. Use 'pretty-json' or 'yaml'."
        )
        raise typer.Exit(1)

    # Initialize storage manager
    storage = StorageManager()

    # Collect issues based on parameters
    console.print("🔍 Loading issues from storage...")

    try:
        if issue_number is not None:
            # Single issue mode
            if repo is None:
                console.print(
                    "❌ Error: --issue-number requires both --org and --repo parameters"
                )
                raise typer.Exit(1)

            console.print(
                f"📄 Exporting single issue #{issue_number} from {org}/{repo}"
            )
            issues = storage.load_issues(org, repo, issue_number)

        elif repo is not None:
            # Repository mode
            console.print(f"📂 Exporting all issues from {org}/{repo}")
            issues = storage.load_issues(org, repo)

        else:
            # Organization mode
            console.print(f"🏢 Exporting all issues from organization {org}")
            issues = storage.load_issues(org)

        if not issues:
            console.print("❌ No issues found matching the criteria")
            return

        console.print(f"✅ Found {len(issues)} issues to export")

        # Convert to export format
        export_data = prepare_export_data(issues)

        # Export in requested format
        if format == "pretty-json":
            exported_content = export_pretty_json(export_data)
        elif format == "yaml":
            exported_content = export_yaml(export_data)
        else:
            console.print(f"❌ Error: Unsupported format '{format}'")
            raise typer.Exit(1)

        # Output result
        if output:
            output_path = Path(output)
            with output_path.open("w", encoding="utf-8") as f:
                f.write(exported_content)
            console.print(f"✅ Exported to {output_path}")
        else:
            console.print(exported_content)

    except Exception as e:
        console.print(f"❌ Error during export: {e}")
        raise typer.Exit(1)


def prepare_export_data(issues: list[StoredIssue]) -> dict[str, Any]:
    """Prepare issues data for export in a clean, readable format."""
    export_data: dict[str, Any] = {
        "export_info": {
            "total_issues": len(issues),
            "export_timestamp": "2024-01-01T00:00:00Z",  # Will be replaced
        },
        "issues": [],
    }

    import datetime

    export_data["export_info"]["export_timestamp"] = datetime.datetime.now().isoformat()

    for stored_issue in issues:
        # Convert StoredIssue to dict for export
        issue_data = stored_issue.model_dump()

        # Clean up the issue data for better readability
        clean_issue = {
            "organization": issue_data.get("org"),
            "repository": issue_data.get("repo"),
            "issue": {
                "number": issue_data["issue"]["number"],
                "title": issue_data["issue"]["title"],
                "body": issue_data["issue"]["body"],
                "state": issue_data["issue"]["state"],
                "creator": {
                    "username": issue_data["issue"]["user"]["login"],
                    "id": issue_data["issue"]["user"]["id"],
                },
                "labels": [
                    {
                        "name": label["name"],
                        "color": label["color"],
                        "description": label.get("description"),
                    }
                    for label in issue_data["issue"]["labels"]
                ],
                "comments": [
                    {
                        "id": comment["id"],
                        "author": comment["user"]["login"],
                        "body": comment["body"],
                        "created_at": comment["created_at"],
                        "updated_at": comment["updated_at"],
                    }
                    for comment in issue_data["issue"]["comments"]
                ],
                "created_at": issue_data["issue"]["created_at"],
                "updated_at": issue_data["issue"]["updated_at"],
                "attachments": [
                    {
                        "filename": attachment["filename"],
                        "original_url": attachment["original_url"],
                        "local_path": attachment.get("local_path"),
                        "content_type": attachment.get("content_type"),
                        "size": attachment.get("size"),
                        "downloaded": attachment.get("downloaded", False),
                        "source": attachment["source"],
                    }
                    for attachment in issue_data["issue"].get("attachments", [])
                ],
            },
            "metadata": issue_data.get("metadata", {}),
        }

        export_data["issues"].append(clean_issue)

    return export_data


def export_pretty_json(data: dict[str, Any]) -> str:
    """Export data as pretty-printed JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def export_yaml(data: dict[str, Any]) -> str:
    """Export data as YAML."""
    try:
        import yaml

        return yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
    except ImportError:
        raise ImportError(
            "PyYAML is required for YAML export. Install it with: uv add pyyaml"
        )


if __name__ == "__main__":
    app()
