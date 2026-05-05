"""Command-line entry point for scraping and exporting jobs."""

from __future__ import annotations

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


def parse_output_mode(settings: ScraperSettings) -> set[str]:
    """Resolve requested output modes from environment aliases."""
    modes = OUTPUT_MODE_ALIASES.get(settings.output_mode)
    if modes:
        return modes

    print(f"⚠ Unknown OUTPUT_MODE '{settings.output_mode}', using local Excel output.")
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


def main() -> None:
    """Run the scraper CLI using resolved local settings."""
    settings = load_scraper_settings()
    run_started = time.perf_counter()

    if not settings.apify_api_token or settings.apify_api_token == TOKEN_PLACEHOLDER:
        print(
            f"❌ Please set {TOKEN_ENV_VAR} in {settings.token_file.name} "
            "or as an environment variable."
        )
        print(f"   Add this line to {settings.token_file.name}:")
        print(f"   {TOKEN_ENV_VAR}={TOKEN_PLACEHOLDER}")
        return

    job_sources = parse_job_sources(settings)
    search_source, searches = get_searches(settings, job_sources)
    if not searches:
        print("❌ No searches configured.")
        print("   Add keywords in the script.")
        return

    output_modes = parse_output_mode(settings)
    google_sheets_service = None
    if "google_sheets" in output_modes:
        print("Checking Google Sheets access ...")
        try:
            google_sheets_service = build_scraper_google_sheets_service()
            print("Google Sheets access OK.")
        except GoogleSheetsExportError as exc:
            print(f"\n❌ {exc}")
            return

    print("=" * 60)
    print(f"  Job Scraper — {settings.run_started_at.strftime('%Y-%m-%d %H:%M %Z')}")
    print(
        "  UTC start time: "
        f"{settings.run_started_at_utc.strftime('%Y-%m-%d %H:%M UTC')}"
    )
    print(f"  Sources: {', '.join(source_label(source) for source in job_sources)}")
    if "linkedin" in job_sources:
        print(f"  LinkedIn actor: {settings.source_actor_ids['linkedin']}")
    if "indeed" in job_sources:
        print(f"  Indeed actor: {settings.source_actor_ids['indeed']}")
    print(f"  Search source: {search_source}")
    print(f"  Output mode: {', '.join(sorted(output_modes))}")
    print(f"  Timezone: {settings.scraper_timezone}")
    print(f"  Posted timezone: {settings.posted_timezone}")
    print(f"  Searches: {len(searches)}")
    print(f"  Search concurrency: {settings.search_concurrency}")
    print(f"  Max applicants/job: {settings.max_applicants}")
    print(f"  Apify child run memory: {settings.apify_run_memory_mb} MB")
    print(f"  Apify child run timeout: {settings.apify_run_timeout_seconds}s")
    if settings.delay_between_requests:
        print(f"  Delay between starting searches: {settings.delay_between_requests}s")
    if "linkedin" in job_sources:
        print(f"  LinkedIn job types: {', '.join(settings.contract_types)}")
        print(f"  LinkedIn experience levels: {', '.join(settings.experience_levels)}")
        print(f"  LinkedIn max results/search: {settings.max_results_per_search}")
        print(
            "  LinkedIn scrape company details: " f"{settings.scrape_company_details}"
        )
    if "indeed" in job_sources:
        print(
            "  Indeed country/location: "
            f"{settings.indeed_country.upper()} / {settings.indeed_location}"
        )
        print(f"  Indeed max results/search: {settings.indeed_max_results_per_search}")
        print(f"  Indeed max concurrency: {settings.indeed_max_concurrency}")
        print("  Indeed save unique only: " f"{settings.indeed_save_only_unique_items}")
    print("=" * 60)

    all_results, zero_searches, failed_sources, skipped_searches = run_all_searches(
        settings, searches
    )

    print("\n" + "─" * 60)
    print("Deduplicating results ...")
    unique_jobs = merge_and_deduplicate(all_results)
    print(f"  → {len(unique_jobs)} unique job(s) after deduplication")

    print("Applying title filters ...")
    unique_jobs, excluded_title_count = filter_excluded_titles(settings, unique_jobs)
    terms = ", ".join(settings.excluded_title_terms)
    print(f"  → Removed {excluded_title_count} job(s) containing: {terms}")

    print("Applying applicant count filter ...")
    unique_jobs, excluded_applicant_count = filter_applicant_count(
        settings, unique_jobs
    )
    print(
        f"  → Removed {excluded_applicant_count} job(s) with more than "
        f"{settings.max_applicants} applicant(s)"
    )

    print("Sorting results ...")
    unique_jobs.sort(key=lambda job: sort_key(settings, job), reverse=True)

    outputs = []
    if "excel" in output_modes:
        print(f"Saving local Excel file '{settings.excel_output_file.name}' ...")
        outputs.append(
            (
                "Excel file",
                export_to_excel(settings, unique_jobs, settings.excel_output_file),
            )
        )

    if "google_sheets" in output_modes:
        print("Creating Google Sheet ...")
        try:
            spreadsheet_url = export_to_google_sheets(
                settings,
                google_sheets_service,
                unique_jobs,
            )
        except GoogleSheetsExportError as exc:
            print(f"\n❌ {exc}")
            return
        outputs.append(("Google Sheet", spreadsheet_url))

    print("\n" + "=" * 60)
    print(
        f"  Searched {len(searches)} search URL(s) → "
        f"Found {len(unique_jobs)} unique job postings."
    )
    print(f"  Total runtime: {format_duration(time.perf_counter() - run_started)}")
    if excluded_title_count:
        print(f"  Excluded by title rule: {excluded_title_count}")
    if excluded_applicant_count:
        print(f"  Excluded by applicant count: {excluded_applicant_count}")
    if zero_searches:
        print(f"  Searches with 0 results ({len(zero_searches)}):")
        for label in zero_searches:
            print(f"    • {label}")
    if failed_sources:
        print(f"  Failed source(s) ({len(failed_sources)}):")
        for source, message in failed_sources.items():
            print(f"    • {source_label(source)}: {message[:180]}")
    if skipped_searches:
        print(f"  Skipped searches after source failure: {len(skipped_searches)}")
    for label, destination in outputs:
        print(f"  {label}: {destination}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
