# CLI Standards and Options Reference

This document defines the standardized CLI option patterns used across all commands in the GitHub Issue Analysis tool. These standards ensure consistent user experience and prevent option drift across the codebase.

## Standardized Option Definitions

All CLI commands use centralized option definitions from `github_issue_analysis.cli.options` to ensure consistency.

### Core Options

These options are used across most commands for basic GitHub repository targeting:

| Short | Long | Type | Description | Used In |
|-------|------|------|-------------|---------|
| `-o` | `--org` | str | GitHub organization name | collect, batch, process, update-labels |
| `-r` | `--repo` | str | GitHub repository name | collect, batch, process, update-labels |
| `-i` | `--issue-number` | int | Specific issue number | collect, batch, process, update-labels |

### Filter Options

Options used for filtering and limiting data collection:

| Short | Long | Type | Description | Used In |
|-------|------|------|-------------|---------|
| `-l` | `--labels` | list[str] | Filter by labels (multiple values) | collect |
| `-s` | `--state` | str | Issue state: open, closed, or all | collect |
| `-x` | `--exclude-repo` | list[str] | Exclude repositories (multiple values) | collect |
| | `--limit` | int | Maximum number of items | collect |

### Behavior Options

Options that control command behavior and execution:

| Short | Long | Type | Description | Used In |
|-------|------|------|-------------|---------|
| `-d` | `--dry-run` | bool | Preview changes without applying | batch, process, update-labels |
| `-f` | `--force` | bool | Apply changes without confirmation | batch, update-labels |
| `-h` | `--help` | bool | Show help message and exit | ALL COMMANDS |

### Data Processing Options

Options for configuring AI processing and model behavior:

| Short | Long | Type | Description | Used In |
|-------|------|------|-------------|---------|
| `-m` | `--model` | str | AI model to use | batch, process |
| | `--thinking-effort` | str | Reasoning effort level | batch, process |
| | `--thinking-budget` | int | Token budget for thinking | batch, process |
| | `--include-images` | bool | Include image analysis | batch, process |

### Authentication and Configuration

| Short | Long | Type | Description | Used In |
|-------|------|------|-------------|---------|
| `-t` | `--token` | str | GitHub API token | collect |
| | `--data-dir` | str | Data directory path | update-labels |

## Implementation Guidelines

### For New Commands

When creating new CLI commands, follow these guidelines:

1. **Import standardized options** from `github_issue_analysis.cli.options`:
   ```python
   from .options import (
       ORG_OPTION,
       REPO_OPTION,
       ISSUE_NUMBER_OPTION,
       DRY_RUN_OPTION,
       # ... other needed options
   )
   ```

2. **Use imported options in function signatures**:
   ```python
   @app.command()
   def my_command(
       org: str | None = ORG_OPTION,
       repo: str | None = REPO_OPTION,
       dry_run: bool = DRY_RUN_OPTION,
   ) -> None:
       """My command description."""
       # Implementation here
   ```

3. **Enable -h help shorthand** in your Typer app:
   ```python
   app = typer.Typer(
       help="My command help",
       context_settings={"help_option_names": ["-h", "--help"]}
   )
   ```

### For New Options

When adding new standardized options:

1. **Add to `cli/options.py`** with appropriate shorthand:
   ```python
   MY_NEW_OPTION = typer.Option(
       default_value, "--my-option", "-m", help="Description"
   )
   ```

2. **Choose shorthand carefully** to avoid conflicts:
   - Check existing mappings in this document
   - Run tests to ensure no conflicts
   - Follow logical patterns (e.g., `-o` for organization)

3. **Update this documentation** with the new option.

## Shorthand Option Mappings

### Reserved Shorthands

These single-letter shorthands are reserved and standardized:

- `-d` → `--dry-run` (preview mode)
- `-f` → `--force` (skip confirmations)
- `-h` → `--help` (show help)
- `-i` → `--issue-number` (issue targeting)
- `-l` → `--labels` (label filtering)
- `-m` → `--model` (AI model selection)
- `-o` → `--org` (GitHub organization)
- `-r` → `--repo` (GitHub repository)
- `-s` → `--state` (issue state)
- `-t` → `--token` (authentication)
- `-x` → `--exclude-repo` (repository exclusion)

### Available Shorthands

These letters are available for future use:
`-a`, `-b`, `-c`, `-e`, `-g`, `-j`, `-k`, `-n`, `-p`, `-q`, `-u`, `-v`, `-w`, `-y`, `-z`

## Command-Specific Examples

### collect Command
```bash
# Using standardized options
uv run gh-analysis collect -o myorg -r myrepo -i 123 -l bug,enhancement

# Full form equivalent
uv run gh-analysis collect --org myorg --repo myrepo --issue-number 123 --labels bug --labels enhancement
```

### update-labels Command  
```bash
# Using new shorthand options (added in CLI normalization)
uv run gh-analysis update-labels -o myorg -r myrepo -i 123 -d

# Full form equivalent
uv run gh-analysis update-labels --org myorg --repo myrepo --issue-number 123 --dry-run
```

### batch Command
```bash
# Batch processing with shorthand
uv run gh-analysis batch submit product-labeling -o myorg -r myrepo -d

# Full form equivalent  
uv run gh-analysis batch submit product-labeling --org myorg --repo myrepo --dry-run
```

## Testing Standards

### CLI Consistency Tests

The `tests/test_cli/test_option_consistency.py` file contains automated tests that verify:

1. **Help shorthand works** (`-h`) on all commands
2. **Core options consistency** (`-o`, `-r`, `-i`) across commands
3. **Behavior options consistency** (`-d`, `-f`) where applicable
4. **No conflicting shorthands** within any command
5. **Mixed short/long options** work correctly

### Running Tests

```bash
# Test CLI option consistency
uv run pytest tests/test_cli/test_option_consistency.py -v

# Test all CLI functionality
uv run pytest tests/test_cli/ -v
```

## Validation Commands

Test that shorthand options work correctly:

```bash
# Test help shorthand on all commands
uv run gh-analysis collect -h
uv run gh-analysis batch -h
uv run gh-analysis process -h
uv run gh-analysis update-labels -h

# Test specific shorthand options
uv run gh-analysis collect -o test-org --dry-run
uv run gh-analysis update-labels -o test-org -r test-repo -d
uv run gh-analysis batch submit product-labeling -o test-org -d
```

## Migration Notes

### Before CLI Normalization

- `update-labels` command had NO shorthand options
- `-h` help shorthand was not available on any command
- Option definitions were duplicated across command files
- No enforcement mechanism for consistency

### After CLI Normalization

- All commands support `-h` for help
- `update-labels` supports `-o`, `-r`, `-i`, `-d`, `-f` shorthands
- Centralized option definitions prevent drift
- Automated tests enforce consistency
- Clear documentation and standards

## Troubleshooting

### Common Issues

1. **"No such option: -h"**
   - Ensure your Typer app includes `context_settings={"help_option_names": ["-h", "--help"]}`

2. **Shorthand conflicts**
   - Check this document for reserved shorthands
   - Run consistency tests to detect conflicts

3. **Missing shorthand options**
   - Import from `cli.options` instead of defining inline
   - Follow the implementation guidelines above

### Getting Help

For questions about CLI standards or to report inconsistencies:

1. Check existing tests in `tests/test_cli/test_option_consistency.py`
2. Review this documentation
3. Ensure your changes pass all CLI tests
4. Follow the implementation guidelines for new commands