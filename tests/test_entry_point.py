"""Test that the CLI entry point works correctly in built packages."""

import subprocess
import sys


def test_entry_point_import():
    """Test that the entry point module can be imported."""
    # This should work whether we're in dev mode or installed from a wheel
    try:
        from gh_analysis.cli.main import app

        assert app is not None
    except ImportError:
        # Fallback for development mode
        from gh_analysis.cli.main import app

        assert app is not None


def test_cli_help_command():
    """Test that the CLI help command works."""
    result = subprocess.run(
        [sys.executable, "-c", "from gh_analysis.cli.main import app; app(['--help'])"],
        capture_output=True,
        text=True,
    )

    # Should exit with code 0 for help
    assert result.returncode == 0
    assert "GitHub issue collection and AI analysis" in result.stdout
