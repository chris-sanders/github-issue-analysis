# Analysis Type Field Mappings

This document maps the fields from different analysis types to how they're displayed in Slack notifications.

## ProductLabelingResponse Fields
- `root_cause_analysis` → NOT displayed in Slack (only troubleshooting root_cause is shown)
- `root_cause_confidence` → NOT displayed
- `recommendation_confidence` → NOT displayed
- `recommended_labels` → NOT displayed
- `current_labels_assessment` → NOT displayed
- `summary` → NOT displayed
- `reasoning` → NOT displayed
- `images_analyzed` → NOT displayed
- `image_impact` → NOT displayed

**Note**: The current Slack implementation seems to be designed for troubleshooting results, not product labeling!

## ResolvedAnalysis Fields (Troubleshooting - Resolved)
- `status: "resolved"` → Displayed with ✅ emoji
- `root_cause` → Displayed in "Root Cause" section (NOW FIRST after fix)
- `evidence` → Displayed in "Key Evidence" section (NOW SECOND after fix)
- `solution` → Displayed in "Recommended Solution" section (NOW WORKING after fix)
- `validation` → NOT displayed in Slack

## NeedsDataAnalysis Fields (Troubleshooting - Needs Data)
- `status: "needs_data"` → Displayed with 📋 emoji
- `current_hypothesis` → NOT displayed in Slack
- `missing_evidence` → NOT displayed in Slack
- `next_steps` → Displayed in "Next Steps" section
- `eliminated` → NOT displayed in Slack

## Issues Found

### Critical Issues (Fixed in Current PR)
1. ✅ **FIXED**: Root Cause appeared after Evidence instead of first
2. ✅ **FIXED**: Solution field not displayed (expected `recommended_solution` but got `solution`)

### Additional Issues Not Yet Fixed
1. **ProductLabelingResponse not supported**: The Slack client doesn't display ANY fields from product labeling analysis
2. **Missing NeedsDataAnalysis fields**: `current_hypothesis`, `missing_evidence`, and `eliminated` are not displayed
3. **Missing validation field**: The `validation` field from ResolvedAnalysis is not shown

## Recommended Additional Fixes

### 1. Support ProductLabelingResponse
The Slack client should check if the results contain product labeling fields and display them appropriately:
```python
# Check if this is a product labeling result
if "recommended_labels" in results:
    # Format product labeling specific fields
    self._format_product_labels_topic(results)
```

### 2. Display All Troubleshooting Fields
For NeedsDataAnalysis, display:
- `current_hypothesis` as "Current Assessment"
- `missing_evidence` as "Data Needed"
- `eliminated` as "Ruled Out"

For ResolvedAnalysis, display:
- `validation` as "Validation" or include it with the root cause

### 3. Add Type Detection
Add a method to detect which analysis type the results are from:
```python
def _detect_analysis_type(self, results: Dict[str, Any]) -> str:
    if "recommended_labels" in results:
        return "product_labeling"
    elif "root_cause" in results or "solution" in results:
        return "troubleshooting_resolved"
    elif "current_hypothesis" in results or "missing_evidence" in results:
        return "troubleshooting_needs_data"
    else:
        return "unknown"
```