# Task: CLI Review and Normalization

**Status:** complete

**Description:**
Standardize CLI option patterns across all commands to ensure consistent shorthand options and prevent future drift. Currently, shorthand options like `-o` only work on some commands, `-h` for `--help` needs verification, and the `update-labels` command lacks any shorthand options. Create a unified CLI option standard with enforcement mechanisms to maintain consistency.

**Acceptance Criteria:**
- [ ] Create `cli/options.py` module with standardized option definitions and shorthand mappings
- [ ] Update all CLI command files to use standardized options from the shared module
- [ ] Ensure `-h` shorthand works for `--help` across all commands (verify Typer default behavior)
- [ ] Add shorthand options to `update-labels` command consistent with other commands
- [ ] Create CLI testing framework to validate option consistency across commands
- [ ] Create documentation of CLI option standards for future development
- [ ] All existing CLI functionality remains unchanged (no breaking changes)
- [ ] Tests pass for all CLI commands with both long and short option forms
- [ ] Code quality checks pass

**Implementation Plan:**

## Phase 1: Create Standardized Option Definitions

1. **Create `cli/options.py` module** with:
   ```python
   # Standard option definitions with consistent shorthand mappings
   ORG_OPTION = typer.Option(..., "--org", "-o", help="GitHub organization name")
   REPO_OPTION = typer.Option(None, "--repo", "-r", help="GitHub repository name")
   ISSUE_NUMBER_OPTION = typer.Option(None, "--issue-number", "-i", help="Specific issue number")
   LABELS_OPTION = typer.Option(None, "--labels", "-l", help="Filter by labels")
   DRY_RUN_OPTION = typer.Option(False, "--dry-run", "-d", help="Preview changes without applying")
   FORCE_OPTION = typer.Option(False, "--force", "-f", help="Apply changes without confirmation")
   ```

2. **Define option categories**:
   - **Core options** (org, repo, issue-number): Used across most commands
   - **Filter options** (labels, state, limit): Used for filtering operations  
   - **Behavior options** (dry-run, force, skip-comments): Control command behavior
   - **Data options** (model, thinking-effort, include-images): AI processing configuration

## Phase 2: Update Existing Commands

3. **Update `collect.py`**:
   - Replace individual option definitions with imports from `cli.options`
   - Maintain all existing functionality and option names
   - Add missing shorthand for options that should have them

4. **Update `batch.py`**:
   - Replace option definitions with standardized imports
   - Ensure consistent shorthand options across all batch subcommands

5. **Update `process.py`**:
   - Replace option definitions with standardized imports
   - Maintain existing AI processing options

6. **Update `update.py`** (highest priority):
   - Add shorthand options that are missing: `-o`, `-r`, `-i`, `-d`, `-f`
   - Use standardized option definitions
   - Ensure no functional changes to the command behavior

## Phase 3: Verification and Testing

7. **Verify `-h` for `--help`**:
   - Test that `uv run gh-analysis collect -h` works correctly
   - If not working, investigate Typer configuration needed
   - Document findings and fix if necessary

8. **Create CLI consistency tests**:
   ```python
   # Test that all commands support expected shorthand options
   def test_shorthand_consistency():
       # Test -o/--org works on all commands that should support it
       # Test -r/--repo works on all commands that should support it
       # Test -h/--help works on all commands
   ```

## Phase 4: Documentation and Standards

9. **Create CLI standards documentation** in `docs/cli-standards.md`:
   - Document all standardized options and their shorthand mappings
   - Provide guidelines for adding new CLI options
   - Include examples of correct usage patterns

10. **Add validation to prevent drift**:
    - Create test that validates new commands follow the standards
    - Add development guidelines to CLAUDE.md about using standardized options

**Current CLI Option Analysis:**

**Existing Shorthand Options:**
- `collect`: `--org/-o`, `--repo/-r`, `--labels/-l`, `--exclude-repo/-x` ✓
- `batch submit`: `--org/-o`, `--repo/-r` ✓
- `process product-labeling`: `--org/-o`, `--repo/-r` ✓  
- `update-labels`: **NO shorthand options** ❌

**Missing Shorthand Options to Add:**
- `update-labels`: needs `-o`, `-r`, `-i` (issue-number), `-d` (dry-run), `-f` (force)
- Consistent options across all commands where applicable

**Standard Shorthand Mapping:**
- `-o` → `--org` (organization)
- `-r` → `--repo` (repository)  
- `-i` → `--issue-number` (issue number)
- `-l` → `--labels` (labels filter)
- `-d` → `--dry-run` (dry run mode)
- `-f` → `--force` (force mode)
- `-h` → `--help` (help - should be automatic)
- `-x` → `--exclude-repo` (exclude repository)

**Agent Notes:**
This task addresses CLI inconsistency issues where shorthand options like `-o` only work on some commands. The main problems are:

1. **update-labels command lacks shorthand options** - users expect `-o` and `-r` to work consistently
2. **No shared option definitions** - each command defines options independently, leading to drift
3. **No enforcement mechanism** - nothing prevents future commands from having different patterns

The solution creates a centralized option definition system that ensures consistency and prevents future drift. All changes must be backwards compatible - no existing functionality should break.

**Testing Requirements:**
- Test all existing commands still work with long option names
- Test all commands work with new shorthand options  
- Test `-h` works for help on all commands
- Test that mixed long/short options work (e.g., `--org myorg -r myrepo`)
- Test edge cases like `collect -o org -r repo -l bug,feature`

**Validation:**

**Phase 1 - Core Framework:**
```bash
# Verify standardized options module exists and works
uv run python -c "from github_issue_analysis.cli.options import ORG_OPTION, REPO_OPTION; print('Options module works')"
```

**Phase 2 - Updated Commands:**
```bash
# Test collect command with shorthand options
uv run gh-analysis collect -o USER_PROVIDED_ORG -r USER_PROVIDED_REPO -i USER_PROVIDED_ISSUE_NUMBER --dry-run

# Test batch command with shorthand options  
uv run gh-analysis batch submit product-labeling -o USER_PROVIDED_ORG -r USER_PROVIDED_REPO --dry-run

# Test process command with shorthand options
uv run gh-analysis process product-labeling -o USER_PROVIDED_ORG -r USER_PROVIDED_REPO -i USER_PROVIDED_ISSUE_NUMBER --dry-run

# Test update-labels with NEW shorthand options (most important)
uv run gh-analysis update-labels -o USER_PROVIDED_ORG -r USER_PROVIDED_REPO -i USER_PROVIDED_ISSUE_NUMBER -d

# Test help shorthand works
uv run gh-analysis collect -h
uv run gh-analysis batch -h  
uv run gh-analysis update-labels -h
```

**Phase 3 - Consistency Validation:**
```bash
# Run CLI consistency tests
uv run pytest tests/test_cli/test_option_consistency.py -v

# Run existing CLI tests to ensure no regressions
uv run pytest tests/test_cli/ -v

# Quality checks must pass
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
```

**Phase 4 - Documentation Check:**
```bash
# Verify documentation was created
cat docs/cli-standards.md

# Verify CLAUDE.md was updated with CLI guidelines
grep -A 10 "CLI Standards" CLAUDE.md
```

**Success Criteria:**
- All commands support expected shorthand options consistently
- No breaking changes to existing functionality
- Future CLI commands will automatically follow the standard via shared option definitions
- Clear documentation exists for CLI option standards
- Tests prevent regression and enforce consistency

**Critical Requirements:**
- NEVER create any functionality that modifies GitHub data without `--dry-run` flag during testing
- All `update-labels` testing MUST use `--dry-run` to prevent posting to GitHub
- Maintain exact same command behavior, only adding shorthand options
- Backwards compatibility is mandatory - existing scripts must continue working