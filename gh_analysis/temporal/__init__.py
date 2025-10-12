"""Temporal infrastructure for gh-analysis.

Provides CLI-managed Temporal server and worker lifecycle management.
"""

from .manager import TemporalManager

__all__ = ["TemporalManager"]
