"""Main CLI entry point."""

import typer
from rich.console import Console

from . import batch, process, recommendations
from .collect import collect, status
from .export import export
from .update import update_labels

app = typer.Typer(
    name="github-analysis",
    help="GitHub issue collection and AI analysis",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


# All commands including main command support -h shorthand via context_settings


app.command(name="collect", context_settings={"help_option_names": ["-h", "--help"]})(
    collect
)
app.command(name="status", context_settings={"help_option_names": ["-h", "--help"]})(
    status
)
app.command(name="export", context_settings={"help_option_names": ["-h", "--help"]})(
    export
)
app.command(
    name="update-labels", context_settings={"help_option_names": ["-h", "--help"]}
)(update_labels)
app.add_typer(process.app, name="process")
app.add_typer(batch.app, name="batch")
app.add_typer(recommendations.app, name="recommendations")


@app.command(context_settings={"help_option_names": ["-h", "--help"]})
def version() -> None:
    """Show version information."""
    from gh_analysis import __version__

    console.print(f"GitHub Issue Analysis v{__version__}")


if __name__ == "__main__":
    app()
