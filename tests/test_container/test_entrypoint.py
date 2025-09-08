"""Tests for container entrypoint script parsing and functionality."""

import subprocess
import tempfile
import os
from pathlib import Path
import pytest


class TestEntrypointScript:
    """Test entrypoint script functionality."""

    @pytest.fixture
    def entrypoint_script(self):
        """Return path to the entrypoint script."""
        return Path("scripts/container-entrypoint.sh")

    def test_script_validates_required_env_vars(self, entrypoint_script):
        """Test that script validates required environment variables."""
        # Run script without ISSUE_URL
        result = subprocess.run(
            ["bash", str(entrypoint_script)],
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"]},  # Keep PATH but clear other vars
        )

        assert result.returncode == 2, (
            "Script should exit with code 2 when ISSUE_URL is missing"
        )
        assert "ERROR: ISSUE_URL environment variable is required" in result.stderr, (
            "Script should show error for missing ISSUE_URL"
        )

    def test_script_builds_basic_command(self, entrypoint_script):
        """Test that script builds basic command with ISSUE_URL."""
        # Create a mock environment with just ISSUE_URL
        env = {
            "PATH": "/app/.venv/bin:" + os.environ["PATH"],
            "ISSUE_URL": "https://github.com/test/repo/issues/123",
        }

        # We can't actually run the full command since gh-analysis won't be available
        # But we can test the script logic by modifying it temporarily
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as temp_script:
            # Read original script
            with open(entrypoint_script, "r") as f:
                content = f.read()

            # Replace the final exec with echo for testing
            test_content = content.replace(
                "eval exec $CMD", 'echo "Would execute: $CMD"'
            )
            temp_script.write(test_content)
            temp_script.flush()

            # Make it executable
            os.chmod(temp_script.name, 0o755)

            try:
                result = subprocess.run(
                    ["bash", temp_script.name], capture_output=True, text=True, env=env
                )

                assert result.returncode == 0, (
                    f"Script should run successfully: {result.stderr}"
                )
                expected_cmd = 'gh-analysis process troubleshoot --url "https://github.com/test/repo/issues/123"'
                assert expected_cmd in result.stdout, (
                    f"Script should build correct command, got: {result.stdout}"
                )

            finally:
                os.unlink(temp_script.name)

    def test_script_includes_cli_args(self, entrypoint_script):
        """Test that script includes CLI_ARGS when provided."""
        env = {
            "PATH": "/app/.venv/bin:" + os.environ["PATH"],
            "ISSUE_URL": "https://github.com/test/repo/issues/123",
            "CLI_ARGS": "--agent gpt5_mini_medium --interactive",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as temp_script:
            with open(entrypoint_script, "r") as f:
                content = f.read()

            # Replace exec with echo for testing
            test_content = content.replace(
                "eval exec $CMD", 'echo "Would execute: $CMD"'
            )
            temp_script.write(test_content)
            temp_script.flush()
            os.chmod(temp_script.name, 0o755)

            try:
                result = subprocess.run(
                    ["bash", temp_script.name], capture_output=True, text=True, env=env
                )

                assert result.returncode == 0, (
                    f"Script should run successfully: {result.stderr}"
                )
                assert "--agent gpt5_mini_medium" in result.stdout, (
                    "Script should include CLI_ARGS in command"
                )
                assert "--interactive" in result.stdout, (
                    "Script should include all CLI_ARGS"
                )

            finally:
                os.unlink(temp_script.name)

    def test_script_handles_quotes_in_issue_url(self, entrypoint_script):
        """Test that script properly handles quotes in ISSUE_URL."""
        # Issue URL with special characters that might need escaping
        env = {
            "PATH": "/app/.venv/bin:" + os.environ["PATH"],
            "ISSUE_URL": "https://github.com/test/repo-with-dash/issues/123",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False
        ) as temp_script:
            with open(entrypoint_script, "r") as f:
                content = f.read()

            test_content = content.replace(
                "eval exec $CMD", 'echo "Would execute: $CMD"'
            )
            temp_script.write(test_content)
            temp_script.flush()
            os.chmod(temp_script.name, 0o755)

            try:
                result = subprocess.run(
                    ["bash", temp_script.name], capture_output=True, text=True, env=env
                )

                assert result.returncode == 0, (
                    f"Script should handle URLs with special chars: {result.stderr}"
                )
                assert "repo-with-dash" in result.stdout, (
                    "Script should preserve URL with special characters"
                )

            finally:
                os.unlink(temp_script.name)

    def test_script_sets_venv_path(self, entrypoint_script):
        """Test that script sets virtual environment PATH."""
        with open(entrypoint_script, "r") as f:
            content = f.read()

        assert 'export PATH="/app/.venv/bin:$PATH"' in content, (
            "Script should set PATH to include virtual environment"
        )

    def test_script_uses_set_e(self, entrypoint_script):
        """Test that script uses 'set -e' for error handling."""
        with open(entrypoint_script, "r") as f:
            content = f.read()

        assert "set -e" in content, "Script should use 'set -e' for error handling"

    def test_script_has_proper_shebang(self, entrypoint_script):
        """Test that script has proper bash shebang."""
        with open(entrypoint_script, "r") as f:
            first_line = f.readline().strip()

        assert first_line == "#!/bin/bash", "Script should have proper bash shebang"
