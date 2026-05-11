"""Indeed Apify actor payload construction."""

from __future__ import annotations

from typing import Any

from jobfinder.scraper.settings import ScraperSettings

INDEED_DOMAIN_BY_COUNTRY = {
    "us": "www.indeed.com",
    "gb": "uk.indeed.com",
    "uk": "uk.indeed.com",
    "de": "de.indeed.com",
    "at": "at.indeed.com",
    "ch": "ch.indeed.com",
    "fr": "fr.indeed.com",
    "nl": "nl.indeed.com",
    "it": "it.indeed.com",
    "es": "es.indeed.com",
    "ca": "ca.indeed.com",
    "au": "au.indeed.com",
}


def base_url(settings: ScraperSettings) -> str:
    """Return the public Indeed base URL for the configured country."""
    country_key = settings.indeed_country.lower()
    domain = INDEED_DOMAIN_BY_COUNTRY.get(country_key, f"{country_key}.indeed.com")
    return f"https://{domain}"


def build_actor_input(settings: ScraperSettings, keyword: str) -> dict[str, Any]:
    """Build the Apify actor payload for Indeed searches."""
    return {
        "country": settings.indeed_country,
        "location": settings.indeed_location,
        "maxConcurrency": settings.indeed_max_concurrency,
        "maxItems": settings.indeed_max_results_per_search,
        "position": keyword,
        "saveOnlyUniqueItems": settings.indeed_save_only_unique_items,
    }
