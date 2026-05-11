"""Google Sheets run-history helpers for scraper windows and duplicate checks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from jobfinder.google_sheets import quote_sheet_name
from jobfinder.scraper.normalize import (
    get_company,
    get_job_url,
    get_location,
    get_posted_datetime,
    get_source_label,
    get_title,
)
from jobfinder.scraper.settings import ScraperSettings

RUN_SHEET_NAME_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2})(?: \(\d+\))?$"
)
LINKEDIN_JOB_ID_RE = re.compile(r"/jobs/view/(?P<id>\d+)", re.IGNORECASE)
HYPERLINK_RE = re.compile(
    r'^=HYPERLINK\("(?P<url>(?:[^"]|"")*)"\s*[,;]\s*"',
    re.IGNORECASE,
)
HISTORICAL_IDENTITY_HEADERS = ("App", "Job Title", "Company", "Location", "Job URL")
SEEN_JOBS_SHEET_NAME = "_jobfinder_seen_jobs"
SEEN_JOBS_HEADER = ["Job Key"]


@dataclass(frozen=True)
class GoogleSpreadsheetContext:
    """Historical spreadsheet data needed before a scraper run is exported."""

    spreadsheet_id: str
    spreadsheet_url: str
    sheet_names: list[str]
    previous_run_started_at: datetime | None
    historical_job_keys: set[str]


def parse_run_sheet_started_at(sheet_name: str, timezone: ZoneInfo) -> datetime | None:
    """Parse a timestamped run sheet name into a timezone-aware datetime."""
    match = RUN_SHEET_NAME_RE.match(sheet_name.strip())
    if not match:
        return None

    try:
        parsed = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H-%M-%S")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone)


def find_previous_run_started_at(
    sheet_names: list[str],
    current_run_started_at: datetime,
    timezone: ZoneInfo,
) -> datetime | None:
    """Return the newest timestamped sheet before the current run."""
    current = current_run_started_at.astimezone(timezone)
    previous_runs = [
        started_at
        for sheet_name in sheet_names
        if (started_at := parse_run_sheet_started_at(sheet_name, timezone))
        and started_at < current
    ]
    return max(previous_runs) if previous_runs else None


def apply_previous_run_search_window(
    settings: ScraperSettings,
    previous_run_started_at: datetime | None,
) -> tuple[ScraperSettings, int | None]:
    """Use the previous run timestamp to build a broad LinkedIn posted window."""
    if previous_run_started_at is None:
        return settings, None

    elapsed_seconds = math.ceil(
        (
            settings.run_started_at
            - previous_run_started_at.astimezone(settings.scraper_tz)
        ).total_seconds()
    )
    if elapsed_seconds <= 0:
        return settings, None

    search_seconds = max(1, elapsed_seconds + settings.search_window_buffer_seconds)
    return replace(settings, published_at=f"r{search_seconds}"), search_seconds


def filter_jobs_to_previous_run_window(
    settings: ScraperSettings,
    jobs: list[dict[str, Any]],
    previous_run_started_at: datetime | None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Keep jobs posted after the previous run and no later than this run start."""
    if previous_run_started_at is None:
        return jobs, 0, 0

    window_start = previous_run_started_at.astimezone(settings.posted_tz)
    window_end = settings.run_started_at.astimezone(settings.posted_tz)
    kept: list[dict[str, Any]] = []
    outside_window_count = 0
    unknown_posted_count = 0

    for job in jobs:
        posted_at = get_posted_datetime(settings, job)
        if posted_at is None:
            kept.append(job)
            unknown_posted_count += 1
            continue

        posted_at = posted_at.astimezone(settings.posted_tz)
        if window_start < posted_at <= window_end:
            kept.append(job)
        else:
            outside_window_count += 1

    return kept, outside_window_count, unknown_posted_count


def normalize_identity_value(value: Any) -> str:
    """Normalize spreadsheet/job text for stable identity comparisons."""
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text in {"N/A", "Open Job", "Open Apply"}:
        return ""
    return text.casefold()


def hyperlink_formula_url(value: Any) -> str:
    """Extract the URL from a Google Sheets HYPERLINK formula when present."""
    if not isinstance(value, str):
        return ""
    match = HYPERLINK_RE.match(value.strip())
    if not match:
        return value.strip()
    return match.group("url").replace('""', '"').strip()


def canonical_job_url(value: Any) -> str:
    """Return a canonical URL token for duplicate comparisons."""
    url = hyperlink_formula_url(value)
    if not url or normalize_identity_value(url) == "":
        return ""

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""

    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if "linkedin.com" in host:
        match = LINKEDIN_JOB_ID_RE.search(path)
        if match:
            return f"linkedin:{match.group('id')}"
        return f"{host}{path}".casefold()

    if "indeed." in host:
        job_keys = parse_qs(parsed.query).get("jk", [])
        if job_keys and job_keys[0]:
            return f"indeed:{job_keys[0].casefold()}"

    return f"{host}{path}".casefold()


def job_id_from_url(value: Any) -> str:
    """Extract a source-native job ID from a job URL when possible."""
    canonical_url = canonical_job_url(value)
    if ":" not in canonical_url:
        return ""
    source, job_id = canonical_url.split(":", 1)
    if source in {"linkedin", "indeed"}:
        return job_id
    return ""


def job_identity_keys_from_values(
    *,
    source: Any,
    title: Any,
    company: Any,
    location: Any,
    job_url: Any,
    job_id: Any = "",
) -> set[str]:
    """Build all useful duplicate keys from normalized row/job values."""
    source_key = normalize_identity_value(source) or "unknown"
    keys: set[str] = set()

    normalized_job_id = normalize_identity_value(job_id)
    if normalized_job_id:
        keys.add(f"id|{source_key}|{normalized_job_id}")

    url_key = canonical_job_url(job_url)
    if url_key:
        keys.add(f"url|{source_key}|{url_key}")

    url_job_id = job_id_from_url(job_url)
    if url_job_id:
        keys.add(f"id|{source_key}|{url_job_id}")

    title_key = normalize_identity_value(title)
    company_key = normalize_identity_value(company)
    location_key = normalize_identity_value(location)
    if title_key and company_key and location_key:
        keys.add(f"profile|{source_key}|{title_key}|{company_key}|{location_key}")

    return keys


def job_identity_keys(settings: ScraperSettings, job: dict[str, Any]) -> set[str]:
    """Build duplicate keys for one raw scraped job."""
    job_id = job.get("jobId") or job.get("job_id") or job.get("id") or ""
    return job_identity_keys_from_values(
        source=get_source_label(job),
        title=get_title(job),
        company=get_company(job),
        location=get_location(job),
        job_url=get_job_url(settings, job),
        job_id=job_id,
    )


def remove_jobs_seen_in_history(
    settings: ScraperSettings,
    jobs: list[dict[str, Any]],
    historical_job_keys: set[str],
) -> tuple[list[dict[str, Any]], int]:
    """Drop newly scraped jobs that already appear in previous run sheets."""
    if not historical_job_keys:
        return jobs, 0

    kept: list[dict[str, Any]] = []
    duplicate_count = 0
    for job in jobs:
        if job_identity_keys(settings, job) & historical_job_keys:
            duplicate_count += 1
        else:
            kept.append(job)
    return kept, duplicate_count


def normalize_header(value: Any) -> str:
    """Normalize a spreadsheet header for duplicate-column lookup."""
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def a1_column_name(column_number: int) -> str:
    """Return a one-based spreadsheet column number as A1 letters."""
    letters = ""
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def batch_get_values(
    service: Any,
    spreadsheet_id: str,
    ranges: list[str],
    *,
    value_render_option: str = "FORMATTED_VALUE",
) -> list[dict[str, Any]]:
    """Read Google Sheets ranges, preserving response order."""
    if not ranges:
        return []

    value_ranges: list[dict[str, Any]] = []
    chunk_size = 50
    for start_idx in range(0, len(ranges), chunk_size):
        response = (
            service.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=spreadsheet_id,
                ranges=ranges[start_idx : start_idx + chunk_size],
                valueRenderOption=value_render_option,
            )
            .execute()
        )
        value_ranges.extend(response.get("valueRanges", []))
    return value_ranges


def seen_jobs_index_exists(sheet_names: list[str]) -> bool:
    """Return true when the spreadsheet has the maintained seen-jobs index tab."""
    return SEEN_JOBS_SHEET_NAME in sheet_names


def read_seen_jobs_index(service: Any, spreadsheet_id: str) -> set[str]:
    """Read canonical job keys from the maintained seen-jobs index tab."""
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"{quote_sheet_name(SEEN_JOBS_SHEET_NAME)}!A2:A",
        )
        .execute()
    )
    values = response.get("values", [])
    return {str(row[0]).strip() for row in values if row and str(row[0]).strip()}


def ensure_seen_jobs_index_sheet(
    service: Any,
    spreadsheet_id: str,
    sheet_names: list[str],
) -> None:
    """Create the hidden seen-jobs index tab when it does not exist."""
    if seen_jobs_index_exists(sheet_names):
        return

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "addSheet": {
                        "properties": {
                            "title": SEEN_JOBS_SHEET_NAME,
                            "hidden": True,
                        }
                    }
                }
            ]
        },
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(SEEN_JOBS_SHEET_NAME)}!A1",
        valueInputOption="RAW",
        body={"values": [SEEN_JOBS_HEADER]},
    ).execute()


def append_seen_job_keys(
    service: Any,
    spreadsheet_id: str,
    sheet_names: list[str],
    job_keys: set[str],
) -> None:
    """Append newly seen canonical job keys to the maintained index tab."""
    if not job_keys:
        return

    ensure_seen_jobs_index_sheet(service, spreadsheet_id, sheet_names)
    existing_keys = read_seen_jobs_index(service, spreadsheet_id)
    new_keys = sorted(job_keys - existing_keys)
    if not new_keys:
        return

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(SEEN_JOBS_SHEET_NAME)}!A:A",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [[key] for key in new_keys]},
    ).execute()


def sheet_header_indexes(headers: list[Any]) -> dict[str, int]:
    """Return duplicate-relevant header indexes for one sheet."""
    normalized_headers = {
        normalize_header(header): idx for idx, header in enumerate(headers)
    }
    return {
        header: normalized_headers[normalize_header(header)]
        for header in HISTORICAL_IDENTITY_HEADERS
        if normalize_header(header) in normalized_headers
    }


def read_historical_google_job_keys(
    service: Any,
    spreadsheet_id: str,
    sheet_names: list[str],
) -> set[str]:
    """Read previous Google Sheet tabs and return all known job identity keys."""
    header_ranges = [
        f"{quote_sheet_name(sheet_name)}!1:1" for sheet_name in sheet_names
    ]
    header_responses = batch_get_values(service, spreadsheet_id, header_ranges)
    sheet_columns: dict[str, dict[str, int]] = {}

    for sheet_name, value_range in zip(sheet_names, header_responses, strict=False):
        values = value_range.get("values", [])
        headers = values[0] if values else []
        indexes = sheet_header_indexes(headers)
        has_profile = {"App", "Job Title", "Company", "Location"} <= indexes.keys()
        has_url = {"App", "Job URL"} <= indexes.keys()
        if has_profile or has_url:
            sheet_columns[sheet_name] = indexes

    column_range_specs: list[tuple[str, str, str]] = []
    for sheet_name, indexes in sheet_columns.items():
        for header, zero_based_idx in indexes.items():
            column = a1_column_name(zero_based_idx + 1)
            range_name = f"{quote_sheet_name(sheet_name)}!{column}2:{column}"
            column_range_specs.append((sheet_name, header, range_name))

    column_responses = batch_get_values(
        service,
        spreadsheet_id,
        [range_name for _, _, range_name in column_range_specs],
        value_render_option="FORMULA",
    )
    sheet_values: dict[str, dict[str, list[Any]]] = {
        sheet_name: {} for sheet_name in sheet_columns
    }

    for (sheet_name, header, _), value_range in zip(
        column_range_specs,
        column_responses,
        strict=False,
    ):
        values = value_range.get("values", [])
        sheet_values[sheet_name][header] = [row[0] if row else "" for row in values]

    historical_keys: set[str] = set()
    for columns in sheet_values.values():
        row_count = max((len(values) for values in columns.values()), default=0)
        for row_idx in range(row_count):
            row = {
                header: values[row_idx] if row_idx < len(values) else ""
                for header, values in columns.items()
            }
            historical_keys.update(
                job_identity_keys_from_values(
                    source=row.get("App", ""),
                    title=row.get("Job Title", ""),
                    company=row.get("Company", ""),
                    location=row.get("Location", ""),
                    job_url=row.get("Job URL", ""),
                )
            )

    return historical_keys


def load_google_spreadsheet_context(
    settings: ScraperSettings,
    service: Any,
    *,
    seed_seen_jobs_index: bool = True,
) -> GoogleSpreadsheetContext:
    """Load existing run metadata and duplicate keys from Google Sheets."""
    from jobfinder.scraper.export_google_sheets import (
        GoogleSheetsExportError,
        get_google_spreadsheet,
        read_google_spreadsheet_id,
    )

    spreadsheet_id = read_google_spreadsheet_id(settings)
    if not spreadsheet_id:
        return GoogleSpreadsheetContext("", "", [], None, set())

    try:
        spreadsheet = get_google_spreadsheet(service, spreadsheet_id)
        sheet_names = [
            sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])
        ]
        previous_run_started_at = find_previous_run_started_at(
            sheet_names,
            settings.run_started_at,
            settings.scraper_tz,
        )
        if seen_jobs_index_exists(sheet_names):
            historical_job_keys = read_seen_jobs_index(service, spreadsheet_id)
        else:
            historical_job_keys = read_historical_google_job_keys(
                service,
                spreadsheet_id,
                sheet_names,
            )
            if seed_seen_jobs_index:
                append_seen_job_keys(
                    service,
                    spreadsheet_id,
                    sheet_names,
                    historical_job_keys,
                )
    except Exception as exc:
        raise GoogleSheetsExportError(
            f"Could not read run history from Google spreadsheet ID "
            f"'{spreadsheet_id}'. Details: {exc}"
        ) from exc

    return GoogleSpreadsheetContext(
        spreadsheet_id=spreadsheet_id,
        spreadsheet_url=spreadsheet["spreadsheetUrl"],
        sheet_names=sheet_names,
        previous_run_started_at=previous_run_started_at,
        historical_job_keys=historical_job_keys,
    )
