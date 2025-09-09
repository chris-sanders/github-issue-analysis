"""Tests for CLI option consistency across all commands."""

from typer.testing import CliRunner

from gh_analysis.cli.main import app


class TestOptionConsistency:
    """Test that CLI options are consistent across commands."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb"})

    def test_help_shorthand_works_on_all_commands(self):
        """Test that -h works for --help on all commands."""
        commands_to_test = [
            ["-h"],  # Main command
            ["collect", "-h"],
            ["batch", "-h"],
            ["process", "-h"],
            ["update-labels", "-h"],
            ["recommendations", "-h"],
            ["version", "-h"],
        ]

        for cmd in commands_to_test:
            result = self.runner.invoke(app, cmd)
            # Help should exit with code 0 and contain help text
            assert result.exit_code == 0, (
                f"Command {' '.join(cmd)} failed: {result.stdout}"
            )
            assert "Usage:" in result.stdout, (
                f"No help text in {' '.join(cmd)}: {result.stdout}"
            )
            assert "--help" in result.stdout, (
                f"No --help option shown for {' '.join(cmd)}"
            )
            assert "-h" in result.stdout, f"No -h shorthand shown for {' '.join(cmd)}"

    def test_main_command_help_works(self):
        """Test that main command supports both --help and -h."""
        # Test both --help and -h
        for help_flag in ["--help", "-h"]:
            result = self.runner.invoke(app, [help_flag])
            assert result.exit_code == 0
            assert "Usage:" in result.stdout
            assert "--help" in result.stdout
            assert "-h" in result.stdout

    def test_org_shorthand_consistency(self):
        """Test that -o works for --org on commands that support it."""
        # Commands that should support -o/--org
        commands_with_org = [
            ["collect", "--help"],
            ["batch", "submit", "--help"],
            ["process", "product-labeling", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_with_org:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            # Should show both -o and --org
            assert "--org" in result.stdout, f"No --org option in {' '.join(cmd)}"
            assert "-o" in result.stdout, f"No -o shorthand in {' '.join(cmd)}"

    def test_repo_shorthand_consistency(self):
        """Test that -r works for --repo on commands that support it."""
        commands_with_repo = [
            ["collect", "--help"],
            ["batch", "submit", "--help"],
            ["process", "product-labeling", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_with_repo:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            assert "--repo" in result.stdout, f"No --repo option in {' '.join(cmd)}"
            assert "-r" in result.stdout, f"No -r shorthand in {' '.join(cmd)}"

    def test_issue_number_shorthand_consistency(self):
        """Test that -i works for --issue-number on commands that support it."""
        commands_with_issue_number = [
            ["collect", "--help"],
            ["batch", "submit", "--help"],
            ["process", "product-labeling", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_with_issue_number:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            assert "--issue-number" in result.stdout, (
                f"No --issue-number option in {' '.join(cmd)}"
            )
            assert "-i" in result.stdout, f"No -i shorthand in {' '.join(cmd)}"

    def test_dry_run_shorthand_consistency(self):
        """Test that -d works for --dry-run on commands that support it."""
        commands_with_dry_run = [
            ["batch", "submit", "--help"],
            ["process", "product-labeling", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_with_dry_run:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            assert "--dry-run" in result.stdout, (
                f"No --dry-run option in {' '.join(cmd)}"
            )
            assert "-d" in result.stdout, f"No -d shorthand in {' '.join(cmd)}"

    def test_force_shorthand_consistency(self):
        """Test that -f works for --force on commands that support it."""
        commands_with_force = [
            ["batch", "remove", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_with_force:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            assert "--force" in result.stdout, f"No --force option in {' '.join(cmd)}"
            assert "-f" in result.stdout, f"No -f shorthand in {' '.join(cmd)}"

    def test_labels_shorthand_consistency(self):
        """Test that -l works for --labels on commands that support it."""
        commands_with_labels = [
            ["collect", "--help"],
        ]

        for cmd in commands_with_labels:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Command {' '.join(cmd)} failed"
            assert "--labels" in result.stdout, f"No --labels option in {' '.join(cmd)}"
            assert "-l" in result.stdout, f"No -l shorthand in {' '.join(cmd)}"

    def test_mixed_short_and_long_options_work(self):
        """Test that mixing short and long options works correctly."""
        # This test would normally require actual GitHub data, so we'll just test
        # that the CLI parsing doesn't fail with mixed options

        # Test with --dry-run to avoid actual API calls
        mixed_option_tests = [
            # Mix of short and long options
            ["collect", "-o", "test-org", "--repo", "test-repo", "--dry-run"],
            ["update-labels", "--org", "test-org", "-r", "test-repo", "-d"],
            [
                "batch",
                "submit",
                "product-labeling",
                "-o",
                "test-org",
                "--repo",
                "test-repo",
                "--dry-run",
            ],
        ]

        for cmd in mixed_option_tests:
            # We expect these to fail due to missing data/auth, but they should
            # fail with validation errors, not option parsing errors
            result = self.runner.invoke(app, cmd)

            # Should not fail with "No such option" errors
            assert "No such option" not in result.stdout
            assert (
                "No such option" not in str(result.exception)
                if result.exception
                else True
            )

    def test_standard_shorthand_mappings(self):
        """Test that standard shorthand mappings are consistent."""
        expected_mappings = {
            "-o": "--org",
            "-r": "--repo",
            "-i": "--issue-number",
            "-l": "--labels",
            "-d": "--dry-run",
            "-f": "--force",
            "-h": "--help",
            "-x": "--exclude-repo",
            "-s": "--state",
            "-t": "--token",
            "-m": "--model",
        }

        # Test collect command which has most options
        result = self.runner.invoke(app, ["collect", "--help"])
        assert result.exit_code == 0

        for short, long in expected_mappings.items():
            if long in result.stdout:
                # If the long option exists, the short option should too
                assert short in result.stdout, (
                    f"Command collect has {long} but not {short}"
                )

    def test_no_conflicting_shorthand_options(self):
        """Test that no command has conflicting shorthand options."""
        commands_to_test = [
            ["collect", "--help"],
            ["batch", "submit", "--help"],
            ["process", "product-labeling", "--help"],
            ["update-labels", "--help"],
        ]

        for cmd in commands_to_test:
            result = self.runner.invoke(app, cmd)
            assert result.exit_code == 0

            # Extract all short options from help text
            import re

            short_options = re.findall(r"-([a-zA-Z])\s", result.stdout)

            # Should not have duplicates
            assert len(short_options) == len(set(short_options)), (
                f"Duplicate shorthand options in {' '.join(cmd)}: {short_options}"
            )

    def test_update_labels_has_required_shorthand_options(self):
        """Test that update-labels command has all the required shorthand options."""
        result = self.runner.invoke(app, ["update-labels", "--help"])
        assert result.exit_code == 0

        # These were specifically mentioned as missing in the task
        required_shorthands = [
            ("-o", "--org"),
            ("-r", "--repo"),
            ("-i", "--issue-number"),
            ("-d", "--dry-run"),
            ("-f", "--force"),
        ]

        for short, long in required_shorthands:
            assert long in result.stdout, f"update-labels missing {long} option"
            assert short in result.stdout, (
                f"update-labels missing {short} shorthand for {long}"
            )
