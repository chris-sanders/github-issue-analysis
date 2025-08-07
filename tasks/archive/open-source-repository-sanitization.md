# Task: Open Source Repository Sanitization

**Status:** complete

**Description:**
Sanitize the GitHub issue analysis repository for open source release by removing customer references from documentation and task templates, implementing protections against future customer data exposure, and ensuring all examples prompt users for runtime input rather than hardcoding customer information.

## Acceptance Criteria

### Documentation Sanitization (Priority 1 - Required)
- [ ] Update `CLAUDE.md` to replace customer examples with runtime prompts
- [ ] Update `docs/api-reference.md` to use generic placeholder patterns
- [ ] Update `github_issue_analysis/cli/collect.py` docstring examples
- [ ] Update `README.md` to use generic examples throughout
- [ ] Update `docs/data-schemas.md` to use generic organization/repository names
- [ ] Remove or anonymize `model_comparison_summary.md` (contains real customer analysis)

### Task Template Updates (Priority 2 - Required)
- [ ] Update all task files in `tasks/` directory to instruct agents to ask users for test repositories at runtime
- [ ] Update task validation steps to use `--dry-run` and user-provided test data
- [ ] Remove hardcoded customer references from all task examples and validation commands
- [ ] Ensure task templates follow pattern: "Ask user to provide test organization/repository at runtime"

### Git History Sanitization (Priority 3 - CRITICAL REQUIRED)
- [ ] Install git-filter-repo: `uv add git-filter-repo`
- [ ] Use `git filter-repo` to permanently remove `dryRun.md` and `dryRun2.md` from all git history
- [ ] Remove any other customer data files found in git history  
- [ ] Verify git history is completely clean of customer references after sanitization
- [ ] Force push sanitized history to replace remote repository history

### AI Logic Review (Priority 4 - Assessment Required)
- [ ] Review `github_issue_analysis/ai/prompts.py` for product-specific logic that should remain vs customer-specific logic that should be genericized
- [ ] Determine if Replicated domain references (`*.replicated.com`) are legitimate product logic or should be parameterized
- [ ] Ensure AI prompts work with generic customer data

### Protection Implementation (Priority 5 - Proactive)
- [ ] Create `/tmp` directory for agent temporary files
- [ ] Add `/tmp/` to `.gitignore` to prevent temporary files from being committed
- [ ] Add explicit instruction to `CLAUDE.md`: "Never write files to the root directory. Use `/tmp/` for any temporary/analysis files."
- [ ] Enhance `.gitignore` with additional customer data protection patterns
- [ ] Create documentation on safe development practices with customer data

## Implementation Notes

### Key Findings from Analysis
1. **CRITICAL**: Git history contains customer data exposure - `dryRun.md` and `dryRun2.md` files contained real customer issue analysis with company names
2. **Customer Data Files**: Found deleted files with 1,247+ lines of actual customer issue data (removed July 7, 2025)
3. **Runtime Data**: `/data` directory currently contains extensive customer data but is now properly ignored by git
4. **Limited Documentation Scope**: 18 committed files need customer reference updates in documentation
5. **No Customer Logic**: No hardcoded customer-specific business logic found in core functionality
6. **Test Data Clean**: Test files properly use mock data patterns

### Files Requiring Updates (18 total committed files with customer references)

**Priority 1 - User-Facing Documentation (6 files):**
- `CLAUDE.md` (line 165: customer-specific example)
- `README.md` (lines 16, 22, 34, 37: microsoft/vscode examples)  
- `docs/api-reference.md` (multiple customer examples)
- `docs/data-schemas.md` (microsoft/vscode in JSON schemas)
- `github_issue_analysis/cli/collect.py` (lines 86-88: docstring examples)
- `model_comparison_summary.md` (real customer analysis data)

**Priority 2 - Task Templates (12 files in tasks/ and tasks/archive/):**
- All task files containing customer references need to instruct agents to ask users for test repositories at runtime

### Replacement Patterns

**Instead of hardcoded examples like:**
```bash
# Ask user to provide test organization, repository, and issue number for validation
# Example: uv run github-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number USER_PROVIDED_ISSUE_NUMBER
```

**Use runtime prompts like:**
```bash
# Ask user for test repository
uv run github-analysis collect --org YOUR_ORG --repo YOUR_REPO --issue-number 123 --dry-run
```

**Task templates should instruct:**
```markdown
**Validation:**
- Ask user to provide a test organization and repository for validation
- Run with --dry-run flag: `uv run github-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --dry-run`
```

### Implementation Approach

**Git History Sanitization Required**
- **CRITICAL**: Git history contains customer data from deleted `dryRun.md` and `dryRun2.md` files
- **Customer Data Period**: Files contained real customer issue analysis with company names (deleted July 7, 2025)
- **Risk**: Git history permanently contains customer data unless rewritten
- **Decision Required**: Either accept customer data remains in git history OR perform git history rewrite to remove customer data entirely

**Current Repository Sanitization Steps:**
1. Remove customer references from documentation (18 files)
2. Ensure `/data` directory remains properly ignored
3. Implement protections against future customer data exposure
4. Address git history customer data exposure per user decision

## Agent Instructions

**CRITICAL: Execute ALL 5 sub-agents in parallel using a SINGLE message with 5 Task tool calls.**

**DO NOT execute sub-agents sequentially or in phases. Use ONE message containing 5 parallel Task tool calls like this:**
```
<invoke name="Task">...</invoke>
<invoke name="Task">...</invoke>
<invoke name="Task">...</invoke>
<invoke name="Task">...</invoke>
<invoke name="Task">...</invoke>
```

All sub-agents must use consistent replacement patterns:
- Customer examples → `YOUR_ORG` / `YOUR_REPO` / issue `123`
- Generic examples → `example-org` / `example-repo`
- Always include `--dry-run` in validation commands

### Parallel Sub-Agent Tasks (Execute all 4 simultaneously)

**Sub-agent 1: Core Documentation Sanitization**
```
Task: "Sanitize core documentation files for open source release. Update the following files to replace all customer references with generic runtime prompts:

Files to update:
- CLAUDE.md (line 165: USER_PROVIDED_ORG/USER_PROVIDED_REPO example)
- README.md (lines 16, 22, 34, 37: microsoft/vscode examples)  
- github_issue_analysis/cli/collect.py (lines 86-88: docstring examples)

Replacement patterns:
- Replace 'USER_PROVIDED_ORG' → 'YOUR_ORG' 
- Replace customer repository references → 'YOUR_REPO'
- Replace 'microsoft' → 'YOUR_ORG'
- Replace 'vscode' → 'YOUR_REPO'
- Use issue number 123 instead of 71
- Add --dry-run to all validation commands

Ensure examples prompt users to provide their own test repositories at runtime."
```

**Sub-agent 2: API Documentation Sanitization**
```
Task: "Sanitize API and schema documentation for open source release. Update the following files:

Files to update:
- docs/api-reference.md (multiple customer examples throughout)
- docs/data-schemas.md (microsoft/vscode in JSON schemas)
- model_comparison_summary.md (handle real customer analysis data)

Replacement patterns:
- Replace all 'microsoft/vscode' → 'example-org/example-repo'
- Replace 'USER_PROVIDED_ORG' → 'example-org'
- Update JSON schema examples to use generic data
- For model_comparison_summary.md: either anonymize customer data or recommend moving to secure location

Maintain functional accuracy while removing customer-specific information."
```

**Sub-agent 3: Git History Sanitization**
```
Task: "CRITICAL: Permanently remove customer data files from git history.

Required steps:
1. Install git-filter-repo: uv add git-filter-repo
2. Remove customer data files from ALL git history:
   git filter-repo --path dryRun.md --invert-paths
   git filter-repo --path dryRun2.md --invert-paths
3. Verify history is clean: git log --all --name-only | grep -E 'dryRun\.md|dryRun2\.md' (should return nothing)
4. Check for any other customer data files in history and remove them
5. Force push sanitized history: git push --force-with-lease

WARNING: This permanently rewrites git history. Ensure you're working in a fresh repository clone."
```

**Sub-agent 4: Task Template Sanitization** 
```
Task: "Update all task template files to remove customer references and instruct future agents to ask users for test repositories at runtime.

Files to update: All files in tasks/ and tasks/archive/ directories containing 'USER_PROVIDED_ORG' references (12 files total based on analysis)

Required changes:
1. Replace hardcoded customer examples with instructions like: 'Ask user to provide test organization and repository for validation'
2. Update validation sections to use pattern: 'uv run github-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --dry-run'
3. Ensure all validation commands include --dry-run flag
4. Use consistent instruction pattern: 'Ask user to provide test organization/repository at runtime'

Maintain task functionality while ensuring no hardcoded customer data remains."
```

**Sub-agent 5: AI Logic Review and Protection Setup**
```
Task: "Review AI logic for customer-specific patterns and implement protections against future customer data exposure.

Responsibilities:
1. Review github_issue_analysis/ai/prompts.py for customer-specific logic vs legitimate product logic
2. Determine if Replicated domain references (*.replicated.com) should remain or be parameterized
3. Create /tmp directory for agent temporary files
4. Add /tmp/ to .gitignore to prevent temporary files from being committed
5. Add explicit instruction to CLAUDE.md: 'Never write files to the root directory. Use /tmp/ for any temporary/analysis files.'
6. Enhance .gitignore with additional customer data protection patterns

Focus on protecting against future customer data exposure while preserving legitimate product functionality."
```

### After Parallel Execution Complete
1. **Consistency Check**: Verify all files use consistent placeholder patterns
2. **Validation**: Run all validation commands to ensure no customer references remain  
3. **Testing**: Ensure all CLI functionality works with generic examples

**REMEMBER: Execute all 5 Task tool calls in a SINGLE message for true parallel execution.**

## Validation Commands

### Pre-Sanitization Validation
```bash
# Find remaining customer references (should return specific files before sanitization)
git ls-tree -r HEAD --name-only | xargs grep -l "USER_PROVIDED_ORG\|pixee-replicated\|microsoft.*vscode"

# Count total files with customer references  
git ls-tree -r HEAD --name-only | xargs grep -l "USER_PROVIDED_ORG" | wc -l
```

### Post-Sanitization Validation  
```bash
# Should return no results after sanitization
git ls-tree -r HEAD --name-only | xargs grep -l "USER_PROVIDED_ORG\|pixee-replicated" || echo "Clean!"

# Test CLI with generic examples
uv run github-analysis collect --help | grep -E "(YOUR_ORG|example-org)"

# Ensure quality checks pass
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest

# Test pre-commit hooks (if implemented)
echo "USER_PROVIDED_ORG test" > test_file.md && git add test_file.md && git commit -m "test" 
# Should fail with customer data detection
git reset HEAD^ && rm test_file.md
```

### Documentation Validation
```bash
# Verify examples use generic patterns
grep -r "YOUR_ORG\|example-org" docs/ CLAUDE.md README.md

# Confirm no hardcoded customer examples remain
grep -r "USER_PROVIDED_ORG\|pixee\|microsoft.*vscode" docs/ CLAUDE.md README.md || echo "Clean documentation!"
```

## Risk Assessment and Mitigation

### Low Risk - Most of repository is clean
- Git history contains no customer data in commits
- Core business logic has no hardcoded customer references  
- Test files properly use mock data
- `/data` directory properly excluded from git

### Medium Risk - Documentation contains customer examples
- Limited to 18 committed files with customer references
- Primarily in documentation and task templates
- No exposure of sensitive customer data (only public repository names)

### Mitigation Strategy
- Replace examples with runtime prompts to users
- Implement detection hooks to prevent future customer data exposure
- Clear documentation on safe development practices
- Maintain functionality while removing specific customer references

## Success Criteria

1. **Zero hardcoded customer references** in committed documentation and code
2. **Functional equivalence** - all CLI commands and workflows work with user-provided test data
3. **Protection implemented** - hooks and documentation prevent future customer data exposure
4. **Documentation clarity** - examples clearly prompt users for runtime input
5. **Tests pass** - all existing functionality preserved
6. **Git history preserved** - maintain commit history and attribution (unless fresh repo needed)

This approach maintains the valuable development history while ensuring customer data protection and creating a clean foundation for open source release.