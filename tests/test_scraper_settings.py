"""Tests for scraper runtime settings resolution."""

from __future__ import annotations

from jobfinder.env import EnvSettings
from jobfinder.scraper.settings import load_scraper_settings


def test_load_scraper_settings_clamps_provider_payload_limits(monkeypatch):
    """Invalid low numeric settings should not reach Apify actor payloads."""
    monkeypatch.delenv("JOBSCRAPER_MAX_RESULTS_PER_SEARCH", raising=False)
    monkeypatch.delenv("INDEED_MAX_RESULTS_PER_SEARCH", raising=False)
    monkeypatch.delenv("INDEED_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("STEPSTONE_MAX_RESULTS_PER_SEARCH", raising=False)
    monkeypatch.delenv("STEPSTONE_MAX_CONCURRENCY", raising=False)
    monkeypatch.setattr("jobfinder.scraper.settings.load_filter_config", lambda _: {})
    monkeypatch.setattr("jobfinder.scraper.settings.load_keywords", lambda _: ["GIS"])

    settings = load_scraper_settings(
        EnvSettings(
            {
                "APIFY_API_TOKEN": "apify_api_real_token",
                "JOBSCRAPER_MAX_RESULTS_PER_SEARCH": "0",
                "INDEED_MAX_RESULTS_PER_SEARCH": "-10",
                "INDEED_MAX_CONCURRENCY": "0",
                "STEPSTONE_MAX_RESULTS_PER_SEARCH": "-20",
                "STEPSTONE_MAX_CONCURRENCY": "0",
                "JOBSCRAPER_SEARCH_CONCURRENCY": "15",
                "JOBSCRAPER_APIFY_MEMORY_LIMIT_MB": "1024",
                "APIFY_RUN_MEMORY_MB": "512",
                "JOBSCRAPER_APIFY_BATCH_SIZE": "3",
            }
        )
    )

    assert settings.max_results_per_search == 1
    assert settings.indeed_max_results_per_search == 1
    assert settings.indeed_max_concurrency == 1
    assert settings.stepstone_max_results_per_search == 1
    assert settings.stepstone_max_concurrency == 1
    assert settings.search_concurrency == 2
    assert settings.apify_batch_size == 3
    assert settings.source_max_items == {"linkedin": 1, "indeed": 1, "stepstone": 1}


def test_load_scraper_settings_reads_manual_posted_time_window(monkeypatch):
    """Workflow/manual runs should be able to override the posted-time window."""
    monkeypatch.setattr("jobfinder.scraper.settings.load_filter_config", lambda _: {})
    monkeypatch.setattr("jobfinder.scraper.settings.load_keywords", lambda _: ["GIS"])

    settings = load_scraper_settings(
        EnvSettings(
            {
                "APIFY_API_TOKEN": "apify_api_real_token",
                "JOBSCRAPER_POSTED_TIME_WINDOW": "last_24h",
            }
        )
    )

    assert settings.posted_time_window == "last_24h"


def test_load_scraper_settings_uses_new_indeed_actor_and_limit(monkeypatch):
    """Indeed settings should target the new actor and respect its limit cap."""
    monkeypatch.setattr("jobfinder.scraper.settings.load_filter_config", lambda _: {})
    monkeypatch.setattr("jobfinder.scraper.settings.load_keywords", lambda _: ["GIS"])

    settings = load_scraper_settings(
        EnvSettings(
            {
                "APIFY_API_TOKEN": "apify_api_real_token",
                "INDEED_MAX_RESULTS_PER_SEARCH": "1500",
            }
        )
    )

    assert settings.source_actor_ids["indeed"] == "valig~indeed-jobs-scraper"
    assert settings.indeed_max_results_per_search == 1000
    assert settings.source_max_items["indeed"] == 1000


def test_load_scraper_settings_reads_stepstone_defaults_and_overrides(monkeypatch):
    """Stepstone should be a first-class source with safe defaults."""
    monkeypatch.setattr(
        "jobfinder.scraper.settings.load_filter_config",
        lambda _: {"stepstone_search": {"location": "berlin", "category": "it"}},
    )
    monkeypatch.setattr("jobfinder.scraper.settings.load_keywords", lambda _: ["GIS"])

    settings = load_scraper_settings(
        EnvSettings(
            {
                "APIFY_API_TOKEN": "apify_api_real_token",
                "STEPSTONE_START_URLS": (
                    "https://www.stepstone.de/jobs/software,"
                    "https://www.stepstone.de/work/data/in-berlin"
                ),
                "STEPSTONE_MAX_CONCURRENCY": "4",
            }
        )
    )

    assert settings.source_actor_ids["stepstone"] == (
        "memo23~stepstone-search-cheerio-ppr"
    )
    assert settings.stepstone_location == "berlin"
    assert settings.stepstone_category == "it"
    assert settings.stepstone_start_urls == [
        "https://www.stepstone.de/jobs/software",
        "https://www.stepstone.de/work/data/in-berlin",
    ]
    assert settings.stepstone_max_concurrency == 4
    assert settings.source_max_items["stepstone"] == 500
