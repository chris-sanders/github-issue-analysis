# Task: Clarify Confidence Scores

**Status:** complete

**Description:**
Simplify and standardize the confidence scoring system to provide clear, consistent confidence metrics for AI-driven label recommendations. The current system has multiple confidence scores with unclear meanings and inconsistent usage. This task will implement a unified confidence model with at most 2 confidence scores: optional root cause confidence and required overall recommendation confidence.

**Problem Analysis:**
The current confidence scoring system has several issues:
1. **Multiple confusing confidence scores**: Overall confidence, individual label confidence, and calculated removal confidence
2. **Unclear semantics**: Models and filtering logic are unclear about what confidence means
3. **Inconsistent usage**: Different components interpret confidence differently
4. **Complex filtering**: Separate confidence thresholds for additions vs removals complicate decision-making

**Solution:**
Implement a simplified confidence model:
- **Root cause confidence** (optional): Confidence in identified root cause (0-1). Only provided if a specific root cause is defined.
- **Recommendation confidence** (required): Overall confidence in the complete label recommendation (0-1).
- **Single filtering threshold**: All decisions use recommendation confidence only.

**Acceptance Criteria:**
- [ ] Update `ProductLabelingResponse` model to use simplified confidence structure
- [ ] Remove individual label confidence from `RecommendedLabel`
- [ ] Update prompts to request only the two defined confidence scores
- [ ] Modify `ChangeDetector` to use only `recommendation_confidence` for ALL filtering decisions (no more multiple confidence scores)
- [ ] Update comment generation to display simplified confidence information
- [ ] Create validation tests for new confidence model
- [ ] Run quality checks and ensure all tests pass

**Implementation Steps:**

### 1. Update Data Models (`ai/models.py`)

Replace the current confidence structure with:

```python
class RecommendedLabel(BaseModel):
    """A recommended product label with reasoning (no individual confidence)."""
    
    label: ProductLabel
    reasoning: str = Field(description="Explanation for this recommendation")


class ProductLabelingResponse(BaseModel):
    """Structured response for product labeling analysis."""
    
    root_cause_analysis: str = Field(
        default="Root cause unclear",
        description="Root cause analysis of the issue. "
        "State 'Root cause unclear' if unable to determine.",
    )
    root_cause_confidence: float | None = Field(
        default=None,
        description="Confidence in identified root cause (0-1). "
        "Only provide if a specific root cause is defined.",
    )
    recommendation_confidence: float = Field(
        description="Overall confidence in the complete label recommendation (0-1)"
    )
    recommended_labels: list[RecommendedLabel] = Field(
        description="Suggested product labels"
    )
    current_labels_assessment: list[LabelAssessment] = Field(
        description="Assessment of existing labels"
    )
    summary: str = Field(
        description="Brief summary of the issue's product classification"
    )
    reasoning: str = Field(description="Detailed reasoning for label recommendations")
    
    # Image-related fields remain unchanged
    images_analyzed: list[ImageAnalysis] = Field(
        default_factory=list,
        description="Analysis of images found in issue. "
        "MUST be empty if no images were provided.",
    )
    image_impact: str = Field(
        default="",
        description="How images influenced the classification decision. "
        "MUST be empty if no images were provided.",
    )
```

### 2. Update Prompts (`ai/prompts.py`)

Add confidence guidance to the system prompt:

```python
# Add to the end of the prompt:
**Confidence Scoring:**
- **Root Cause Confidence**: Only provide if you identify a specific root cause (not "unclear"). This represents how confident you are in your root cause analysis (0.3 for tentative, 0.9 for certain).
- **Recommendation Confidence**: Always provide. This represents your overall confidence in the complete label recommendation - if you're recommending changing from product::troubleshoot to product::kots, how confident are you in that entire change?
```

### 3. Update Change Detection (`ai/change_detector.py`)

Simplify the change detection logic:

```python
def detect_changes(
    self,
    issue: GitHubIssue,
    ai_result: ProductLabelingResponse,
    org: str,
    repo: str,
) -> IssueUpdatePlan:
    """Detect what label changes are needed for an issue."""
    current_labels = {label.name for label in issue.labels}
    changes: list[LabelChange] = []
    
    # Use unified confidence filtering
    if ai_result.recommendation_confidence < self.min_confidence:
        # Skip all changes if overall confidence is too low
        return IssueUpdatePlan(
            org=org,
            repo=repo,
            issue_number=issue.number,
            changes=[],
            overall_confidence=ai_result.recommendation_confidence,
            needs_update=False,
            comment_summary="",
            ai_result=ai_result,
        )
    
    # Process recommended additions
    for recommendation in ai_result.recommended_labels:
        if recommendation.label.value not in current_labels:
            changes.append(
                LabelChange(
                    action="add",
                    label=recommendation.label.value,
                    reason=recommendation.reasoning,
                    confidence=ai_result.recommendation_confidence,  # Use overall confidence
                )
            )
    
    # Process recommended removals based on assessment
    for assessment in ai_result.current_labels_assessment:
        if (
            not assessment.correct
            and assessment.label in current_labels
            and self._should_remove_label(assessment, ai_result.recommended_labels)
        ):
            changes.append(
                LabelChange(
                    action="remove",
                    label=assessment.label,
                    reason=assessment.reasoning,
                    confidence=ai_result.recommendation_confidence,  # Use overall confidence
                )
            )
    
    # Rest of the method remains the same...
```

Remove the complex confidence estimation methods:
- Remove `_estimate_removal_confidence()`
- Simplify `_should_remove_label()` to not check individual confidence

### 4. Update Comment Generation (`ai/comment_generator.py`)

Simplify confidence display:

```python
def generate_update_comment(self, plan: IssueUpdatePlan) -> str:
    """Generate a comment explaining label changes."""
    # ... existing comment generation logic ...
    
    # Simplified confidence display
    lines.append(f"**Confidence Level**: {plan.overall_confidence:.0%}")
    
    # Add root cause confidence if available
    if (
        hasattr(plan, "ai_result")
        and plan.ai_result
        and hasattr(plan.ai_result, "root_cause_confidence")
        and plan.ai_result.root_cause_confidence is not None
    ):
        lines.append(f"**Root Cause Confidence**: {plan.ai_result.root_cause_confidence:.0%}")
    
    # Rest remains the same...
```

### 5. Update Dry-Run Display (`ai/comment_generator.py`)

Simplify the dry-run summary:

```python
def generate_dry_run_summary(self, plans: list[IssueUpdatePlan]) -> str:
    """Generate a summary of planned changes for dry-run mode."""
    # ... existing logic ...
    
    for plan in plans:
        lines.append(f"**Issue #{plan.issue_number} ({plan.org}/{plan.repo})**")
        lines.append(f"Recommendation confidence: {plan.overall_confidence:.2f}")
        
        # Show root cause confidence if available
        if (
            hasattr(plan, "ai_result")
            and plan.ai_result
            and hasattr(plan.ai_result, "root_cause_confidence")
            and plan.ai_result.root_cause_confidence is not None
        ):
            lines.append(f"Root cause confidence: {plan.ai_result.root_cause_confidence:.2f}")
        
        # Show changes without individual confidence scores
        additions = [c for c in plan.changes if c.action == "add"]
        removals = [c for c in plan.changes if c.action == "remove"]
        
        if additions:
            lines.append("  Add:")
            for change in additions:
                lines.append(f"    + {change.label} - {change.reason}")
        
        if removals:
            lines.append("  Remove:")
            for change in removals:
                lines.append(f"    - {change.label} - {change.reason}")
        
        # Rest remains the same...
```

**Testing Strategy:**

### Unit Tests (with mocks):
1. **Test confidence model validation**: Ensure `ProductLabelingResponse` correctly handles optional root cause confidence
2. **Test filtering logic**: Verify `ChangeDetector` uses only `recommendation_confidence` for all decisions
3. **Test comment generation**: Validate simplified confidence display in comments and dry-run output
4. **Test prompt structure**: Ensure prompts request correct confidence fields

### Integration Tests (real data):
1. **Collect fresh test data**: Since working in new branch, collect real issues first
2. **Test AI processing**: Verify AI responses include correct confidence structure
3. **Test filtering at different thresholds**: Validate filtering behavior with real confidence scores
4. **Test comment generation**: Verify comments display unified confidence correctly

**Validation Commands:**

```bash
# 1. First run quality checks to ensure code compiles
uv run black . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest

# 2. Collect fresh test data (no existing data in new branch)
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis collect --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --limit 3

# 3. Test AI processing with real issue (MUST actually run to generate results for testing)
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis process product-labeling --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --issue-number 71

# 4. Test confidence filtering with different thresholds (ALWAYS use --dry-run)
# Example: uv run gh-analysis update-labels --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --min-confidence 0.9 --dry-run
# Example: uv run gh-analysis update-labels --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --min-confidence 0.5 --dry-run
# Example: uv run gh-analysis update-labels --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --min-confidence 0.8 --dry-run

# 5. Test full processing pipeline with all collected issues
# Ask user to provide test organization and repository for validation
# Example: uv run gh-analysis process product-labeling --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO
# Example: uv run gh-analysis update-labels --org USER_PROVIDED_ORG --repo USER_PROVIDED_REPO --dry-run

# 6. Verify JSON output structure manually
# Example: cat data/results/ORG_REPO_issue_NUMBER_product-labeling.json | jq '.analysis | keys'
# Should show: ["recommendation_confidence", "root_cause_confidence", "recommended_labels", ...]
# Should NOT show individual confidence in recommended_labels
```

**Expected Validation Results:**
- **AI responses**: Should include `recommendation_confidence` (always) and `root_cause_confidence` (only when root cause identified)
- **Filtering**: All decisions should use `recommendation_confidence` only
- **Comments**: Should display unified confidence, not individual label confidence
- **Dry-run output**: Should show recommendation confidence and optionally root cause confidence
- **JSON structure**: No individual confidence scores in `recommended_labels` array

**CRITICAL TESTING RULE:**
- **NEVER run update-labels without --dry-run during testing**
- **ALWAYS use --dry-run flag** when testing update-labels to avoid modifying live GitHub issues
- **Only collect and process** are safe to run without --dry-run during testing

**Agent Notes:**
- **Key principle**: One confidence score governs all filtering decisions
- **Simplification**: Remove all individual label confidence logic
- **Clarity**: Make confidence meaning obvious to both AI and users
- **Consistency**: Use the same confidence value throughout the entire change detection process