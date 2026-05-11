"""Tests for scraper runtime settings resolution."""

from __future__ import annotations

from jobfinder.env import EnvSettings
from jobfinder.scraper.settings import load_scraper_settings


def test_load_scraper_settings_clamps_provider_payload_limits(monkeypatch):
    """Invalid low numeric settings should not reach Apify actor payloads."""
    monkeypatch.delenv("JOBSCRAPER_MAX_RESULTS_PER_SEARCH", raising=False)
    monkeypatch.delenv("INDEED_MAX_RESULTS_PER_SEARCH", raising=False)
    monkeypatch.delenv("INDEED_MAX_CONCURRENCY", raising=False)
    monkeypatch.setattr("jobfinder.scraper.settings.load_filter_config", lambda _: {})
    monkeypatch.setattr("jobfinder.scraper.settings.load_keywords", lambda _: ["GIS"])

    settings = load_scraper_settings(
        EnvSettings(
            {
                "APIFY_API_TOKEN": "apify_api_real_token",
                "JOBSCRAPER_MAX_RESULTS_PER_SEARCH": "0",
                "INDEED_MAX_RESULTS_PER_SEARCH": "-10",
                "INDEED_MAX_CONCURRENCY": "0",
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
    assert settings.search_concurrency == 2
    assert settings.apify_batch_size == 3
    assert settings.source_max_items == {"linkedin": 1, "indeed": 1}
