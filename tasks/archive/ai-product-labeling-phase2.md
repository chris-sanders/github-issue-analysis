# Task: AI Product Labeling - Phase 2 (Image Processing)

**Status:** complete

## Overview

Enhance the Phase 1 product labeling processor with image processing capabilities. Add support for analyzing screenshots and attachments to improve classification accuracy.

**Prerequisites:**
- `ai-product-labeling-phase1.md` must be completed first
- Phase 1 implementation working and tested
- Collected issues with downloaded attachments in `data/attachments/`

## Implementation Plan

### Files to Modify
- `github_issue_analysis/ai/processors.py` - Add image processing support
- `github_issue_analysis/ai/models.py` - Add image-related response fields
- `github_issue_analysis/cli/process.py` - Add `--include-images/--no-images` flag
- `tests/test_ai/test_processors.py` - Add image processing tests

### Files to Create
- `github_issue_analysis/ai/image_utils.py` - Image loading and processing utilities
- `tests/test_ai/test_image_processing.py` - Image-specific tests

## Image Processing Implementation

### Enhanced Models
```python
# Addition to github_issue_analysis/ai/models.py

class ImageAnalysis(BaseModel):
    """Analysis of an individual image."""
    filename: str
    source: str  # "issue_body" or "comment_{id}"
    description: str = Field(description="What the image shows relevant to product classification")
    relevance_score: float = Field(ge=0.0, le=1.0, description="How relevant this image is to classification")

class ProductLabelingResponse(BaseModel):
    """Enhanced response with image analysis."""
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence in analysis")
    recommended_labels: List[RecommendedLabel] = Field(description="Suggested product labels")
    current_labels_assessment: List[LabelAssessment] = Field(description="Assessment of existing labels")
    summary: str = Field(description="Brief summary of the issue's product classification")
    reasoning: str = Field(description="Detailed reasoning for label recommendations")
    
    # New image-related fields
    images_analyzed: List[ImageAnalysis] = Field(default_factory=list, description="Analysis of images found in issue")
    image_impact: str = Field(default="", description="How images influenced the classification decision")
```

### Image Processing Utilities
```python
# github_issue_analysis/ai/image_utils.py
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional
import mimetypes

def load_downloaded_images(issue_data: dict, include_images: bool = True) -> List[Dict[str, Any]]:
    """Load pre-downloaded images from data/attachments directory."""
    if not include_images:
        return []
    
    image_contents = []
    issue = issue_data["issue"]
    
    for attachment in issue.get("attachments", []):
        # Only process downloaded image attachments
        if not attachment.get("downloaded") or not attachment.get("local_path"):
            continue
            
        local_path = Path(attachment["local_path"])
        if not local_path.exists():
            continue
            
        # Check if it's an image file
        content_type = attachment.get("content_type") or mimetypes.guess_type(str(local_path))[0]
        if not content_type or not content_type.startswith("image/"):
            continue
            
        try:
            # Read and encode the downloaded image
            img_bytes = local_path.read_bytes()
            img_base64 = base64.b64encode(img_bytes).decode()
            
            image_contents.append({
                "type": "image_url",
                "image_url": {"url": f"data:{content_type};base64,{img_base64}"},
                "metadata": {
                    "source": attachment["source"],  # "issue_body" or "comment_{id}"
                    "filename": attachment["filename"],
                    "original_url": attachment["original_url"]
                }
            })
        except Exception as e:
            print(f"Failed to load image {local_path}: {e}")
            continue
    
    return image_contents

def describe_image_context(attachment_source: str, issue_data: dict) -> str:
    """Get contextual description of where an image appears in the issue."""
    if attachment_source == "issue_body":
        return "Image from issue description"
    
    if attachment_source.startswith("comment_"):
        try:
            comment_id = attachment_source.split("_")[1]
            comment_idx = int(comment_id)
            comments = issue_data["issue"].get("comments", [])
            if comment_idx < len(comments):
                comment = comments[comment_idx]
                user = comment["user"]["login"]
                return f"Image from comment by {user}"
        except (ValueError, IndexError, KeyError):
            pass
    
    return f"Image from {attachment_source}"
```

### Enhanced Processor
```python
# Additions to github_issue_analysis/ai/processors.py

class ProductLabelingProcessor:
    """Enhanced processor with image support."""
    
    async def analyze_issue(self, issue_data: dict, include_images: bool = True) -> ProductLabelingResponse:
        """Analyze issue with optional image processing."""
        from .image_utils import load_downloaded_images
        
        # Build text prompt
        text_prompt = self._format_issue_prompt(issue_data)
        
        # Load images if requested
        image_contents = load_downloaded_images(issue_data, include_images)
        
        # Build message content
        content = [{"type": "text", "text": text_prompt}]
        
        # Add images with context
        if image_contents:
            # Add instruction about images
            image_instruction = f"""

**IMAGES ATTACHED:** This issue contains {len(image_contents)} image(s). Analyze these images for visual clues about the product classification. Consider:
- UI screenshots showing specific product interfaces
- Error messages or logs that indicate which product is failing
- File browser views, admin consoles, or diagnostic outputs
- Any visual indicators of the affected product

When analyzing images, describe what you see and how it influences your product classification decision.
"""
            content[0]["text"] += image_instruction
            
            # Add each image
            content.extend(image_contents)
        
        try:
            result = await self.agent.run_sync(content)
            return result.data
        except Exception as e:
            print(f"Failed to analyze issue: {e}")
            raise
    
    def _enhance_system_prompt_for_images(self) -> str:
        """Enhanced system prompt when images are present."""
        base_prompt = self._build_system_prompt()
        
        image_guidance = """

**IMAGE ANALYSIS GUIDANCE:**
When images are provided, analyze them carefully for:
1. **Product Interface Screenshots**: Look for specific UI elements, branding, or interface patterns
2. **Error Messages**: Read error text that might indicate which product is failing
3. **File Paths and Logs**: Check for product-specific file paths or log entries
4. **Admin Console Views**: Identify KOTS admin interface, file browsers, or configuration screens

Include your image analysis in the reasoning field and populate the images_analyzed array with descriptions of what each image shows.
"""
        
        return base_prompt + image_guidance
```

### Enhanced CLI
```python
# Addition to github_issue_analysis/cli/process.py

@app.command()
def product_labeling(
    issue: Optional[int] = typer.Option(None, help="Process specific issue number"),
    model: Optional[str] = typer.Option(None, help="AI model to use"),
    include_images: bool = typer.Option(True, help="Include image analysis"),
    dry_run: bool = typer.Option(False, help="Show what would be processed")
):
    """Analyze GitHub issues for product labeling with optional image processing."""
    asyncio.run(_run_product_labeling(issue, model, include_images, dry_run))

async def _run_product_labeling(
    issue_num: Optional[int], 
    model: Optional[str], 
    include_images: bool,
    dry_run: bool
):
    """Enhanced processing with image support."""
    
    # ... existing file discovery logic ...
    
    console.print(f"[blue]Using model: {processor.model_name}[/blue]")
    console.print(f"[blue]Image processing: {'enabled' if include_images else 'disabled'}[/blue]")
    
    for file_path in issue_files:
        try:
            console.print(f"Processing {file_path.name}...")
            
            # Load issue data
            with open(file_path) as f:
                issue_data = json.load(f)
            
            # Check for images if enabled
            if include_images:
                attachment_count = len([
                    att for att in issue_data["issue"].get("attachments", [])
                    if att.get("downloaded") and att.get("content_type", "").startswith("image/")
                ])
                if attachment_count > 0:
                    console.print(f"  Found {attachment_count} image(s) to analyze")
            
            # Analyze with AI
            result = await processor.analyze_issue(issue_data, include_images)
            
            # Enhanced result saving with image info
            result_data = {
                "issue_reference": {
                    "file_path": str(file_path),
                    "org": issue_data["org"],
                    "repo": issue_data["repo"], 
                    "issue_number": issue_data["issue"]["number"]
                },
                "processor": {
                    "name": "product-labeling",
                    "version": "2.0.0",  # Phase 2 version
                    "model": processor.model_name,
                    "include_images": include_images,
                    "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
                },
                "analysis": result.model_dump()
            }
            
            # Save result
            result_file = results_dir / f"{file_path.stem}_product-labeling.json"
            with open(result_file, 'w') as f:
                json.dump(result_data, f, indent=2)
            
            console.print(f"[green]✓ Saved results to {result_file.name}[/green]")
            
        except Exception as e:
            console.print(f"[red]✗ Failed to process {file_path.name}: {e}[/red]")
            continue
```

## Testing Strategy

### Image Processing Tests
```python
# tests/test_ai/test_image_processing.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import base64

from github_issue_analysis.ai.processors import ProductLabelingProcessor
from github_issue_analysis.ai.models import ProductLabelingResponse, ImageAnalysis
from github_issue_analysis.ai.image_utils import load_downloaded_images

@pytest.fixture
def issue_with_images():
    return {
        "org": "test-org",
        "repo": "test-repo",
        "issue": {
            "number": 71,
            "title": "Admin console file browser issue",
            "body": "The KOTS admin console file browser shows issues with symlinks",
            "labels": [{"name": "product::troubleshoot"}],  # Incorrect label
            "comments": [
                {
                    "user": {"login": "testuser"},
                    "body": "Here's a screenshot of the problem"
                }
            ],
            "attachments": [
                {
                    "original_url": "https://github.com/user-attachments/assets/test-image",
                    "filename": "screenshot.png",
                    "local_path": "/fake/path/screenshot.png",
                    "content_type": "image/png",
                    "downloaded": True,
                    "source": "comment_0"
                }
            ]
        }
    }

@pytest.mark.asyncio
async def test_image_processing_improves_classification(issue_with_images):
    """Test that image analysis improves product classification."""
    processor = ProductLabelingProcessor()
    
    # Mock image loading
    with patch('github_issue_analysis.ai.image_utils.load_downloaded_images') as mock_load:
        mock_load.return_value = [{
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,fake_image_data"},
            "metadata": {
                "source": "comment_0",
                "filename": "screenshot.png"
            }
        }]
        
        # Mock AI response indicating image helped with classification
        mock_response = ProductLabelingResponse(
            confidence=0.95,
            recommended_labels=[{
                "label": "product::kots",
                "confidence": 0.95,
                "reasoning": "Screenshot clearly shows KOTS admin console interface with file browser"
            }],
            current_labels_assessment=[{
                "label": "product::troubleshoot",
                "correct": False,
                "reasoning": "Issue is about KOTS admin UI, not troubleshoot tool"
            }],
            summary="KOTS admin console file browser issue revealed by screenshot",
            reasoning="Image analysis shows KOTS admin interface, confirming this is a KOTS product issue",
            images_analyzed=[
                ImageAnalysis(
                    filename="screenshot.png",
                    source="comment_0",
                    description="KOTS admin console file browser showing symlink handling issue",
                    relevance_score=0.9
                )
            ],
            image_impact="Screenshot provided definitive evidence this is KOTS admin console, not troubleshoot tool"
        )
        
        with patch.object(processor.agent, 'run_sync', new_callable=AsyncMock) as mock_run:
            mock_run.return_value.data = mock_response
            
            result = await processor.analyze_issue(issue_with_images, include_images=True)
            
            # Verify image analysis improved classification
            assert result.confidence == 0.95
            assert len(result.images_analyzed) == 1
            assert result.images_analyzed[0].filename == "screenshot.png"
            assert "KOTS admin console" in result.images_analyzed[0].description
            assert result.image_impact != ""
            assert "screenshot" in result.image_impact.lower()

@pytest.mark.asyncio
async def test_multiple_products_with_images():
    """Test that images can help identify multiple specific products affected."""
    processor = ProductLabelingProcessor()
    
    # Mock response showing issue affects both products
    mock_response = ProductLabelingResponse(
        confidence=0.9,
        recommended_labels=[
            {"label": "product::embedded-cluster", "confidence": 0.85, "reasoning": "Cluster setup logs visible in screenshot"},
            {"label": "product::kots", "confidence": 0.95, "reasoning": "KOTS admin interface shown in second screenshot"}
        ],
        current_labels_assessment=[],
        summary="Issue affects both cluster installation and KOTS deployment",
        reasoning="Screenshots show both cluster setup process and KOTS admin interface problems",
        images_analyzed=[
            ImageAnalysis(filename="cluster-logs.png", source="issue_body", description="Cluster installation logs", relevance_score=0.8),
            ImageAnalysis(filename="kots-admin.png", source="comment_0", description="KOTS admin console error", relevance_score=0.9)
        ],
        image_impact="Screenshots clearly show this affects both cluster setup and KOTS admin functionality"
    )
    
    issue_data = {
        "org": "test", "repo": "test",
        "issue": {
            "title": "Cluster install and KOTS both failing",
            "body": "Both cluster and admin console have issues",
            "labels": [], "comments": [], "attachments": []
        }
    }
    
    with patch.object(processor.agent, 'run_sync', new_callable=AsyncMock) as mock_run:
        mock_run.return_value.data = mock_response
        
        result = await processor.analyze_issue(issue_data, include_images=True)
        
        # Verify multiple specific products identified
        assert len(result.recommended_labels) == 2
        labels = [r["label"] for r in result.recommended_labels]
        assert "product::embedded-cluster" in labels
        assert "product::kots" in labels

def test_load_downloaded_images_filters_correctly(issue_with_images):
    """Test that image loading correctly filters downloaded image files."""
    
    # Mock file system
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.read_bytes') as mock_read:
        
        mock_exists.return_value = True
        mock_read.return_value = b"fake_image_data"
        
        images = load_downloaded_images(issue_with_images, include_images=True)
        
        assert len(images) == 1
        assert images[0]["metadata"]["filename"] == "screenshot.png"
        assert images[0]["metadata"]["source"] == "comment_0"
        assert "data:image/png;base64," in images[0]["image_url"]["url"]

def test_load_downloaded_images_disabled():
    """Test that image loading respects include_images=False."""
    images = load_downloaded_images({}, include_images=False)
    assert images == []
```

## CLI Usage Examples

```bash
# Test with images (default)
uv run gh-analysis process --task product-labeling --issue 71

# Test without images for comparison
uv run gh-analysis process --task product-labeling --issue 71 --no-images

# Process all issues with image analysis
uv run gh-analysis process --task product-labeling --include-images

# Use higher quality model for complex image analysis
uv run gh-analysis process --task product-labeling --issue 71 --model openai:gpt-4o
```

## Expected Improvements

### Issue #71 Test Case
- **Without images**: May misclassify as `product::troubleshoot` based on text alone
- **With images**: Should correctly identify as `product::kots` by analyzing admin console screenshots
- **Image impact**: Response should explain how screenshots revealed KOTS admin interface

### Validation Criteria
- [ ] Image loading from pre-downloaded attachments works correctly
- [ ] Vision models receive properly formatted base64 image data
- [ ] Non-vision models gracefully ignore images
- [ ] CLI `--include-images/--no-images` flags work as expected
- [ ] Image analysis fields populated in response when images present
- [ ] **Test case validation**: Issue #71 classification improves with images
- [ ] **A/B testing**: Compare results with/without images for same issues
- [ ] Performance acceptable with multiple images per issue
- [ ] Error handling for missing/corrupted image files
- [ ] All Phase 1 functionality continues to work

## Implementation Strategy

1. **Start with Phase 1 complete and working**
2. **Add image utilities first** - Test image loading independently
3. **Enhance models** - Add image-related response fields
4. **Update processor** - Add image processing to existing logic
5. **Enhance CLI** - Add image flags and messaging
6. **Comprehensive testing** - Verify improvements with real issue data
7. **A/B comparison** - Document classification improvements

This phase builds incrementally on Phase 1 while adding significant value through visual analysis of screenshots and attachments.