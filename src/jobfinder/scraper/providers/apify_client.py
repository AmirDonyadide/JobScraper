"""Low-level Apify actor execution helpers."""

from __future__ import annotations

import time
from typing import Any

import requests

from jobfinder.scraper.settings import ScraperSettings

APIFY_POLL_INTERVAL_SECONDS = 15
APIFY_TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
RETRYABLE_APIFY_HTTP_STATUS_CODES = {408, 429, 500, 502, 503, 504}
MAX_APIFY_RETRY_DELAY_SECONDS = 300


class ApifyConfigurationError(RuntimeError):
    """Raised when Apify rejects the token, actor access, or paid actor setup."""


class ApifyRunError(RuntimeError):
    """Raised when an Apify actor run finishes unsuccessfully."""


class ApifyRunTimeoutError(ApifyRunError):
    """Raised when an Apify actor run exceeds the configured timeout."""


class ApifyTransientError(RuntimeError):
    """Raised for temporary Apify API errors that should be retried."""


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
