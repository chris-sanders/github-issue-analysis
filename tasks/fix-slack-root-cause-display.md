# Task: Fix Slack Root Cause Display Priority and Field Mapping

**Status:** complete

**Implementation Note:** The fix has been implemented in branch `feature/fix-slack-root-cause` in worktree `trees/fix-slack-root-cause`. The changes are minimal and surgical as specified - only reordering topics and adding field mapping fallbacks.

**Description:**
Fix two critical issues in Slack notifications for troubleshooting results:
1. **Root Cause Priority**: Root Cause section must appear FIRST in the message (immediately after status), not after Evidence as currently implemented
2. **Field Mapping**: Fix the mismatch where troubleshooting provides `solution` field but Slack expects `recommended_solution`, causing the solution to not display at all

**Acceptance Criteria:**
- [ ] Root Cause appears as the FIRST content section after Status/Agent info in all Slack messages
- [ ] Solution from troubleshooting analysis correctly displays in Slack notifications
- [ ] Evidence section appears AFTER Root Cause (reordered from current implementation)
- [ ] All existing functionality preserved including message splitting for long content
- [ ] No regression in handling of other analysis types (product-labeling, etc.)
- [ ] Tests updated to validate new topic ordering
- [ ] Zero data loss - all content still displayed, just reordered

**Root Cause Analysis:**
1. **Topic Ordering Issue**: In `/Users/chris/src/github-issue-analysis/gh_analysis/slack/client.py:158-164`, topics are generated in this order:
   - Status → Evidence → Root Cause → Solution → Next Steps → Footer
   - Should be: Status → **Root Cause** → Evidence → Solution → Next Steps → Footer

2. **Field Mapping Issue**:
   - Troubleshooting analysis (ResolvedAnalysis model) provides field `solution`
   - Slack client expects field `recommended_solution` (lines 380, 550)
   - This causes solutions to be completely missing from Slack notifications

## Implementation Plan

### 1. Fix Topic Ordering in notify_analysis_complete
**Location**: `gh_analysis/slack/client.py` line 158-164

**Current code:**
```python
all_topics = [
    self._format_status_topic(analysis_results, agent_name),
    self._format_evidence_topic(analysis_results),
    self._format_root_cause_topic(analysis_results),
    self._format_solution_topic(analysis_results),
    self._format_next_steps_topic(analysis_results),
    self._format_footer_topic(),
]
```

**Fixed code:**
```python
all_topics = [
    self._format_status_topic(analysis_results, agent_name),
    self._format_root_cause_topic(analysis_results),  # MOVED TO SECOND POSITION
    self._format_evidence_topic(analysis_results),    # MOVED TO THIRD POSITION
    self._format_solution_topic(analysis_results),
    self._format_next_steps_topic(analysis_results),
    self._format_footer_topic(),
]
```

### 2. Fix Field Mapping for Solution
**Location**: `gh_analysis/slack/client.py` lines 550-553 (in `_format_solution_topic`)

**Current code:**
```python
def _format_solution_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Format recommended solution (splits if >2900 chars)."""
    solution = results.get("recommended_solution")
    status = results.get("status", "unknown")
```

**Fixed code:**
```python
def _format_solution_topic(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Format recommended solution (splits if >2900 chars)."""
    # Handle both field names for backward compatibility
    solution = results.get("recommended_solution") or results.get("solution")
    status = results.get("status", "unknown")
```

### 3. Update Old Format Method (for backward compatibility)
**Location**: `gh_analysis/slack/client.py` lines 380-390 (in `_format_analysis_results`)

**Current code:**
```python
# Solution (if high confidence)
solution = results.get("recommended_solution")
if solution and status == "resolved":
```

**Fixed code:**
```python
# Solution (if high confidence)
solution = results.get("recommended_solution") or results.get("solution")
if solution and status == "resolved":
```

### 4. Update Tests for New Ordering
**Location**: `tests/test_slack_splitting.py`

**Add new test:**
```python
def test_topic_ordering_root_cause_first(self):
    """Test that Root Cause appears before Evidence in topic order."""
    results = {
        "status": "resolved",
        "root_cause": "Test root cause",
        "evidence": ["Evidence 1", "Evidence 2"],
        "solution": "Test solution"
    }

    # Use internal method to verify ordering
    client = SlackClient(SlackConfig())

    # Get all topics
    all_topics = [
        client._format_status_topic(results, "test_agent"),
        client._format_root_cause_topic(results),
        client._format_evidence_topic(results),
        client._format_solution_topic(results),
        client._format_next_steps_topic(results),
        client._format_footer_topic()
    ]

    # Filter non-empty topics
    non_empty_topics = [topic for topic in all_topics if topic]

    # Find indices of root cause and evidence topics
    root_cause_index = -1
    evidence_index = -1

    for i, topic in enumerate(non_empty_topics):
        if topic and len(topic) > 0:
            text = topic[0].get("text", {}).get("text", "")
            if "Root Cause" in text:
                root_cause_index = i
            elif "Evidence" in text:
                evidence_index = i

    # Root Cause should come before Evidence
    assert root_cause_index < evidence_index, "Root Cause must appear before Evidence"
    assert root_cause_index == 1, "Root Cause should be second topic (after status)"

def test_solution_field_mapping_backward_compatibility(self):
    """Test that both 'solution' and 'recommended_solution' fields work."""
    client = SlackClient(SlackConfig())

    # Test with 'solution' field (new troubleshooting format)
    results_new = {
        "status": "resolved",
        "solution": "Fix using new format"
    }
    blocks = client._format_solution_topic(results_new)
    assert len(blocks) == 1
    assert "Fix using new format" in blocks[0]["text"]["text"]

    # Test with 'recommended_solution' field (old format)
    results_old = {
        "status": "resolved",
        "recommended_solution": "Fix using old format"
    }
    blocks = client._format_solution_topic(results_old)
    assert len(blocks) == 1
    assert "Fix using old format" in blocks[0]["text"]["text"]
```

### 5. Manual Testing Commands

```bash
# Test with a real troubleshooting issue
uv run gh-analysis collect --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE]

# Run troubleshooting with Slack notification (ask user for test issue)
uv run gh-analysis process troubleshoot \
  --org [USER-ORG] \
  --repo [USER-REPO] \
  --issue-number [USER-ISSUE] \
  --agent gpt5_mini_medium_mt \
  --slack-notifications

# Verify in Slack that:
# 1. Root Cause appears FIRST (after status)
# 2. Evidence appears AFTER Root Cause
# 3. Solution is displayed (not missing)
```

### 6. Integration Test
**Location**: Create new test in `tests/test_slack_integration.py`

```python
@patch('gh_analysis.slack.client.SlackClient.bot_client')
@patch('gh_analysis.slack.client.SlackClient.search_for_issue')
@patch('gh_analysis.slack.config.SlackConfig.is_configured', return_value=True)
def test_troubleshooting_result_formatting(self, mock_configured, mock_search, mock_bot_client):
    """Test that troubleshooting results display correctly in Slack."""
    mock_search.return_value = None
    mock_bot_client.chat_postMessage.return_value = {"ok": True, "ts": "123"}

    # Simulate troubleshooting analysis result structure
    troubleshoot_results = {
        "status": "resolved",
        "root_cause": "The service fails because the configuration file is missing",
        "evidence": [
            "Error log shows 'config.yaml not found'",
            "Service startup fails at configuration loading step"
        ],
        "solution": "Create the missing config.yaml file with required parameters",
        "validation": "Evidence clearly points to missing configuration"
    }

    client = SlackClient(SlackConfig())
    success = client.notify_analysis_complete(
        "https://github.com/test/test/issues/1",
        "Service startup failure",
        troubleshoot_results,
        "gpt5_mini_medium_mt"
    )

    assert success

    # Verify the posted message structure
    call_args = mock_bot_client.chat_postMessage.call_args[1]
    blocks = call_args["blocks"]

    # Extract text from all blocks
    block_texts = []
    for block in blocks:
        if block.get("type") == "section" and "text" in block:
            block_texts.append(block["text"]["text"])

    # Verify content ordering
    root_cause_position = -1
    evidence_position = -1
    solution_position = -1

    for i, text in enumerate(block_texts):
        if "Root Cause" in text:
            root_cause_position = i
        elif "Evidence" in text:
            evidence_position = i
        elif "Solution" in text or "Recommended Solution" in text:
            solution_position = i

    # Assertions
    assert root_cause_position != -1, "Root Cause must be present"
    assert evidence_position != -1, "Evidence must be present"
    assert solution_position != -1, "Solution must be present"
    assert root_cause_position < evidence_position, "Root Cause must appear before Evidence"

    # Verify content is preserved
    all_text = " ".join(block_texts)
    assert "configuration file is missing" in all_text
    assert "config.yaml not found" in all_text
    assert "Create the missing config.yaml file" in all_text
```

## Validation Steps

1. **Run quality checks:**
   ```bash
   uv run ruff format . && uv run ruff check --fix --unsafe-fixes && uv run mypy . && uv run pytest
   ```

2. **Test topic ordering:**
   ```bash
   uv run pytest tests/test_slack_splitting.py::TestTopicFormatting::test_topic_ordering_root_cause_first -xvs
   ```

3. **Test field mapping:**
   ```bash
   uv run pytest tests/test_slack_splitting.py::TestTopicFormatting::test_solution_field_mapping_backward_compatibility -xvs
   ```

4. **Integration test with mock data:**
   ```bash
   uv run pytest tests/test_slack_integration.py::test_troubleshooting_result_formatting -xvs
   ```

5. **Manual test with real issue** (ask user for test repo/issue):
   ```bash
   # Collect test issue
   uv run gh-analysis collect --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE]

   # Run with Slack notifications
   uv run gh-analysis process troubleshoot \
     --org [USER-ORG] --repo [USER-REPO] --issue-number [USER-ISSUE] \
     --agent gpt5_mini_medium_mt --slack-notifications
   ```

6. **Verify in Slack:**
   - Root Cause section appears FIRST (after status)
   - Evidence section appears AFTER Root Cause
   - Solution section is present and contains the recommended fix
   - All content is preserved (no truncation)

## Success Metrics

- [ ] Root Cause consistently appears before Evidence in all Slack messages
- [ ] Solution from troubleshooting analysis is visible in Slack
- [ ] No regression in existing functionality
- [ ] All tests pass
- [ ] Manual testing confirms correct display order

## Implementation Notes

1. **Minimal Changes**: Only reorder the topic array and add field mapping fallback
2. **Backward Compatibility**: Support both `solution` and `recommended_solution` fields
3. **No Breaking Changes**: Existing product-labeling and other analysis types unaffected
4. **Preserve Splitting Logic**: Message splitting for long content continues to work

## Agent Implementation Guidance

When implementing this task:

1. Make the minimal changes specified - do not refactor unrelated code
2. Test both troubleshooting and product-labeling to ensure no regression
3. Verify the changes work with both single and multi-message scenarios
4. The changes are simple but critical for user experience

The implementation should take less than 15 minutes as it's primarily:
- Reordering 2 lines in the topics array
- Adding `or results.get("solution")` in 2 locations
- Adding test coverage for the changes