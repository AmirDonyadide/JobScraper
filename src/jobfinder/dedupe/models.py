"""Data structures for deterministic job deduplication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SalaryRange:
    """Comparable salary range extracted without AI."""

    minimum: float | None = None
    maximum: float | None = None
    currency: str = ""
    period: str = ""
    raw: str = ""

    @property
    def midpoint(self) -> float | None:
        """Return the midpoint for proximity comparisons."""
        if self.minimum is None and self.maximum is None:
            return None
        if self.minimum is None:
            return self.maximum
        if self.maximum is None:
            return self.minimum
        return (self.minimum + self.maximum) / 2


@dataclass(frozen=True)
class Provenance:
    """One source-specific view of a canonical real-world job."""

    source: str
    label: str
    job_id: str = ""
    job_url: str = ""
    job_url_key: str = ""
    apply_url: str = ""
    apply_url_key: str = ""
    company_url: str = ""
    company_url_key: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    keywords: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a compact serializable provenance record."""
        return {
            key: value
            for key, value in {
                "source": self.source,
                "label": self.label,
                "job_id": self.job_id,
                "job_url": self.job_url,
                "job_url_key": self.job_url_key,
                "apply_url": self.apply_url,
                "apply_url_key": self.apply_url_key,
                "company_url": self.company_url,
                "company_url_key": self.company_url_key,
                "title": self.title,
                "company": self.company,
                "location": self.location,
                "keywords": list(self.keywords),
            }.items()
            if value not in ("", [], ())
        }


@dataclass(frozen=True)
class NormalizedJob:
    """Cached deterministic features for one scraped job."""

    index: int
    raw: dict[str, Any]
    keywords: tuple[str, ...]
    source: str
    source_label: str
    job_id: str
    title: str
    company: str
    location: str
    job_type: str
    description: str
    posted_at: datetime | None
    salary: SalaryRange
    remote_mode: str
    normalized_title: str
    normalized_company: str
    normalized_location: str
    title_tokens: frozenset[str]
    company_tokens: frozenset[str]
    location_tokens: frozenset[str]
    job_url: str
    job_url_key: str
    apply_url: str
    apply_url_key: str
    company_url: str
    company_url_key: str
    strong_keys: frozenset[str]
    blocking_keys: frozenset[str]
    provenance: Provenance

    @property
    def profile_key(self) -> str:
        """Return the source-agnostic exact normalized profile key."""
        if (
            not self.normalized_company
            or not self.normalized_title
            or not self.normalized_location
        ):
            return ""
        return (
            "profile|any|"
            f"{self.normalized_company}|{self.normalized_title}|"
            f"{self.normalized_location}"
        )


@dataclass(frozen=True)
class MatchDecision:
    """Explain why two jobs did or did not merge."""

    left_index: int
    right_index: int
    matched: bool
    confidence: float
    stage: str
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class DedupeResult:
    """Deduplication output plus optional explainability data."""

    jobs: list[dict[str, Any]]
    decisions: list[MatchDecision] = field(default_factory=list)
    input_count: int = 0
    output_count: int = 0
