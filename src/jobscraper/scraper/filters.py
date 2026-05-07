"""Final in-memory job filtering rules."""

from __future__ import annotations

from typing import Any

from jobscraper.scraper.normalize import get_applicant_count, get_company, get_title
from jobscraper.scraper.settings import ScraperSettings


def normalize_filter_text(value: str) -> str:
    """Normalize text for fuzzy filter matching."""
    return "".join(char for char in value.casefold() if char.isalnum())


def text_matches_filter_terms(value: str, terms: list[str]) -> bool:
    """Return true when a value contains any filter term."""
    value_casefolded = value.casefold()
    value_normalized = normalize_filter_text(value)

    for term in terms:
        term_casefolded = term.casefold()
        term_normalized = normalize_filter_text(term)
        if term_casefolded and term_casefolded in value_casefolded:
            return True
        if term_normalized and term_normalized in value_normalized:
            return True

    return False


def has_excluded_title(settings: ScraperSettings, job: dict[str, Any]) -> bool:
    """Return true when the job title matches an excluded term."""
    return text_matches_filter_terms(get_title(job), settings.excluded_title_terms)


def filter_excluded_titles(
    settings: ScraperSettings, jobs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Remove jobs whose titles contain configured excluded terms."""
    filtered_jobs = [job for job in jobs if not has_excluded_title(settings, job)]
    return filtered_jobs, len(jobs) - len(filtered_jobs)


def has_excluded_company(settings: ScraperSettings, job: dict[str, Any]) -> bool:
    """Return true when the company name matches an excluded term."""
    return text_matches_filter_terms(get_company(job), settings.excluded_company_terms)


def filter_excluded_companies(
    settings: ScraperSettings, jobs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Remove jobs whose company names contain configured excluded terms."""
    filtered_jobs = [job for job in jobs if not has_excluded_company(settings, job)]
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
