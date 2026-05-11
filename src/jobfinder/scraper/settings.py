"""Runtime settings for the Apify-powered job scraper."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jobfinder.config_files import (
    ConfigFileError,
    config_int,
    config_list,
    config_str,
    load_filter_config,
    load_keywords,
)
from jobfinder.env import EnvSettings
from jobfinder.paths import (
    DEFAULT_EXCEL_FILE,
    ENV_FILE,
    FILTERS_FILE,
    GOOGLE_SPREADSHEET_ID_FILE,
    KEYWORDS_FILE,
)

TOKEN_ENV_VAR = "APIFY_API_TOKEN"
TOKEN_PLACEHOLDER = "apify_api_XXXXXXXXXXXX"
SPREADSHEET_TITLE = "jobs"
DEFAULT_APIFY_RUN_TIMEOUT_SECONDS = 3600
DEFAULT_APIFY_CLIENT_TIMEOUT_SECONDS = 120
DEFAULT_APIFY_TRANSIENT_ERROR_RETRIES = 5
DEFAULT_APIFY_RETRY_DELAY_SECONDS = 30

LINKEDIN_ACTOR_ID = "curious_coder~linkedin-jobs-scraper"
INDEED_ACTOR_ID = "misceres~indeed-scraper"

SOURCE_ORDER = ("linkedin", "indeed")
SOURCE_DISPLAY_NAMES = {
    "linkedin": "LinkedIn",
    "indeed": "Indeed",
}
SOURCE_ALIASES = {
    "linkedin": {"linkedin"},
    "li": {"linkedin"},
    "indeed": {"indeed"},
    "both": {"linkedin", "indeed"},
    "all": {"linkedin", "indeed"},
}
OUTPUT_MODE_ALIASES = {
    "excel": {"excel"},
    "local": {"excel"},
    "xlsx": {"excel"},
    "google": {"google_sheets"},
    "drive": {"google_sheets"},
    "google_sheets": {"google_sheets"},
    "sheets": {"google_sheets"},
    "both": {"excel", "google_sheets"},
    "all": {"excel", "google_sheets"},
}

DEFAULT_EXCLUDED_COMPANY_TERMS = [
    "Zeiss",
    "Airbus",
    "Airbus Aircraft",
    "Boston Consulting Group",
    "BCG",
    "IBM",
    "Fraunhofer",
    "German Aerospace Center",
    "DLR",
    "Siemens",
    "Tesla",
]


@dataclass(frozen=True)
class ScraperSettings:
    """Resolved scraper settings from env variables and config files."""

    env: EnvSettings
    filter_config: dict[str, Any]
    keywords: list[str]
    apify_api_token: str
    google_spreadsheet_id: str
    scraper_timezone: str
    posted_timezone: str
    scraper_tz: ZoneInfo
    posted_tz: ZoneInfo
    run_started_at_utc: datetime
    run_started_at: datetime
    run_sheet_name: str
    source_mode: str
    output_mode: str
    excel_output_file: Path
    max_results_per_search: int
    indeed_max_results_per_search: int
    search_concurrency: int
    apify_run_memory_mb: int
    apify_run_timeout_seconds: int
    apify_client_timeout_seconds: int
    apify_transient_error_retries: int
    apify_retry_delay_seconds: int
    delay_between_requests: int
    search_window_buffer_seconds: int
    location: str
    geo_id: str
    published_at: str
    experience_levels: list[str]
    contract_types: list[str]
    scrape_company_details: bool
    use_incognito_mode: bool
    split_by_location: bool
    split_country: str
    excluded_title_terms: list[str]
    excluded_company_terms: list[str]
    max_applicants: int
    application_status_options: list[str]
    indeed_country: str
    indeed_location: str
    indeed_max_concurrency: int
    indeed_save_only_unique_items: bool
    source_actor_ids: dict[str, str]
    source_max_items: dict[str, int]

    @property
    def token_file(self) -> Path:
        """Return the env-file path referenced in user-facing token messages."""
        return ENV_FILE

    @property
    def spreadsheet_id_file(self) -> Path:
        """Return the file used to cache the Google spreadsheet ID."""
        return GOOGLE_SPREADSHEET_ID_FILE


def load_scraper_settings(env: EnvSettings | None = None) -> ScraperSettings:
    """Resolve and validate scraper settings."""
    env = env or EnvSettings()
    try:
        filter_config = load_filter_config(FILTERS_FILE)
        keywords = load_keywords(KEYWORDS_FILE)
    except ConfigFileError as exc:
        raise RuntimeError(f"Configuration error: {exc}") from exc

    scraper_timezone = env.get("JOBSCRAPER_TIMEZONE", "Europe/Berlin")
    posted_timezone = env.get("JOBSCRAPER_POSTED_TIMEZONE", "Europe/Berlin")
    scraper_tz = load_timezone(scraper_timezone, "JOBSCRAPER_TIMEZONE")
    posted_tz = load_timezone(posted_timezone, "JOBSCRAPER_POSTED_TIMEZONE")

    run_started_at_utc = datetime.now(UTC)
    run_started_at = run_started_at_utc.astimezone(scraper_tz)

    max_results_per_search = env.get_int("JOBSCRAPER_MAX_RESULTS_PER_SEARCH", 500)
    indeed_max_results = env.get_int(
        "INDEED_MAX_RESULTS_PER_SEARCH", max_results_per_search
    )
    apify_run_timeout_seconds = max(
        60,
        env.get_int("APIFY_RUN_TIMEOUT_SECONDS", DEFAULT_APIFY_RUN_TIMEOUT_SECONDS),
    )
    apify_client_timeout_seconds = max(
        1,
        env.get_int(
            "APIFY_CLIENT_TIMEOUT_SECONDS",
            DEFAULT_APIFY_CLIENT_TIMEOUT_SECONDS,
        ),
    )
    location = config_str(filter_config, "linkedin_search", "location", "Germany")
    config_max_applicants = config_int(
        filter_config, "final_filters", "max_applicants", 100
    )

    return ScraperSettings(
        env=env,
        filter_config=filter_config,
        keywords=keywords,
        apify_api_token=env.get(TOKEN_ENV_VAR),
        google_spreadsheet_id=env.get("GOOGLE_SPREADSHEET_ID"),
        scraper_timezone=scraper_timezone,
        posted_timezone=posted_timezone,
        scraper_tz=scraper_tz,
        posted_tz=posted_tz,
        run_started_at_utc=run_started_at_utc,
        run_started_at=run_started_at,
        run_sheet_name=run_started_at.strftime("%Y-%m-%d %H-%M-%S"),
        source_mode=env.get("JOBSCRAPER_SOURCES", "linkedin").lower(),
        output_mode=env.get("JOBSCRAPER_OUTPUT_MODE", "excel").lower(),
        excel_output_file=DEFAULT_EXCEL_FILE,
        max_results_per_search=max_results_per_search,
        indeed_max_results_per_search=indeed_max_results,
        search_concurrency=max(1, env.get_int("JOBSCRAPER_SEARCH_CONCURRENCY", 15)),
        apify_run_memory_mb=max(128, env.get_int("APIFY_RUN_MEMORY_MB", 512)),
        apify_run_timeout_seconds=apify_run_timeout_seconds,
        apify_client_timeout_seconds=apify_client_timeout_seconds,
        apify_transient_error_retries=max(
            0,
            env.get_int(
                "APIFY_TRANSIENT_ERROR_RETRIES",
                DEFAULT_APIFY_TRANSIENT_ERROR_RETRIES,
            ),
        ),
        apify_retry_delay_seconds=max(
            0,
            env.get_int("APIFY_RETRY_DELAY_SECONDS", DEFAULT_APIFY_RETRY_DELAY_SECONDS),
        ),
        delay_between_requests=max(
            0, env.get_int("JOBSCRAPER_DELAY_BETWEEN_REQUESTS", 0)
        ),
        search_window_buffer_seconds=max(
            0, env.get_int("JOBSCRAPER_SEARCH_WINDOW_BUFFER_SECONDS", 3600)
        ),
        location=location,
        geo_id=config_str(filter_config, "linkedin_search", "geo_id", "101282230"),
        published_at=config_str(
            filter_config, "linkedin_search", "published_at", "r86400"
        ),
        experience_levels=config_list(
            filter_config, "linkedin_search", "experience_levels", ["1", "2"]
        ),
        contract_types=config_list(
            filter_config, "linkedin_search", "contract_types", ["F", "P", "I"]
        ),
        scrape_company_details=env.get_bool("JOBSCRAPER_SCRAPE_COMPANY_DETAILS", False),
        use_incognito_mode=env.get_bool("JOBSCRAPER_USE_INCOGNITO_MODE", True),
        split_by_location=env.get_bool("JOBSCRAPER_SPLIT_BY_LOCATION", False),
        split_country=config_str(
            filter_config, "linkedin_search", "split_country", "DE"
        ),
        excluded_title_terms=config_list(
            filter_config,
            "final_filters",
            "excluded_title_terms",
            ["Werkstudent", "Working Student", "Senior"],
        ),
        excluded_company_terms=config_list(
            filter_config,
            "final_filters",
            "excluded_company_terms",
            DEFAULT_EXCLUDED_COMPANY_TERMS,
        ),
        max_applicants=max(
            0, env.get_int("JOBSCRAPER_MAX_APPLICANTS", config_max_applicants)
        ),
        application_status_options=config_list(
            filter_config,
            "spreadsheet",
            "application_status_options",
            ["applied", "rejected", "interview", "accepted"],
        ),
        indeed_country=env.get("INDEED_COUNTRY", "DE").upper(),
        indeed_location=env.get("INDEED_LOCATION", location),
        indeed_max_concurrency=env.get_int("INDEED_MAX_CONCURRENCY", 5),
        indeed_save_only_unique_items=env.get_bool(
            "INDEED_SAVE_ONLY_UNIQUE_ITEMS", True
        ),
        source_actor_ids={
            "linkedin": LINKEDIN_ACTOR_ID,
            "indeed": INDEED_ACTOR_ID,
        },
        source_max_items={
            "linkedin": max_results_per_search,
            "indeed": indeed_max_results,
        },
    )


def load_timezone(value: str, setting_name: str) -> ZoneInfo:
    """Load an IANA timezone or raise a user-facing runtime error."""
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(
            f"Timezone '{value}' is not available. Install tzdata or set "
            f"{setting_name} to a valid IANA timezone."
        ) from exc


def source_label(source: str) -> str:
    """Return a display label for a job source."""
    return SOURCE_DISPLAY_NAMES.get(source, source.title())
