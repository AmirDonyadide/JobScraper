"""Tests for Apify search execution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import requests

from jobfinder.scraper.search import (
    ApifyRunTimeoutError,
    SearchExecutionError,
    SearchRequest,
    apify_http_timeout,
    fetch_jobs_for_search,
    run_actor,
    run_all_searches,
)


class FakeResponse:
    """Small response double for Apify API tests."""

    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = ""
        self.reason = "OK"

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


def make_settings() -> SimpleNamespace:
    """Build the settings attributes used by Apify search execution."""
    return SimpleNamespace(
        apify_api_token="apify_api_real_token",
        apify_run_timeout_seconds=3600,
        apify_run_memory_mb=512,
        apify_client_timeout_seconds=120,
        apify_transient_error_retries=5,
        apify_retry_delay_seconds=0,
        apify_batch_size=1,
        search_concurrency=2,
        delay_between_requests=0,
        max_results_per_search=500,
        scrape_company_details=False,
        use_incognito_mode=True,
        split_by_location=False,
        split_country="DE",
    )


def test_run_actor_uses_async_api_and_fetches_dataset(monkeypatch):
    """Long keyword searches should not use Apify's 300-second sync endpoint."""
    settings = make_settings()
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("POST", url, kwargs.get("params")))
        return FakeResponse({"data": {"id": "run-1", "defaultDatasetId": "dataset-1"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        calls.append(("GET", url, kwargs.get("params")))
        if "/actor-runs/" in url:
            return FakeResponse(
                {
                    "data": {
                        "id": "run-1",
                        "status": "SUCCEEDED",
                        "defaultDatasetId": "dataset-1",
                    }
                }
            )
        return FakeResponse([{"title": "GIS Analyst"}])

    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.post", fake_post
    )
    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.get", fake_get
    )

    jobs = run_actor(settings, "owner~actor", {"input": True}, 500)

    assert jobs == [{"title": "GIS Analyst"}]
    assert calls[0] == (
        "POST",
        "https://api.apify.com/v2/acts/owner~actor/runs",
        {"timeout": 3600, "memory": 512, "maxItems": 500},
    )
    assert calls[2] == (
        "GET",
        "https://api.apify.com/v2/datasets/dataset-1/items",
        {"format": "json", "limit": 500},
    )
    assert apify_http_timeout(settings) == 120


def test_run_actor_reports_apify_timed_out_status(monkeypatch):
    """A terminal TIMED-OUT actor status should be handled as a search timeout."""
    settings = make_settings()

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"data": {"id": "run-1", "defaultDatasetId": "dataset-1"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"data": {"id": "run-1", "status": "TIMED-OUT"}})

    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.post", fake_post
    )
    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.get", fake_get
    )

    with pytest.raises(ApifyRunTimeoutError):
        run_actor(settings, "owner~actor", {"input": True}, 500)


def test_fetch_jobs_for_search_retries_temporary_apify_http_errors(monkeypatch):
    """A temporary Apify 502 should be retried instead of becoming 0 results."""
    settings = make_settings()
    post_statuses = [502, 201]
    post_calls = 0

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        nonlocal post_calls
        post_calls += 1
        status_code = post_statuses.pop(0)
        if status_code >= 400:
            return FakeResponse("<h1>Bad Gateway</h1>", status_code=status_code)
        return FakeResponse({"data": {"id": "run-1", "defaultDatasetId": "dataset-1"}})

    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if "/actor-runs/" in url:
            return FakeResponse(
                {
                    "data": {
                        "id": "run-1",
                        "status": "SUCCEEDED",
                        "defaultDatasetId": "dataset-1",
                    }
                }
            )
        return FakeResponse([{"title": "GIS Analyst"}])

    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.post", fake_post
    )
    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.get", fake_get
    )

    jobs = fetch_jobs_for_search(
        settings,
        SearchRequest(
            source="linkedin",
            source_label="LinkedIn",
            keyword="GIS",
            display_label="LinkedIn / GIS",
            actor_id="owner~actor",
            payload={"input": True},
            max_items=500,
        ),
    )

    assert post_calls == 2
    assert jobs == [
        {"title": "GIS Analyst", "_source": "linkedin", "_source_label": "LinkedIn"}
    ]


def test_fetch_jobs_for_search_fails_after_retry_budget(monkeypatch):
    """A keyword should fail the pipeline instead of being silently skipped."""
    settings = make_settings()
    settings.apify_transient_error_retries = 1

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse("<h1>Bad Gateway</h1>", status_code=502)

    monkeypatch.setattr(
        "jobfinder.scraper.providers.apify_client.requests.post", fake_post
    )

    with pytest.raises(SearchExecutionError):
        fetch_jobs_for_search(
            settings,
            SearchRequest(
                source="linkedin",
                source_label="LinkedIn",
                keyword="GIS",
                display_label="LinkedIn / GIS",
                actor_id="owner~actor",
                payload={"input": True},
                max_items=500,
            ),
        )


def test_run_all_searches_batches_linkedin_when_results_are_attributable(monkeypatch):
    """Opt-in LinkedIn batching should preserve keyword attribution when possible."""
    settings = make_settings()
    settings.apify_batch_size = 2
    payloads: list[dict[str, Any]] = []

    def fake_run_actor(settings, actor_id, payload, max_items):
        payloads.append(payload)
        first_url, second_url = payload["urls"]
        return [
            {"title": "GIS Analyst", "inputUrl": first_url},
            {"title": "Python Analyst", "inputUrl": second_url},
        ]

    monkeypatch.setattr("jobfinder.scraper.search.run_actor", fake_run_actor)

    results, zero_searches, failed_sources, skipped_searches = run_all_searches(
        settings,
        [
            SearchRequest(
                source="linkedin",
                source_label="LinkedIn",
                keyword="GIS",
                display_label="LinkedIn / GIS",
                actor_id="owner~actor",
                payload={
                    "urls": ["https://www.linkedin.com/jobs/search/?keywords=GIS"]
                },
                max_items=500,
            ),
            SearchRequest(
                source="linkedin",
                source_label="LinkedIn",
                keyword="Python",
                display_label="LinkedIn / Python",
                actor_id="owner~actor",
                payload={
                    "urls": ["https://www.linkedin.com/jobs/search/?keywords=Python"]
                },
                max_items=500,
            ),
        ],
    )

    assert len(payloads) == 1
    assert [keyword for keyword, _ in results] == ["GIS", "Python"]
    assert [jobs[0]["title"] for _, jobs in results] == [
        "GIS Analyst",
        "Python Analyst",
    ]
    assert zero_searches == []
    assert failed_sources == {}
    assert skipped_searches == []
