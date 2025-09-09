"""Test main CLI functionality."""

from typer.testing import CliRunner

from gh_analysis.cli.main import app

runner = CliRunner()


def test_version_command() -> None:
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "GitHub Issue Analysis v" in result.stdout
