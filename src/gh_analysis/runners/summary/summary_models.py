"""
Domain-specific models for technical issue analysis.
"""

from pydantic import BaseModel, Field
from typing import Union, Literal


class ResolvedAnalysis(BaseModel):
    """Analysis result when root cause is identified."""

    status: Literal["resolved"] = "resolved"
    root_cause: str = Field(
        description="The fundamental underlying cause identified through systematic analysis"
    )
    evidence: list[str] = Field(
        description="Specific findings from multiple independent sources that support this conclusion"
    )
    solution: str = Field(
        description="Recommended corrective actions with specific commands and steps"
    )
    validation: str = Field(
        description="How the evidence supports the root cause and what alternatives were ruled out"
    )


class NeedsDataAnalysis(BaseModel):
    """Analysis result when insufficient data is available for definitive conclusion."""

    status: Literal["needs_data"] = "needs_data"
    current_hypothesis: str = Field(
        description="Best assessment based on available evidence with confidence level"
    )
    missing_evidence: list[str] = Field(
        description="What specific data is needed to confirm or deny potential root causes"
    )
    next_steps: list[str] = Field(
        description="Prioritized investigation actions with exact commands or file paths"
    )
    eliminated: list[str] = Field(
        description="Ruled-out possibilities and the evidence that eliminated them"
    )


# Individual field models for specialized agents
class ProductResult(BaseModel):
    """Product identification result."""

    product: list[str] = Field(
        description="List of products directly involved in the evidence, symptoms, or cause"
    )


class SymptomsResult(BaseModel):
    """Symptoms identification result."""

    symptoms: list[str] = Field(
        description="High-level, human-observable failure descriptions. These should read like a ticket report from an operator describing failure modes that they saw."
    )


class EvidenceResult(BaseModel):
    """Evidence gathering result."""

    evidence: list[str] = Field(
        description="List of technical evidence that supports the root cause and conclusion. Include specific technical details like log messages and troubleshooting steps that demonstrated failures."
    )


class CauseResult(BaseModel):
    """Root cause analysis result."""

    cause: str = Field(
        description="Root cause the primary and most fundamental item that had to be addressed to resolve the issue"
    )


class FixResult(BaseModel):
    """Fix identification result."""

    fix: list[str] = Field(description="List of steps taken to resolve the issue")


class ConfidenceResult(BaseModel):
    """Confidence scoring result."""

    confidence: float = Field(
        description="Confidence score from 0 to 1, where 0 means artifacts are unavailable/invalidated and 1 means very clear artifacts with traceable evidence",
        ge=0.0,
        le=1.0,
    )


class SummaryAnalysis(
    ProductResult,
    SymptomsResult,
    EvidenceResult,
    CauseResult,
    FixResult,
    ConfidenceResult,
):
    """Summary analysis result for support case diagnosis.

    Combines all individual agent results into a comprehensive analysis.
    """

    pass


# Discriminated union for the two analysis types
TechnicalAnalysis = Union[ResolvedAnalysis, NeedsDataAnalysis]
