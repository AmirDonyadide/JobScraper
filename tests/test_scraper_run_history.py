"""Tests for scraper run-history windows and cross-run deduplication."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jobscraper.env import EnvSettings
from jobscraper.scraper.run_history import (
    apply_previous_run_search_window,
    filter_jobs_to_previous_run_window,
    find_previous_run_started_at,
    job_identity_keys_from_values,
    remove_jobs_seen_in_history,
)
from jobscraper.scraper.settings import ScraperSettings


def make_settings(run_started_at: datetime) -> ScraperSettings:
    """Build minimal scraper settings for run-history tests."""
    berlin = ZoneInfo("Europe/Berlin")
    return ScraperSettings(
        env=EnvSettings({}),
        filter_config={},
        keywords=["GIS"],
        apify_api_token="token",
        google_spreadsheet_id="spreadsheet-id",
        scraper_timezone="Europe/Berlin",
        posted_timezone="Europe/Berlin",
        scraper_tz=berlin,
        posted_tz=berlin,
        run_started_at_utc=run_started_at.astimezone(UTC),
        run_started_at=run_started_at,
        run_sheet_name=run_started_at.strftime("%Y-%m-%d %H-%M-%S"),
        source_mode="linkedin",
        output_mode="google_sheets",
        excel_output_file=Path("jobs.xlsx"),
        max_results_per_search=500,
        indeed_max_results_per_search=500,
        search_concurrency=1,
        apify_run_memory_mb=512,
        apify_run_timeout_seconds=300,
        apify_client_timeout_seconds=360,
        apify_transient_error_retries=5,
        apify_retry_delay_seconds=30,
        delay_between_requests=0,
        search_window_buffer_seconds=3600,
        location="Germany",
        geo_id="101282230",
        published_at="r86400",
        experience_levels=["1", "2"],
        contract_types=["F"],
        scrape_company_details=False,
        use_incognito_mode=True,
        split_by_location=False,
        split_country="DE",
        excluded_title_terms=[],
        excluded_company_terms=[],
        max_applicants=100,
        application_status_options=["applied"],
        indeed_country="DE",
        indeed_location="Germany",
        indeed_max_concurrency=5,
        indeed_save_only_unique_items=True,
        source_actor_ids={"linkedin": "actor"},
        source_max_items={"linkedin": 500},
    )


def test_find_previous_run_started_at_uses_latest_timestamped_sheet():
    """Only timestamped run tabs should determine the previous run."""
    berlin = ZoneInfo("Europe/Berlin")
    current = datetime(2026, 5, 6, 10, 0, tzinfo=berlin)

    previous = find_previous_run_started_at(
        [
            "Notes",
            "2026-05-05 09-00-00",
            "2026-05-06 08-30-00",
            "2026-05-07 08-30-00",
        ],
        current,
        berlin,
    )

    assert previous == datetime(2026, 5, 6, 8, 30, tzinfo=berlin)


def test_apply_previous_run_search_window_adds_safety_buffer():
    """The Apify search window should cover the exact prior run plus a buffer."""
    berlin = ZoneInfo("Europe/Berlin")
    settings = make_settings(datetime(2026, 5, 6, 10, 0, tzinfo=berlin))
    previous = datetime(2026, 5, 5, 9, 0, tzinfo=berlin)

    updated, seconds = apply_previous_run_search_window(settings, previous)

    assert seconds == 25 * 60 * 60 + 3600
    assert updated.published_at == f"r{seconds}"


def test_filter_jobs_to_previous_run_window_keeps_exact_interval():
    """Posted dates are filtered after scraping to the exact run-to-run window."""
    berlin = ZoneInfo("Europe/Berlin")
    settings = make_settings(datetime(2026, 5, 6, 10, 0, tzinfo=berlin))
    previous = datetime(2026, 5, 5, 9, 0, tzinfo=berlin)
    jobs = [
        {"title": "Old", "postedAt": "2026-05-05T08:59:59+02:00"},
        {"title": "First new", "postedAt": "2026-05-05T09:00:01+02:00"},
        {"title": "At run start", "postedAt": "2026-05-06T10:00:00+02:00"},
        {"title": "Future", "postedAt": "2026-05-06T10:00:01+02:00"},
        {"title": "Unknown"},
    ]

    kept, outside_count, unknown_count = filter_jobs_to_previous_run_window(
        settings,
        jobs,
        previous,
    )

    assert [job["title"] for job in kept] == ["First new", "At run start", "Unknown"]
    assert outside_count == 2
    assert unknown_count == 1


def test_remove_jobs_seen_in_history_matches_previous_hyperlink_formula():
    """New raw jobs should be matched against URLs stored in older run tabs."""
    berlin = ZoneInfo("Europe/Berlin")
    settings = make_settings(datetime(2026, 5, 6, 10, 0, tzinfo=berlin))
    historical_keys = job_identity_keys_from_values(
        source="LinkedIn",
        title="GIS Analyst",
        company="GeoCo",
        location="Berlin",
        job_url='=HYPERLINK("https://www.linkedin.com/jobs/view/123456/?trk=x", '
        '"Open Job")',
    )
    jobs = [
        {
            "_source": "linkedin",
            "_source_label": "LinkedIn",
            "jobId": "123456",
            "title": "GIS Analyst",
            "companyName": "GeoCo",
            "location": "Berlin",
        },
        {
            "_source": "linkedin",
            "_source_label": "LinkedIn",
            "jobId": "999999",
            "title": "Remote Sensing Analyst",
            "companyName": "SpaceCo",
            "location": "Munich",
        },
    ]

    kept, duplicate_count = remove_jobs_seen_in_history(
        settings,
        jobs,
        historical_keys,
    )

    assert [job["jobId"] for job in kept] == ["999999"]
    assert duplicate_count == 1
