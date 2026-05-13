"""Deterministic cross-provider job duplicate detection."""

from __future__ import annotations

from jobfinder.dedupe.matching import deduplicate_search_results
from jobfinder.dedupe.models import DedupeResult, MatchDecision, NormalizedJob

__all__ = [
    "DedupeResult",
    "MatchDecision",
    "NormalizedJob",
    "deduplicate_search_results",
]
