"""Pydantic models for Temporal workflows."""

from typing import Optional

from pydantic import BaseModel

from gh_analysis.ai.models import TechnicalAnalysis


class AnalysisRequest(BaseModel):
    """Request for GitHub issue analysis."""

    repo_owner: str
    repo_name: str
    issue_number: int
    agent_type: str = "gpt5_mini_medium"
    comment_limit: Optional[int] = None


class AnalysisResult(BaseModel):
    """Result from GitHub issue analysis."""

    issue_number: int
    agent_used: str
    analysis: TechnicalAnalysis
    execution_time_seconds: float
