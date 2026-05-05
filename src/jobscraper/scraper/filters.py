"""Final in-memory job filtering rules."""

from __future__ import annotations

from typing import Any

from jobscraper.scraper.normalize import get_applicant_count, get_title
from jobscraper.scraper.settings import ScraperSettings


def normalize_filter_text(value: str) -> str:
    """Normalize text for fuzzy title-filter matching."""
    return "".join(char for char in value.casefold() if char.isalnum())


def has_excluded_title(settings: ScraperSettings, job: dict[str, Any]) -> bool:
    """Return true when the job title matches an excluded term."""
    title = get_title(job)
    title_casefolded = title.casefold()
    title_normalized = normalize_filter_text(title)

    for term in settings.excluded_title_terms:
        term_casefolded = term.casefold()
        term_normalized = normalize_filter_text(term)
        if term_casefolded in title_casefolded:
            return True
        if term_normalized and term_normalized in title_normalized:
            return True

    return False


def filter_excluded_titles(
    settings: ScraperSettings, jobs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Remove jobs whose titles contain configured excluded terms."""
    filtered_jobs = [job for job in jobs if not has_excluded_title(settings, job)]
    return filtered_jobs, len(jobs) - len(filtered_jobs)


def has_too_many_applicants(settings: ScraperSettings, job: dict[str, Any]) -> bool:
    """Return true when the parsed applicant count exceeds the configured cap."""
    applicant_count = get_applicant_count(job)
    return applicant_count is not None and applicant_count > settings.max_applicants


def filter_applicant_count(
    settings: ScraperSettings, jobs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Remove jobs whose applicant count exceeds the configured cap."""
    filtered_jobs = [job for job in jobs if not has_too_many_applicants(settings, job)]
    return filtered_jobs, len(jobs) - len(filtered_jobs)
