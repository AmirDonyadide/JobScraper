"""Build common tabular rows for Excel and Google Sheets exporters."""

from __future__ import annotations

from typing import Any

from jobscraper.scraper.normalize import (
    get_applicants,
    get_apply_url,
    get_company,
    get_job_description,
    get_job_type,
    get_job_url,
    get_location,
    get_posted,
    get_source_label,
    get_title,
)
from jobscraper.scraper.settings import ScraperSettings

HEADER = [
    "Application Status",
    "App",
    "Job Title",
    "Company",
    "Location",
    "Job Type",
    "Job Description",
    "Posted",
    "Applicants",
    "Keywords Matched",
    "Job URL",
    "Apply URL",
]
"""Stable output columns written by scraper exports."""


def sheets_string(value: str) -> str:
    """Escape a string for use inside a Sheets hyperlink formula."""
    return str(value).replace('"', '""')


def hyperlink_formula(url: str, label: str) -> str:
    """Build a spreadsheet hyperlink formula or ``N/A`` for missing URLs."""
    if not url or url == "N/A":
        return "N/A"
    return f'=HYPERLINK("{sheets_string(url)}", "{sheets_string(label)}")'


def make_job_rows(
    settings: ScraperSettings, jobs: list[dict[str, Any]]
) -> list[list[Any]]:
    """Convert normalized job dictionaries into spreadsheet rows."""
    rows: list[list[Any]] = [HEADER]
    for job in jobs:
        job_url = get_job_url(settings, job)
        apply_url = get_apply_url(job)
        rows.append(
            [
                "",
                get_source_label(job),
                get_title(job),
                get_company(job),
                get_location(job),
                get_job_type(job),
                get_job_description(job),
                get_posted(settings, job),
                get_applicants(job),
                ", ".join(job.get("keywords_matched", [])),
                hyperlink_formula(job_url, "Open Job"),
                hyperlink_formula(apply_url, "Open Apply"),
            ]
        )
    return rows


def unique_name(
    existing_names: set[str], base_name: str, max_length: int | None = None
) -> str:
    """Return a unique sheet name, appending a numeric suffix when needed."""
    name = base_name[:max_length] if max_length else base_name
    if name not in existing_names:
        return name

    counter = 2
    while True:
        suffix = f" ({counter})"
        if max_length:
            candidate = f"{base_name[: max_length - len(suffix)]}{suffix}"
        else:
            candidate = f"{base_name}{suffix}"
        if candidate not in existing_names:
            return candidate
        counter += 1
