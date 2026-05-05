"""Command-line entry point for scraping and exporting jobs."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

from jobscraper.scraper.export_excel import export_to_excel
from jobscraper.scraper.export_google_sheets import (
    GoogleSheetsExportError,
    build_scraper_google_sheets_service,
    export_to_google_sheets,
)
from jobscraper.scraper.filters import filter_applicant_count, filter_excluded_titles
from jobscraper.scraper.normalize import get_posted, merge_and_deduplicate
from jobscraper.scraper.search import get_searches, parse_job_sources, run_all_searches
from jobscraper.scraper.settings import (
    OUTPUT_MODE_ALIASES,
    TOKEN_ENV_VAR,
    TOKEN_PLACEHOLDER,
    ScraperSettings,
    load_scraper_settings,
    source_label,
)

LOGGER = logging.getLogger("jobscraper.scraper")


def parse_output_mode(settings: ScraperSettings) -> set[str]:
    """Resolve requested output modes from environment aliases."""
    modes = OUTPUT_MODE_ALIASES.get(settings.output_mode)
    if modes:
        return modes

    LOGGER.warning(
        "Unknown JOBSCRAPER_OUTPUT_MODE %r; using local Excel output.",
        settings.output_mode,
    )
    return {"excel"}


def format_duration(seconds: float) -> str:
    """Format elapsed seconds as a compact human-readable duration."""
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def sort_key(settings: ScraperSettings, job: dict[str, Any]) -> str:
    """Return the posted-date sort key, keeping missing dates at the bottom."""
    posted = get_posted(settings, job)
    return posted if posted != "N/A" else "0000"


def configure_logging() -> None:
    """Configure scraper logging for CLI output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Run the scraper CLI using resolved local settings."""
    configure_logging()
    try:
        settings = load_scraper_settings()
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1

    if not settings.apify_api_token or settings.apify_api_token == TOKEN_PLACEHOLDER:
        LOGGER.error(
            "Please set %s in %s or as an environment variable.",
            TOKEN_ENV_VAR,
            settings.token_file.name,
        )
        LOGGER.info("Example: %s=%s", TOKEN_ENV_VAR, TOKEN_PLACEHOLDER)
        return 1

    run_started = time.perf_counter()

    job_sources = parse_job_sources(settings)
    search_source, searches = get_searches(settings, job_sources)
    if not searches:
        LOGGER.error("No searches configured. Add keywords to configs/keywords.txt.")
        return 1

    output_modes = parse_output_mode(settings)
    google_sheets_service = None
    if "google_sheets" in output_modes:
        LOGGER.info("Checking Google Sheets access.")
        try:
            google_sheets_service = build_scraper_google_sheets_service()
            LOGGER.info("Google Sheets access is ready.")
        except GoogleSheetsExportError as exc:
            LOGGER.error("%s", exc)
            return 1

    LOGGER.info(
        "Job Scraper started at %s.",
        settings.run_started_at.strftime("%Y-%m-%d %H:%M %Z"),
    )
    LOGGER.info(
        "Sources: %s.", ", ".join(source_label(source) for source in job_sources)
    )
    if "linkedin" in job_sources:
        LOGGER.info("LinkedIn actor: %s.", settings.source_actor_ids["linkedin"])
    if "indeed" in job_sources:
        LOGGER.info("Indeed actor: %s.", settings.source_actor_ids["indeed"])
    LOGGER.info("Search source: %s.", search_source)
    LOGGER.info("Output mode: %s.", ", ".join(sorted(output_modes)))
    LOGGER.info("Timezone: %s.", settings.scraper_timezone)
    LOGGER.info("Posted timezone: %s.", settings.posted_timezone)
    LOGGER.info("Searches: %s.", len(searches))
    LOGGER.info("Search concurrency: %s.", settings.search_concurrency)
    LOGGER.info("Max applicants/job: %s.", settings.max_applicants)
    LOGGER.info("Apify child run memory: %s MB.", settings.apify_run_memory_mb)
    LOGGER.info("Apify child run timeout: %ss.", settings.apify_run_timeout_seconds)
    if settings.delay_between_requests:
        LOGGER.info(
            "Delay between starting searches: %ss.",
            settings.delay_between_requests,
        )
    if "linkedin" in job_sources:
        LOGGER.info("LinkedIn job types: %s.", ", ".join(settings.contract_types))
        LOGGER.info(
            "LinkedIn experience levels: %s.",
            ", ".join(settings.experience_levels),
        )
        LOGGER.info("LinkedIn max results/search: %s.", settings.max_results_per_search)
        LOGGER.info(
            "LinkedIn scrape company details: %s.",
            settings.scrape_company_details,
        )
    if "indeed" in job_sources:
        LOGGER.info(
            "Indeed country/location: %s / %s.",
            settings.indeed_country.upper(),
            settings.indeed_location,
        )
        LOGGER.info(
            "Indeed max results/search: %s.",
            settings.indeed_max_results_per_search,
        )
        LOGGER.info("Indeed max concurrency: %s.", settings.indeed_max_concurrency)
        LOGGER.info(
            "Indeed save unique only: %s.",
            settings.indeed_save_only_unique_items,
        )

    all_results, zero_searches, failed_sources, skipped_searches = run_all_searches(
        settings, searches
    )

    LOGGER.info("Deduplicating results.")
    unique_jobs = merge_and_deduplicate(all_results)
    LOGGER.info("%s unique job(s) after deduplication.", len(unique_jobs))

    LOGGER.info("Applying title filters.")
    unique_jobs, excluded_title_count = filter_excluded_titles(settings, unique_jobs)
    terms = ", ".join(settings.excluded_title_terms)
    LOGGER.info(
        "Removed %s job(s) containing excluded title terms: %s.",
        excluded_title_count,
        terms,
    )

    LOGGER.info("Applying applicant count filter.")
    unique_jobs, excluded_applicant_count = filter_applicant_count(
        settings, unique_jobs
    )
    LOGGER.info(
        "Removed %s job(s) with more than %s applicant(s).",
        excluded_applicant_count,
        settings.max_applicants,
    )

    LOGGER.info("Sorting results.")
    unique_jobs.sort(key=lambda job: sort_key(settings, job), reverse=True)

    outputs = []
    if "excel" in output_modes:
        LOGGER.info("Saving local Excel file %s.", settings.excel_output_file.name)
        outputs.append(
            (
                "Excel file",
                export_to_excel(settings, unique_jobs, settings.excel_output_file),
            )
        )

    if "google_sheets" in output_modes:
        LOGGER.info("Creating Google Sheet tab.")
        try:
            spreadsheet_url = export_to_google_sheets(
                settings,
                google_sheets_service,
                unique_jobs,
            )
        except GoogleSheetsExportError as exc:
            LOGGER.error("%s", exc)
            return 1
        outputs.append(("Google Sheet", spreadsheet_url))

    LOGGER.info(
        "Searched %s search URL(s); found %s unique job posting(s).",
        len(searches),
        len(unique_jobs),
    )
    LOGGER.info(
        "Total runtime: %s.",
        format_duration(time.perf_counter() - run_started),
    )
    if excluded_title_count:
        LOGGER.info("Excluded by title rule: %s.", excluded_title_count)
    if excluded_applicant_count:
        LOGGER.info("Excluded by applicant count: %s.", excluded_applicant_count)
    if zero_searches:
        LOGGER.info("Searches with 0 results: %s.", len(zero_searches))
        for label in zero_searches:
            LOGGER.info("No results: %s.", label)
    if failed_sources:
        LOGGER.warning("Failed source(s): %s.", len(failed_sources))
        for source, message in failed_sources.items():
            LOGGER.warning("%s: %s.", source_label(source), message[:180])
    if skipped_searches:
        LOGGER.warning(
            "Skipped searches after source failure: %s.",
            len(skipped_searches),
        )
    for label, destination in outputs:
        LOGGER.info("%s: %s.", label, destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
