# Task: AI Recommendation Management and Review System - Phase 2: Application and Bulk Operations

**Status:** ready

## Description
Build upon Phase 1's foundation to add bulk operations, GitHub integration, and archival capabilities. This phase enables efficient application of reviewed recommendations to GitHub and provides enterprise-scale workflow management.

## Prerequisites
- **Phase 1 Complete**: `recommendation-management-system.md` must be fully implemented and tested
- **Label Updates**: Existing `update-labels` functionality must be working
- **GitHub API Access**: Write permissions for label updates

## New Functionality Overview (Phase 2)
When this task is complete, users will be able to:
- **Bulk approve recommendations**: Approve multiple high-confidence recommendations at once
- **Apply recommendations to GitHub**: Integrate with existing `update-labels` to apply approved recommendations
- **Archive completed work**: Move applied recommendations to archive for clean active view
- **Enterprise workflow**: Handle large-scale recommendation processing efficiently

## Files to Create (Phase 2)
```
github_issue_analysis/
├── recommendation/
│   ├── bulk_operations.py             # Bulk approve/reject operations
│   ├── github_integration.py          # Integration with update-labels system
│   └── archival.py                    # Archive management
├── cli/
│   └── recommendations_bulk.py        # Bulk operation CLI commands
└── tests/
    ├── test_recommendation/
    │   ├── test_bulk_operations.py    # Test bulk operations
    │   ├── test_github_integration.py # Test GitHub integration
    │   └── test_archival.py           # Test archival system
    └── test_cli/
        └── test_recommendations_bulk.py   # Test bulk operation CLI commands
```

## Files to Modify (Phase 2)
```
github_issue_analysis/
├── cli/
│   ├── main.py                        # Add bulk operation commands to main CLI
│   └── recommendations.py             # Add imports for Phase 2 functionality
├── recommendation/
│   ├── models.py                      # Add application tracking fields
│   └── status_tracker.py              # Add archival support
└── docs/
    └── recommendation-workflow.md     # Update with Phase 2 features
```

## Implementation Details

### 1. Bulk Operations
```python
# recommendation/bulk_operations.py
class BulkOperations:
    """Handle bulk operations on recommendations."""
    
    def bulk_approve(self, filter_criteria: RecommendationFilter, dry_run: bool = True) -> Dict[str, int]:
        """Bulk approve recommendations matching criteria."""
        
    def bulk_reject(self, filter_criteria: RecommendationFilter, reason: str, dry_run: bool = True) -> Dict[str, int]:
        """Bulk reject recommendations matching criteria."""
```

### 2. GitHub Integration
```python
# recommendation/github_integration.py
class GitHubIntegration:
    """Integration with existing update-labels system."""
    
    def apply_approved_recommendations(self, recommendations: List[RecommendationMetadata], dry_run: bool = True) -> List[ApplicationResult]:
        """Apply approved recommendations using existing update-labels functionality."""
```

### 3. CLI Commands (Phase 2)
- `uv run gh-analysis recommendations bulk-approve [filters]` - Bulk approve high-confidence recommendations
- `uv run gh-analysis recommendations apply-approved [filters]` - Apply approved recommendations to GitHub
- `uv run gh-analysis recommendations archive-applied [filters]` - Archive completed recommendations

## Acceptance Criteria (Phase 2)

### Bulk Operations
- [ ] **Bulk Approve**: Approve multiple recommendations based on confidence/product filters
- [ ] **Bulk Reject**: Reject multiple recommendations with reason
- [ ] **Safety Controls**: Dry-run mode and confirmation prompts for bulk operations

### GitHub Integration  
- [ ] **Apply Approved**: Integration with existing `update-labels` system
- [ ] **Status Tracking**: Update recommendation status after GitHub application
- [ ] **Error Handling**: Handle GitHub API failures gracefully

### Archival System
- [ ] **Archive Applied**: Move old applied recommendations to archive directory
- [ ] **Archive Query**: Ability to search archived recommendations
- [ ] **Storage Optimization**: Keep active view clean while preserving history

### Quality Assurance
- [ ] **Integration Tests**: Full end-to-end workflow testing
- [ ] **Error Recovery**: Robust handling of partial failures
- [ ] **Documentation**: Updated user guide with Phase 2 features
- [ ] **Backward Compatibility**: Phase 1 functionality remains unchanged
- [ ] **Test Coverage**: >85% coverage for all new Phase 2 code
- [ ] **GitHub API Testing**: Comprehensive mocking and integration testing for label updates

## Testing Requirements (Phase 2)

### Unit Tests Required

**tests/test_recommendation/test_bulk_operations.py:**
```python
class TestBulkOperations:
    def test_bulk_approve_with_confidence_filter(self):
        """Test bulk approve respects confidence threshold."""
        # Create 10 recommendations with confidence 0.5-1.0
        # Call bulk_approve(min_confidence=0.8, dry_run=True)
        # Verify only recommendations ≥0.8 are marked for approval
        # Verify dry_run doesn't actually change status
        
    def test_bulk_approve_actual_execution(self):
        """Test bulk approve actually updates recommendation status."""
        # Create 5 high-confidence recommendations
        # Call bulk_approve(min_confidence=0.9, dry_run=False)
        # Verify status changed to APPROVED
        # Verify reviewed_at timestamp set
        
    def test_bulk_reject_with_reason(self):
        """Test bulk reject sets rejection reason on all recommendations."""
        # Create multiple recommendations
        # Call bulk_reject(reason="Outdated analysis")
        # Verify all have status REJECTED and review_notes set
```

**tests/test_recommendation/test_github_integration.py:**
```python
class TestGitHubIntegration:
    def test_apply_approved_recommendations_dry_run(self):
        """Test GitHub integration dry run mode."""
        # Create approved recommendations
        # Mock existing update-labels functionality
        # Call apply_approved_recommendations(dry_run=True)
        # Verify no actual GitHub API calls made
        # Verify preview results returned
        
    def test_apply_approved_recommendations_success(self):
        """Test successful application to GitHub."""
        # Create approved recommendations
        # Mock successful GitHub API responses
        # Call apply_approved_recommendations(dry_run=False)
        # Verify recommendations marked as APPLIED
        # Verify applied_at timestamp set
        
    def test_apply_approved_recommendations_partial_failure(self):
        """Test handling of partial GitHub API failures."""
        # Create 5 approved recommendations
        # Mock 3 successful, 2 failed GitHub API calls
        # Call apply_approved_recommendations()
        # Verify 3 marked as APPLIED, 2 marked as FAILED
        # Verify error details captured
```

**tests/test_recommendation/test_archival.py:**
```python
class TestArchival:
    def test_archive_applied_recommendations(self):
        """Test moving applied recommendations to archive."""
        # Create recommendations with APPLIED status and old applied_at dates
        # Call archive_applied_recommendations(older_than_days=7)
        # Verify files moved from active/ to archive/ directory
        # Verify recent applications not archived
        
    def test_archive_preserves_data_integrity(self):
        """Test archived data remains complete and queryable."""
        # Archive recommendations
        # Verify archived files contain all original data
        # Test querying archived recommendations works
```

### CLI Tests Required

**tests/test_cli/test_recommendations_bulk.py:**
```python
class TestBulkCLI:
    def test_bulk_approve_command(self):
        """Test bulk approve CLI command."""
        # Create high-confidence pending recommendations
        # Run: uv run gh-analysis recommendations bulk-approve --min-confidence 0.9
        # Verify correct recommendations approved
        
    def test_apply_approved_command_with_filters(self):
        """Test apply approved command with org/repo filters."""
        # Create approved recommendations for multiple orgs
        # Run: uv run gh-analysis recommendations apply-approved --org testorg --dry-run
        # Verify only testorg recommendations included in preview
        
    def test_archive_applied_command(self):
        """Test archive command."""
        # Create old applied recommendations
        # Run: uv run gh-analysis recommendations archive-applied --older-than-days 1
        # Verify files moved to archive directory
```

### Integration Tests Required

**tests/test_integration/test_phase2_workflow.py:**
```python
class TestPhase2Workflow:
    def test_complete_bulk_workflow(self):
        """Test full bulk workflow from approval to archival."""
        # Start with pending recommendations
        # Bulk approve high-confidence ones
        # Apply to GitHub (mocked)
        # Archive applied recommendations
        # Verify clean final state
        
    def test_mixed_individual_and_bulk_workflow(self):
        """Test combination of individual review and bulk operations."""
        # Review some recommendations individually
        # Bulk approve remaining high-confidence ones
        # Apply all approved recommendations
        # Verify both paths work together correctly
```

### Mock Requirements
- **GitHub API**: All GitHub label update calls must be mocked in unit tests
- **Rich Console**: UI output should be captured and verified in tests
- **File System**: Use temporary directories for all file operations
- **Time**: Mock datetime.now() for consistent timestamp testing

## Success Metrics (Phase 2)

**Complete User Workflow:**
1. User runs AI analysis on issues
2. User runs `recommendations discover` to scan for new recommendations  
3. User runs `recommendations review-session` to review pending recommendations
4. User runs `recommendations bulk-approve --min-confidence 0.9` for high-confidence items
5. User runs `recommendations apply-approved --dry-run` to preview GitHub changes
6. User runs `recommendations apply-approved` to apply changes to GitHub  
7. User runs `recommendations archive-applied` to clean up completed work
8. Future AI analysis skips archived recommendations

**Enterprise Benefits:**
- **Scale**: Handle hundreds of recommendations efficiently
- **Automation**: Reduce manual work for high-confidence recommendations  
- **Auditability**: Complete trail from AI recommendation to GitHub application
- **Maintenance**: Keep active workspace clean while preserving history

This completes the full recommendation management system, providing both manual control and enterprise-scale automation capabilities.