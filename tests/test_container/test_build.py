"""Tests for container build functionality."""

import subprocess
import pytest
from pathlib import Path


class TestContainerBuild:
    """Test container build process and basic functionality."""

    def test_containerfile_exists(self):
        """Test that Containerfile exists in project root."""
        containerfile = Path("Containerfile")
        assert containerfile.exists(), "Containerfile should exist in project root"

    def test_containerignore_exists(self):
        """Test that .containerignore exists for build optimization."""
        containerignore = Path(".containerignore")
        assert containerignore.exists(), (
            ".containerignore should exist for build optimization"
        )

    def test_entrypoint_script_exists(self):
        """Test that entrypoint script exists and is executable."""
        entrypoint = Path("scripts/container-entrypoint.sh")
        assert entrypoint.exists(), "Container entrypoint script should exist"
        assert entrypoint.is_file(), "Entrypoint should be a file"
        # Check if file has execute permissions (at least user execute)
        assert entrypoint.stat().st_mode & 0o100, (
            "Entrypoint script should be executable"
        )

    def test_entrypoint_script_has_shebang(self):
        """Test that entrypoint script has proper shebang."""
        entrypoint = Path("scripts/container-entrypoint.sh")
        with open(entrypoint, "r") as f:
            first_line = f.readline().strip()
        assert first_line == "#!/bin/bash", (
            "Entrypoint script should start with #!/bin/bash"
        )

    def test_entrypoint_script_validates_issue_url(self):
        """Test that entrypoint script validates ISSUE_URL environment variable."""
        entrypoint = Path("scripts/container-entrypoint.sh")
        with open(entrypoint, "r") as f:
            content = f.read()

        # Check that script validates ISSUE_URL
        assert 'if [ -z "$ISSUE_URL" ]' in content, "Script should validate ISSUE_URL"
        assert "exit 2" in content, (
            "Script should exit with code 2 for missing ISSUE_URL"
        )

    def test_entrypoint_script_activates_venv(self):
        """Test that entrypoint script activates virtual environment."""
        entrypoint = Path("scripts/container-entrypoint.sh")
        with open(entrypoint, "r") as f:
            content = f.read()

        # Check that script sets PATH to include venv
        assert '"/app/.venv/bin:/usr/local/bin:$PATH"' in content, (
            "Script should activate virtual environment"
        )

    def test_entrypoint_script_builds_command(self):
        """Test that entrypoint script builds proper command."""
        entrypoint = Path("scripts/container-entrypoint.sh")
        with open(entrypoint, "r") as f:
            content = f.read()

        # Check that script builds command with URL
        assert "gh-analysis process troubleshoot --url" in content, (
            "Script should build troubleshoot command"
        )
        assert "CLI_ARGS" in content, "Script should support optional CLI arguments"

    @pytest.mark.skipif(
        subprocess.run(["which", "podman"], capture_output=True).returncode != 0,
        reason="podman not available",
    )
    def test_container_builds_successfully(self):
        """Test that container builds without errors (requires podman)."""
        try:
            # Build the container
            result = subprocess.run(
                [
                    "podman",
                    "build",
                    "-f",
                    "Containerfile",
                    "-t",
                    "test-gh-analysis",
                    ".",
                ],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for build
            )

            assert result.returncode == 0, f"Container build failed: {result.stderr}"
            assert "test-gh-analysis" in result.stdout or not result.stderr, (
                "Container should build successfully"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Container build timed out after 5 minutes")
        except FileNotFoundError:
            pytest.skip("podman not available for container build test")

    @pytest.mark.skipif(
        subprocess.run(["which", "podman"], capture_output=True).returncode != 0,
        reason="podman not available",
    )
    def test_container_missing_issue_url_error(self):
        """Test that container exits with code 2 when ISSUE_URL is missing (requires podman)."""
        # First ensure container exists
        build_result = subprocess.run(
            ["podman", "build", "-f", "Containerfile", "-t", "test-gh-analysis", "."],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Container build failed, skipping test: {build_result.stderr}")

        try:
            # Run container without ISSUE_URL
            result = subprocess.run(
                ["podman", "run", "--rm", "test-gh-analysis"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            assert result.returncode == 2, (
                f"Container should exit with code 2 when ISSUE_URL missing, got {result.returncode}"
            )
            assert (
                "ERROR: ISSUE_URL environment variable is required" in result.stderr
            ), "Container should show error message for missing ISSUE_URL"

        except subprocess.TimeoutExpired:
            pytest.fail("Container run timed out")
        except FileNotFoundError:
            pytest.skip("podman not available for container test")

    def test_containerfile_has_required_components(self):
        """Test that Containerfile has all required components."""
        containerfile = Path("Containerfile")
        with open(containerfile, "r") as f:
            content = f.read()

        # Check for multi-stage build
        assert "FROM python:3.13-slim as builder" in content, (
            "Should use multi-stage build with Python 3.13"
        )
        assert "FROM python:3.13-slim" in content, "Should have runtime stage"

        # Check for UV installation
        assert "ghcr.io/astral-sh/uv:latest" in content, (
            "Should install UV from official image"
        )

        # Check for non-root user
        assert "useradd" in content, "Should create non-root user"
        assert "USER appuser" in content, "Should switch to non-root user"

        # Check for entrypoint
        assert "ENTRYPOINT" in content, "Should set entrypoint"
        assert "container-entrypoint.sh" in content, (
            "Should use container entrypoint script"
        )
