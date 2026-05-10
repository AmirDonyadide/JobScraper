"""Search construction and Apify execution for scraper runs."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from jobscraper.scraper.settings import (
    SOURCE_ALIASES,
    SOURCE_ORDER,
    ScraperSettings,
    source_label,
)

LOGGER = logging.getLogger("jobscraper.scraper")
APIFY_POLL_INTERVAL_SECONDS = 15
APIFY_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
RETRYABLE_APIFY_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_APIFY_RETRY_DELAY_SECONDS = 300

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


class ApifyConfigurationError(RuntimeError):
    """Raised when Apify rejects the token, actor access, or paid actor setup."""


class ApifyRunError(RuntimeError):
    """Raised when an Apify actor run finishes unsuccessfully."""


class ApifyRunTimeoutError(ApifyRunError):
    """Raised when an Apify actor run exceeds the configured timeout."""


class ApifyTransientError(RuntimeError):
    """Raised for temporary Apify API errors that should be retried."""


class SearchExecutionError(RuntimeError):
    """Raised when one keyword search cannot be completed."""


@dataclass(frozen=True)
class SearchRequest:
    """A single source/keyword search to run through Apify."""

    source: str
    source_label: str
    keyword: str
    display_label: str
    actor_id: str
    payload: dict[str, Any]
    max_items: int


def apify_headers(settings: ScraperSettings) -> dict[str, str]:
    """Build authorization headers for Apify API calls."""
    return {"Authorization": f"Bearer {settings.apify_api_token}"}


def apify_error_message(response: requests.Response) -> str:
    """Extract a concise user-facing error message from an Apify response."""
    try:
        data = response.json()
    except ValueError:
        return response.text.strip()[:500] or response.reason

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if data.get("message"):
            return str(data["message"])

    return str(data)[:500]


def apify_response_data(response: requests.Response) -> Any:
    """Return the Apify response payload, unwrapping the common data envelope."""
    data = response.json()
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data


def apify_http_timeout(settings: ScraperSettings) -> int:
    """Return the HTTP timeout for individual Apify API calls."""
    return max(1, settings.apify_client_timeout_seconds)


def is_retryable_payment_error(response: requests.Response) -> bool:
    """Return true for Apify 402 memory-limit pressure that can clear later."""
    if response.status_code != 402:
        return False
    message = apify_error_message(response).lower()
    return "memory limit" in message and "currently used" in message


def is_retryable_apify_response(response: requests.Response) -> bool:
    """Return true when an Apify API response is likely temporary."""
    return (
        response.status_code in RETRYABLE_APIFY_HTTP_STATUS_CODES
        or is_retryable_payment_error(response)
    )


def check_apify_response(response: requests.Response, actor_id: str) -> None:
    """Raise a user-facing exception for Apify auth/access errors."""
    if response.status_code in (401, 403):
        message = apify_error_message(response)
        raise ApifyConfigurationError(
            "Apify rejected the request. Check that APIFY_API_TOKEN is valid, "
            f"that your account can run {actor_id}, and that billing/trial "
            f"access is active. Apify said: {message}"
        )

    if is_retryable_apify_response(response):
        message = apify_error_message(response)
        raise ApifyTransientError(
            f"Apify returned HTTP {response.status_code} for {actor_id}: {message}"
        )

    response.raise_for_status()


def indeed_base_url(settings: ScraperSettings) -> str:
    """Return the public Indeed base URL for the configured country."""
    country_key = settings.indeed_country.lower()
    domain = INDEED_DOMAIN_BY_COUNTRY.get(country_key, f"{country_key}.indeed.com")
    return f"https://{domain}"


def build_linkedin_search_url(settings: ScraperSettings, keyword: str) -> str:
    """Build a LinkedIn job-search URL for one keyword."""
    params = {
        "keywords": keyword,
        "location": settings.location,
        "geoId": settings.geo_id,
        "f_TPR": settings.published_at,
        "f_E": ",".join(settings.experience_levels),
        "f_JT": ",".join(settings.contract_types),
        "position": "1",
        "pageNum": "0",
    }
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def build_linkedin_actor_input(
    settings: ScraperSettings, search_url: str
) -> dict[str, Any]:
    """Build the Apify actor payload for LinkedIn searches."""
    payload = {
        "urls": [search_url],
        "count": settings.max_results_per_search,
        "scrapeCompany": settings.scrape_company_details,
        "useIncognitoMode": settings.use_incognito_mode,
        "splitByLocation": settings.split_by_location,
    }
    if settings.split_by_location:
        payload["splitCountry"] = settings.split_country
    return payload


def build_indeed_actor_input(settings: ScraperSettings, keyword: str) -> dict[str, Any]:
    """Build the Apify actor payload for Indeed searches."""
    return {
        "country": settings.indeed_country,
        "location": settings.indeed_location,
        "maxConcurrency": settings.indeed_max_concurrency,
        "maxItems": settings.indeed_max_results_per_search,
        "position": keyword,
        "saveOnlyUniqueItems": settings.indeed_save_only_unique_items,
    }


def build_actor_input(
    settings: ScraperSettings, source: str, keyword: str
) -> dict[str, Any]:
    """Build a source-specific Apify actor payload."""
    if source == "linkedin":
        return build_linkedin_actor_input(
            settings, build_linkedin_search_url(settings, keyword)
        )
    if source == "indeed":
        return build_indeed_actor_input(settings, keyword)
    raise ValueError(f"Unknown job source: {source}")


def build_search(settings: ScraperSettings, source: str, keyword: str) -> SearchRequest:
    """Build a typed search request for one source and keyword."""
    label = source_label(source)
    return SearchRequest(
        source=source,
        source_label=label,
        keyword=keyword,
        display_label=f"{label} / {keyword}",
        actor_id=settings.source_actor_ids[source],
        payload=build_actor_input(settings, source, keyword),
        max_items=settings.source_max_items[source],
    )


def parse_job_sources(settings: ScraperSettings) -> list[str]:
    """Resolve selected job sources from environment aliases."""
    selected = SOURCE_ALIASES.get(settings.source_mode)
    if not selected:
        LOGGER.warning(
            "Unknown JOBSCRAPER_SOURCES %r; using LinkedIn only.",
            settings.source_mode,
        )
        selected = {"linkedin"}

    return [source for source in SOURCE_ORDER if source in selected]


def get_searches(
    settings: ScraperSettings, sources: list[str]
) -> tuple[str, list[SearchRequest]]:
    """Build all source/keyword searches for a scraper run."""
    searches = [
        build_search(settings, source, keyword)
        for source in sources
        if source in settings.source_actor_ids
        for keyword in settings.keywords
    ]
    source_labels = ", ".join(source_label(source) for source in sources)
    return f"generated {source_labels} keyword URLs", searches


def annotate_jobs(
    jobs: list[dict[str, Any]], source: str, label: str
) -> list[dict[str, Any]]:
    """Attach source metadata to raw jobs returned by Apify."""
    return [dict(job, _source=source, _source_label=label) for job in jobs]


def start_actor_run(
    settings: ScraperSettings, actor_id: str, payload: dict[str, Any], max_items: int
) -> dict[str, Any]:
    """Start a configured Apify actor and return its run metadata."""
    url = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    params = {
        "timeout": settings.apify_run_timeout_seconds,
        "memory": settings.apify_run_memory_mb,
        "maxItems": max_items,
    }

    response = requests.post(
        url,
        params=params,
        headers=apify_headers(settings),
        json=payload,
        timeout=apify_http_timeout(settings),
    )
    check_apify_response(response, actor_id)

    data = apify_response_data(response)
    if not isinstance(data, dict) or not data.get("id"):
        raise ApifyRunError(f"Apify did not return a run id for actor {actor_id}.")
    return data


def get_actor_run(
    settings: ScraperSettings, actor_id: str, run_id: str
) -> dict[str, Any]:
    """Fetch the latest metadata for an Apify actor run."""
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    response = requests.get(
        url,
        headers=apify_headers(settings),
        timeout=apify_http_timeout(settings),
    )
    check_apify_response(response, actor_id)

    data = apify_response_data(response)
    if not isinstance(data, dict):
        raise ApifyRunError(f"Apify returned invalid run data for run {run_id}.")
    return data


def wait_for_actor_run(
    settings: ScraperSettings, actor_id: str, run_id: str
) -> dict[str, Any]:
    """Poll an Apify actor run until it reaches a terminal status."""
    deadline = (
        time.monotonic()
        + settings.apify_run_timeout_seconds
        + APIFY_POLL_INTERVAL_SECONDS
    )

    while True:
        run = get_actor_run(settings, actor_id, run_id)
        status = str(run.get("status") or "").upper()
        if status in APIFY_TERMINAL_STATUSES:
            if status == "SUCCEEDED":
                return run
            if status == "TIMED-OUT":
                raise ApifyRunTimeoutError(
                    f"Apify run {run_id} timed out after "
                    f"{settings.apify_run_timeout_seconds}s."
                )
            raise ApifyRunError(f"Apify run {run_id} finished with status {status}.")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ApifyRunTimeoutError(
                f"Apify run {run_id} did not finish within "
                f"{settings.apify_run_timeout_seconds}s."
            )

        time.sleep(min(APIFY_POLL_INTERVAL_SECONDS, remaining))


def fetch_dataset_items(
    settings: ScraperSettings, actor_id: str, dataset_id: str, max_items: int
) -> list[dict[str, Any]]:
    """Fetch JSON items from an Apify dataset."""
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    params = {"format": "json", "limit": max_items}
    response = requests.get(
        url,
        params=params,
        headers=apify_headers(settings),
        timeout=apify_http_timeout(settings),
    )
    check_apify_response(response, actor_id)

    data = response.json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
        return items if isinstance(items, list) else []
    return []


def run_actor(
    settings: ScraperSettings, actor_id: str, payload: dict[str, Any], max_items: int
) -> list[dict[str, Any]]:
    """Run a configured Apify actor and return its dataset items."""
    run = start_actor_run(settings, actor_id, payload, max_items)
    run_id = str(run["id"])
    completed_run = wait_for_actor_run(settings, actor_id, run_id)
    dataset_id = completed_run.get("defaultDatasetId") or run.get("defaultDatasetId")
    if not dataset_id:
        raise ApifyRunError(f"Apify run {run_id} did not include a default dataset id.")
    return fetch_dataset_items(settings, actor_id, str(dataset_id), max_items)


def retry_delay_seconds(settings: ScraperSettings, attempt: int) -> int:
    """Return the backoff delay before retrying a transient Apify issue."""
    return min(
        settings.apify_retry_delay_seconds * attempt,
        MAX_APIFY_RETRY_DELAY_SECONDS,
    )


def search_failure_message(label: str, exc: Exception) -> str:
    """Build a concise fatal error message for one failed keyword search."""
    return f"Search {label!r} could not be completed: {exc}"


def fetch_jobs_for_search(
    settings: ScraperSettings, search: SearchRequest
) -> list[dict[str, Any]]:
    """Call Apify for one search and return annotated job dictionaries."""
    label = search.display_label
    total_attempts = settings.apify_transient_error_retries + 1
    for attempt in range(1, total_attempts + 1):
        try:
            jobs = run_actor(
                settings,
                search.actor_id,
                search.payload,
                search.max_items,
            )
            return annotate_jobs(jobs, search.source, search.source_label)
        except ApifyConfigurationError:
            raise
        except ApifyRunTimeoutError as exc:
            raise SearchExecutionError(search_failure_message(label, exc)) from exc
        except requests.exceptions.HTTPError as exc:
            response = exc.response
            details = (
                f" {apify_error_message(response)}" if response is not None else ""
            )
            raise SearchExecutionError(
                f"Search {label!r} could not be completed: {exc}.{details}"
            ) from exc
        except (
            ApifyTransientError,
            ApifyRunError,
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
        ) as exc:
            if attempt >= total_attempts:
                raise SearchExecutionError(search_failure_message(label, exc)) from exc

            delay = retry_delay_seconds(settings, attempt)
            LOGGER.warning(
                "Temporary Apify issue for search %r on attempt %s/%s: %s. "
                "Retrying in %ss.",
                label,
                attempt,
                total_attempts,
                exc,
                delay,
            )
            if delay:
                time.sleep(delay)
        except Exception as exc:
            raise SearchExecutionError(search_failure_message(label, exc)) from exc

    raise SearchExecutionError(f"Search {label!r} ended without a result.")


def run_all_searches(
    settings: ScraperSettings,
    searches: list[SearchRequest],
) -> tuple[
    list[tuple[str, list[dict[str, Any]]]], list[str], dict[str, str], list[str]
]:
    """Run searches concurrently while preserving the original result order."""
    all_results: list[tuple[int, str, list[dict[str, Any]]]] = []
    zero_searches: list[str] = []
    failed_sources: dict[str, str] = {}
    skipped_searches: list[str] = []
    max_workers = min(settings.search_concurrency, len(searches))
    submitted_count = 0

    LOGGER.info("Running up to %s search(es) in parallel.", max_workers)

    def submit_next(
        executor: ThreadPoolExecutor,
        search_iter: Any,
        in_flight: dict[Any, tuple[int, SearchRequest]],
    ) -> None:
        """Submit searches until the concurrency window is full."""
        nonlocal submitted_count
        while len(in_flight) < max_workers:
            try:
                idx, search = next(search_iter)
            except StopIteration:
                return

            label = search.display_label
            if search.source in failed_sources:
                LOGGER.info(
                    "[%02d/%s] Skipping %s because %s failed earlier in this run.",
                    idx,
                    len(searches),
                    label,
                    search.source_label,
                )
                skipped_searches.append(label)
                continue

            if settings.delay_between_requests and submitted_count:
                time.sleep(settings.delay_between_requests)

            LOGGER.info(
                "[%02d/%s] Searching %s with Apify actor %s.",
                idx,
                len(searches),
                label,
                search.actor_id,
            )
            future = executor.submit(fetch_jobs_for_search, settings, search)
            in_flight[future] = (idx, search)
            submitted_count += 1

    search_iter = iter(enumerate(searches, start=1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        in_flight: dict[Any, tuple[int, SearchRequest]] = {}
        submit_next(executor, search_iter, in_flight)

        while in_flight:
            for future in as_completed(tuple(in_flight)):
                idx, search = in_flight.pop(future)
                label = search.display_label

                try:
                    jobs = future.result()
                except ApifyConfigurationError as exc:
                    if search.source not in failed_sources:
                        LOGGER.error("%s", exc)
                        LOGGER.warning(
                            "Continuing with other sources. Remaining %s searches "
                            "will be skipped.",
                            search.source_label,
                        )
                        failed_sources[search.source] = str(exc)
                    skipped_searches.append(label)
                except SearchExecutionError as exc:
                    LOGGER.error("%s", exc)
                    raise
                else:
                    all_results.append((idx, search.keyword, jobs))
                    if jobs:
                        LOGGER.info("Completed %s: %s job(s) found.", label, len(jobs))
                    else:
                        LOGGER.info("Completed %s: 0 results.", label)
                        zero_searches.append(label)

                submit_next(executor, search_iter, in_flight)
                break

    ordered_results = [
        (keyword, jobs)
        for _, keyword, jobs in sorted(all_results, key=lambda item: item[0])
    ]
    return ordered_results, zero_searches, failed_sources, skipped_searches
