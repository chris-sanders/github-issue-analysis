**🚨 CRITICAL: ZERO TOLERANCE FOR CI FAILURES 🚨**

PRs that fail CI are unacceptable. ALL quality checks must pass locally before creating the PR.
If CI fails, it means local testing was insufficient. Fix the code, don't bypass tests.

Think very carefully about creating this pull request. I need you to:

1. **Determine the current task/branch context**:
   - Check if we're in a worktree directory (trees/*)
   - Identify the task name from the current branch or directory
   - Read the corresponding task file and branch name to determine the task name

2. **Validate the implementation is complete**:
   - Verify all acceptance criteria in the task file are met
   - Check that all code follows the established patterns
   - Ensure proper error handling and type annotations are in place

3. **Run comprehensive quality checks (CRITICAL - CI MUST NOT FAIL)**:
   - Execute: `uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest`
   - **MANDATORY**: All four commands MUST pass with zero failures/errors before proceeding
   - If ANY tool fails, fix the code to pass the checks - NEVER bypass or skip tests even if it's not related to your changes.
   - Re-run the full command chain until ALL tools pass completely
   - This exact command chain runs in CI - if it fails locally, it WILL fail in CI

4. **Perform manual testing (VERIFY FUNCTIONALITY WORKS)**:
   - Run the validation commands specified in the task file
   - Test the new functionality with specific examples from the requirements
   - Document what was tested and verified
   - **CRITICAL**: Test that all new CLI commands/features actually work as expected

5. **Prepare and create the commit**:
   - Ensure all changes are staged
   - Create commit with clear, concise message (NO Claude Code credit)
   - Follow the project's commit message standards

6. **Push and create PR**:
   - Push the branch: `git push -u origin feature/[task-name]`
   - Create PR with: `gh pr create --title "[Title]" --body "[Body]"`

7. **PR content should include**:
   - **Summary**: Concise bullets of real functionality added
   - **Testing**: Specific commands run and confirmation that ALL passed locally
   - **Manual validation**: Steps taken to confirm functionality works
   - Remain concise focusing on real functionality added and tests/validation run

Task for PR: $ARGUMENTS

Focus on clear communication about what was delivered and how it was validated, verbosity does not mean clarity.
