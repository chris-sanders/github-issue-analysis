# Task: AI Product Labeling - Phase 1 (Text Analysis)

**Status:** complete

## Overview

Implement basic AI-powered product labeling using PydanticAI with text-only analysis. Focus on establishing solid PydanticAI patterns and architecture for easy model expansion.

**Prerequisites:**
- `github-issue-collection.md` must be completed first
- Requires collected issues in `data/issues/` directory

## Implementation Plan

### Files to Create
- `github_issue_analysis/ai/processors.py` - Product labeling processor using PydanticAI
- `github_issue_analysis/ai/models.py` - Pydantic response models
- `github_issue_analysis/ai/prompts.py` - Modular prompt templates
- `github_issue_analysis/cli/process.py` - CLI process command (basic)
- `tests/test_ai/test_processors.py` - Basic test coverage

### Files to Modify
- `github_issue_analysis/cli/main.py` - Add process command import
- `github_issue_analysis/ai/__init__.py` - Package initialization

### Core Dependencies
- `pydantic-ai` - AI integration with structured outputs
- `rich` - CLI progress display
- `pydantic` - Data validation and response models

## PydanticAI Architecture (Best Practices)

### Model Configuration with Easy Expansion
```python
# github_issue_analysis/ai/models.py
from pydantic import BaseModel, Field
from typing import List, Literal
from enum import Enum

class ProductLabel(str, Enum):
    """Available product labels."""
    KOTS = "product::kots"
    TROUBLESHOOT = "product::troubleshoot"
    EMBEDDED_CLUSTER = "product::embedded-cluster"
    SDK = "product::sdk"
    DOCS = "product::docs"
    VENDOR = "product::vendor"
    DOWNLOADPORTAL = "product::downloadportal"
    COMPATIBILITY_MATRIX = "product::compatibility-matrix"
    # Special case
    UNKNOWN = "product::unknown"

class RecommendedLabel(BaseModel):
    """A recommended product label with confidence and reasoning."""
    label: ProductLabel
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(description="Explanation for this recommendation")

class LabelAssessment(BaseModel):
    """Assessment of an existing label."""
    label: str
    correct: bool = Field(description="Whether this label is correctly applied")
    reasoning: str = Field(description="Explanation of the assessment")

class ProductLabelingResponse(BaseModel):
    """Structured response for product labeling analysis."""
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence in analysis")
    recommended_labels: List[RecommendedLabel] = Field(description="Suggested product labels")
    current_labels_assessment: List[LabelAssessment] = Field(description="Assessment of existing labels")
    summary: str = Field(description="Brief summary of the issue's product classification")
    reasoning: str = Field(description="Detailed reasoning for label recommendations")

# Future: Easy to add new response types for different analysis tasks
class IssueClassificationResponse(BaseModel):
    """Future: General issue classification beyond just product labels."""
    pass
```

### Agent Configuration with Model Flexibility
```python
# github_issue_analysis/ai/processors.py
from pydantic_ai import Agent
from pydantic_ai.models import Model, KnownModelName
from typing import Optional
import os

class ProductLabelingProcessor:
    """Product labeling processor with configurable AI models."""
    
    def __init__(self, model_name: Optional[str] = None):
        """Initialize processor with configurable model.
        
        Args:
            model_name: Model identifier (e.g., 'openai:gpt-4o-mini', 'anthropic:claude-3-5-sonnet')
                       If None, uses AI_MODEL environment variable or default
        """
        self.model_name = model_name or os.getenv('AI_MODEL', 'openai:gpt-4o-mini')
        self._agent = None
    
    @property
    def agent(self) -> Agent[ProductLabelingResponse]:
        """Lazy-loaded agent for product labeling."""
        if self._agent is None:
            self._agent = Agent(
                model=self.model_name,
                result_type=ProductLabelingResponse,
                system_prompt=self._build_system_prompt(),
            )
        return self._agent
    
    def _build_system_prompt(self) -> str:
        """Build system prompt from modular components."""
        from .prompts import build_product_labeling_prompt
        return build_product_labeling_prompt()
    
    async def analyze_issue(self, issue_data: dict) -> ProductLabelingResponse:
        """Analyze issue and recommend product labels."""
        prompt = self._format_issue_prompt(issue_data)
        
        try:
            result = await self.agent.run(prompt)
            return result.data
        except Exception as e:
            # Graceful error handling - log and re-raise with context
            print(f"Failed to analyze issue: {e}")
            raise
    
    def _format_issue_prompt(self, issue_data: dict) -> str:
        """Format issue data for analysis prompt."""
        issue = issue_data["issue"]
        
        # Simple comment summary (no truncation for phase 1)
        comment_summary = ""
        if issue.get("comments"):
            recent_comments = issue["comments"][-3:]  # Last 3 comments
            summaries = []
            for comment in recent_comments:
                user = comment["user"]["login"]
                body = comment["body"][:200].replace('\n', ' ').strip()
                summaries.append(f"{user}: {body}")
            comment_summary = " | ".join(summaries)
        
        return f"""
Analyze this GitHub issue for product labeling:

**Title:** {issue["title"]}

**Body:** {issue["body"][:1500]}

**Current Labels:** {[label["name"] for label in issue["labels"]]}

**Repository:** {issue_data["org"]}/{issue_data["repo"]}

**Recent Comments:** {comment_summary or "No comments"}

Recommend the most appropriate product label(s) based on the issue content.
"""

# Future: Easy to add new processor types
class IssueClassificationProcessor:
    """Future: General issue classification processor."""
    pass
```

### Modular Prompt System
```python
# github_issue_analysis/ai/prompts.py
"""
Human-editable prompt templates for AI processing.
Edit the components below to modify AI behavior.
"""

# 1. PRODUCT DEFINITIONS - Edit to update product descriptions
PRODUCT_DEFINITIONS = {
    "kots": "Kubernetes Off-The-Shelf (KOTS): Admin console for managing Kubernetes applications. Issues involve the admin interface, application lifecycle, license validation, configuration screens, and KOTS CLI functionality. Look for: 'kotsadm', admin console problems, KOTS runtime functionality.",
    
    "troubleshoot": "Troubleshoot: Diagnostic and support bundle collection tool. Issues involve support bundle collection, analyzers, collectors, and diagnostic functionality. Look for: 'support-bundle' tool problems, 'troubleshoot' CLI issues, collector/analyzer development.",
    
    "embedded-cluster": "Embedded Cluster: Single-node Kubernetes distribution with KOTS. Issues involve cluster setup, installation, single-node deployments, cluster lifecycle management, KOTS installation/upgrade within clusters.",
    
    "sdk": "Replicated SDK: Developer tools and libraries for platform integration. Issues involve API clients, SDK usage, developer tooling, and programmatic integrations.",
    
    "docs": "Documentation: Issues with documentation, tutorials, guides, examples, or documentation website. Look for: documentation requests, unclear guides, missing examples, doc site issues.",
    
    "vendor": "Vendor Portal: Web interface for vendors to manage applications, customers, and releases. Issues involve vendor.replicated.com interface, application/customer/release management.",
    
    "downloadportal": "Download Portal: Customer-facing download interface for air-gapped installations. Issues involve download.replicated.com, customer download experience, package downloads.",
    
    "compatibility-matrix": "Compatibility Matrix: Tool for testing application compatibility across Kubernetes versions. Issues involve compatibility testing, version matrices, test automation.",
    
    # Special classification
    "unknown": "Unknown Product: Use when issue content is insufficient to determine the correct product, or when the issue is too ambiguous to classify confidently. Requires detailed reasoning explaining what information is missing."
}

# 2. CLASSIFICATION GUIDELINES - Edit to update logic
CLASSIFICATION_GUIDELINES = """
**Key Decision Principles:**

**Installation vs. Runtime:** 
- Installing KOTS via kubectl kots plugin → kots product
- Installing KOTS via kURL/embedded-cluster → embedded-cluster product  
- Using KOTS after it's installed → kots product

**Root Cause Analysis:**
- Where would the bug need to be fixed?
- Which team owns the component that's broken?
- What's the primary product experiencing the failure?

**Symptom vs. Source:**
- A tool may surface an issue without being the source
- The location where you see a problem isn't always where the problem is
- Consider the entire system interaction
"""

# 3. COMMON MISTAKES - Edit to add new pitfalls
COMMON_PITFALLS = """
**Common Pitfalls to Avoid:**
- Don't assume the product mentioned first is the problem source
- Installation/upgrade issues often belong to cluster products
- UI display problems may indicate backend data issues
- Consider the full system context, not just isolated symptoms

**Multiple Product Issues:**
- **Recommend multiple specific labels**: When issue affects multiple products, recommend each specific product label (e.g., both "product::kots" and "product::embedded-cluster")
- **Explain the relationship**: Describe how each product is involved and why multiple labels are needed
- **Prefer single product**: Only use multiple labels when issue truly requires coordination between product teams

**When to Use Special Classifications:**
- **product::unknown**: When issue lacks sufficient detail, is too vague, or you genuinely cannot determine the product from available information
- **Confidence threshold**: Use unknown for confidence < 0.6, prefer specific product for confidence ≥ 0.6
"""

def build_product_labeling_prompt() -> str:
    """Build system prompt from editable components."""
    product_list = "\n".join([
        f"- **{k}**: {v}" for k, v in PRODUCT_DEFINITIONS.items()
    ])
    
    return f"""You are an expert at analyzing GitHub issues to recommend appropriate product labels.

**Available Product Labels:**
{product_list}

**Classification Guidelines:**
{CLASSIFICATION_GUIDELINES}

{COMMON_PITFALLS}

Analyze the provided issue and respond with structured recommendations including confidence scores and detailed reasoning.
"""
```

## CLI Interface (Simplified)

### Basic Command Structure
```bash
# Process specific issue (primary use case)
uv run gh-analysis process --task product-labeling --issue 71

# Process all collected issues
uv run gh-analysis process --task product-labeling

# Use different model
uv run gh-analysis process --task product-labeling --issue 71 --model anthropic:claude-3-5-sonnet

# Environment configuration
export AI_MODEL=openai:gpt-4o-mini
uv run gh-analysis process --task product-labeling --issue 71
```

### CLI Implementation
```python
# github_issue_analysis/cli/process.py
import typer
from rich.console import Console
from pathlib import Path
import json
import asyncio
from typing import Optional

from ..ai.processors import ProductLabelingProcessor

app = typer.Typer(help="AI processing commands")
console = Console()

@app.command()
def product_labeling(
    issue: Optional[int] = typer.Option(None, help="Process specific issue number"),
    model: Optional[str] = typer.Option(None, help="AI model to use (e.g., 'openai:gpt-4o-mini')"),
    dry_run: bool = typer.Option(False, help="Show what would be processed without running AI")
):
    """Analyze GitHub issues for product labeling recommendations."""
    asyncio.run(_run_product_labeling(issue, model, dry_run))

async def _run_product_labeling(issue_num: Optional[int], model: Optional[str], dry_run: bool):
    """Run product labeling analysis."""
    
    # Find issue files to process
    data_dir = Path("data/issues")
    if not data_dir.exists():
        console.print("[red]No issues directory found. Run collect command first.[/red]")
        return
    
    issue_files = []
    if issue_num:
        # Find specific issue file
        pattern = f"*_issue_{issue_num}.json"
        matches = list(data_dir.glob(pattern))
        if not matches:
            console.print(f"[red]Issue #{issue_num} not found in collected data.[/red]")
            return
        issue_files = matches
    else:
        # Process all issues
        issue_files = list(data_dir.glob("*_issue_*.json"))
    
    if not issue_files:
        console.print("[yellow]No issue files found to process.[/yellow]")
        return
    
    console.print(f"[blue]Found {len(issue_files)} issue(s) to process[/blue]")
    
    if dry_run:
        for file_path in issue_files:
            console.print(f"Would process: {file_path.name}")
        return
    
    # Initialize processor
    processor = ProductLabelingProcessor(model_name=model)
    console.print(f"[blue]Using model: {processor.model_name}[/blue]")
    
    # Process each issue
    results_dir = Path("data/results")
    results_dir.mkdir(exist_ok=True)
    
    for file_path in issue_files:
        try:
            console.print(f"Processing {file_path.name}...")
            
            # Load issue data
            with open(file_path) as f:
                issue_data = json.load(f)
            
            # Analyze with AI
            result = await processor.analyze_issue(issue_data)
            
            # Save result
            result_file = results_dir / f"{file_path.stem}_product-labeling.json"
            result_data = {
                "issue_reference": {
                    "file_path": str(file_path),
                    "org": issue_data["org"],
                    "repo": issue_data["repo"], 
                    "issue_number": issue_data["issue"]["number"]
                },
                "processor": {
                    "name": "product-labeling",
                    "version": "1.0.0",
                    "model": processor.model_name,
                    "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
                },
                "analysis": result.model_dump()
            }
            
            with open(result_file, 'w') as f:
                json.dump(result_data, f, indent=2)
            
            console.print(f"[green]✓ Saved results to {result_file.name}[/green]")
            
        except Exception as e:
            console.print(f"[red]✗ Failed to process {file_path.name}: {e}[/red]")
            continue

if __name__ == "__main__":
    app()
```

## Test Strategy (Basic)

```python
# tests/test_ai/test_processors.py
import pytest
from unittest.mock import AsyncMock, patch
from github_issue_analysis.ai.processors import ProductLabelingProcessor
from github_issue_analysis.ai.models import ProductLabelingResponse, ProductLabel

@pytest.fixture
def sample_issue_data():
    return {
        "org": "test-org",
        "repo": "test-repo", 
        "issue": {
            "number": 1,
            "title": "KOTS admin console not loading",
            "body": "The kotsadm interface shows a blank screen after login",
            "labels": [{"name": "bug"}],
            "comments": []
        }
    }

@pytest.mark.asyncio
async def test_product_labeling_basic():
    """Test basic product labeling functionality."""
    processor = ProductLabelingProcessor(model_name="openai:gpt-4o-mini")
    
    # Mock the agent response
    mock_response = ProductLabelingResponse(
        confidence=0.9,
        recommended_labels=[{
            "label": ProductLabel.KOTS,
            "confidence": 0.9,
            "reasoning": "Issue clearly mentions kotsadm admin interface"
        }],
        current_labels_assessment=[{
            "label": "bug",
            "correct": True,
            "reasoning": "This is indeed a bug report"
        }],
        summary="KOTS admin console loading issue",
        reasoning="The issue mentions kotsadm interface problems, which is the KOTS admin console"
    )

@pytest.mark.asyncio 
async def test_multiple_product_labels():
    """Test that AI can recommend multiple specific product labels."""
    processor = ProductLabelingProcessor()
    
    # Mock response for issue affecting both KOTS and embedded-cluster
    mock_response = ProductLabelingResponse(
        confidence=0.85,
        recommended_labels=[
            {
                "label": ProductLabel.EMBEDDED_CLUSTER,
                "confidence": 0.9,
                "reasoning": "Issue involves cluster installation and k0s setup"
            },
            {
                "label": ProductLabel.KOTS,
                "confidence": 0.8,
                "reasoning": "Issue also affects KOTS installation within the cluster"
            }
        ],
        current_labels_assessment=[],
        summary="Installation issue affecting both embedded cluster setup and KOTS deployment",
        reasoning="This issue involves both cluster installation (embedded-cluster product) and KOTS deployment within that cluster (kots product). Both teams need to coordinate on the fix."
    )
    
    sample_data = {
        "org": "test", "repo": "test",
        "issue": {
            "title": "embedded-cluster install fails to deploy KOTS",
            "body": "When running embedded-cluster install, the k0s cluster starts but KOTS fails to deploy",
            "labels": [], "comments": []
        }
    }
    
    with patch.object(processor.agent, 'run', new_callable=AsyncMock) as mock_run:
        mock_run.return_value.data = mock_response
        
        result = await processor.analyze_issue(sample_data)
        
        # Verify multiple specific labels recommended
        assert len(result.recommended_labels) == 2
        assert ProductLabel.EMBEDDED_CLUSTER in [r.label for r in result.recommended_labels]
        assert ProductLabel.KOTS in [r.label for r in result.recommended_labels]
        assert "both" in result.reasoning.lower()
```

## Storage Format
Results saved as: `data/results/{org}_{repo}_issue_{number}_product-labeling.json`

## Acceptance Criteria
- [ ] PydanticAI agent with structured ProductLabelingResponse output
- [ ] CLI process command with `--issue` and `--model` options
- [ ] Model switching via environment variable or CLI flag
- [ ] Modular prompt system for easy fine-tuning
- [ ] Results storage in JSON format with metadata
- [ ] Basic test coverage with mocked AI responses
- [ ] Error handling for API failures
- [ ] **Test validation**: Issue #71 correctly processed (text-only)
- [ ] Code quality checks pass (ruff, black, mypy, pytest)

## Implementation Notes

**Focus Areas:**
1. **PydanticAI Best Practices** - Proper agent initialization, error handling, async patterns
2. **Extensible Architecture** - Easy to add new models, response types, processors
3. **Clean Separation** - Models, prompts, and processing logic in separate modules
4. **Type Safety** - Full type hints and Pydantic validation

**Phase 2 Preparation:**
- Agent architecture supports multimodal content
- Processor interface can be extended for image handling
- Response models can include image-specific fields

This establishes a solid foundation for Phase 2 image processing additions.