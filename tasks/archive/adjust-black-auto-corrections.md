# Task: Adjust Black Usage for Auto-Corrections

**Status:** complete

**Description:**
Update documentation to clarify that Black automatically applies formatting fixes. Currently the documentation only says "Black: Code formatting consistency" without mentioning that `uv run black .` automatically applies fixes. This causes agents to manually make formatting changes instead of letting Black handle them automatically.

**Root Issue:**
The current CLAUDE.md documentation does NOT mention that Black automatically applies fixes. It only lists "Black: Code formatting consistency" which doesn't tell agents that running `uv run black .` will automatically fix formatting issues. This is why agents are manually adjusting line lengths and other formatting.

**Acceptance Criteria:**
- [ ] Update CLAUDE.md to clarify that Black automatically applies fixes
- [ ] Update docs/api-reference.md to match CLAUDE.md exactly
- [ ] Add clear documentation that agents should NOT manually make formatting changes
- [ ] Specify when agents should intervene (syntax errors, actual failures)
- [ ] Ensure consistent messaging across all documentation

**Specific Commands to Use:**
- **Quality Check Command:** `uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`
- **Individual Black Command:** `uv run black .` (automatically applies fixes)
- **Check-only (for verification):** `uv run black --check .` (only when explicitly needed for validation)

**Documentation Updates Required:**

1. **CLAUDE.md** - Update the quality check section to clarify:
   - Black automatically applies formatting fixes
   - Agents should NOT manually make formatting changes
   - Only intervene if Black fails with actual errors (syntax errors, etc.)

2. **docs/api-reference.md** - Update to match CLAUDE.md exactly:
   - Lines 329-336 contain the quality check commands
   - Ensure identical wording to prevent confusion

**Key Messaging:**
- `uv run black .` **automatically applies** formatting fixes
- Agents should **not** manually edit files for formatting
- Only intervene when Black **fails** with actual errors
- Black handles all formatting according to pyproject.toml configuration

**Implementation Steps:**
1. Update CLAUDE.md quality check section with clear messaging
2. Update docs/api-reference.md to match CLAUDE.md exactly
3. Add specific guidance about when NOT to intervene
4. Test that the updated documentation is clear and consistent

**Agent Workflow:**
- **Correct:** Run `uv run black .` → Black applies fixes automatically → Continue
- **Incorrect:** Run `uv run black .` → See formatting changes → Manually edit files → Continue

**Validation:**
1. Update CLAUDE.md with clarified Black behavior
2. Update docs/api-reference.md to match exactly
3. Review both files to ensure consistent messaging
4. Verify no other documentation references Black usage