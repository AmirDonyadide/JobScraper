"""Tests for the new Indeed provider integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from jobfinder.providers.indeed import (
    build_actor_input,
    normalize_actor_item,
    run_actor_search,
)
from jobfinder.scraper.normalize import get_apply_url, get_job_url


def make_settings(**overrides: Any) -> SimpleNamespace:
    """Build the provider settings used by Indeed tests."""
    values = {
        "indeed_country": "DE",
        "indeed_location": "Germany",
        "indeed_max_results_per_search": 500,
        "published_at": "r86400",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def sample_actor_item() -> dict[str, Any]:
    """Return a representative valig/indeed-jobs-scraper result."""
    return {
        "key": "abc123",
        "url": "https://www.indeed.com/viewjob?jk=abc123&from=search",
        "jobUrl": "https://jobs.example.com/apply/abc123",
        "title": "Data Analyst",
        "employer": {
            "name": "Acme Data",
            "ratingsValue": 4.1,
            "ratingsCount": 120,
            "employeesCount": "1,001 to 5,000",
            "industry": "Technology",
        },
        "location": {
            "city": "Berlin",
            "admin1Code": "BE",
            "countryName": "Germany",
        },
        "description": {"text": "Build dashboards with Python and SQL."},
        "datePublished": "2026-05-12T10:00:00Z",
        "baseSalary": {
            "minValue": 75000,
            "maxValue": "95000",
            "currencyCode": "EUR",
            "unitOfWork": "YEAR",
        },
        "jobTypes": {"0": "Full-time"},
        "attributes": {
            "0": "Python",
            "1": "SQL",
            "2": "3+ years experience",
            "3": "Mid level",
            "4": "Bachelor's degree",
        },
        "benefits": {"0": "Health insurance"},
        "employerAttributes": {"0": "Hybrid work"},
    }


def test_build_actor_input_uses_new_actor_schema_and_date_bucket():
    """Indeed payloads should match valig/indeed-jobs-scraper input names."""
    payload = build_actor_input(
        make_settings(indeed_max_results_per_search=1500, published_at="r90000"),
        "GIS analyst",
    )

    assert payload == {
        "country": "de",
        "title": "GIS analyst",
        "location": "Germany",
        "limit": 1000,
        "datePosted": "3",
    }
    assert "position" not in payload
    assert "maxItems" not in payload
    assert "maxConcurrency" not in payload
    assert "saveOnlyUniqueItems" not in payload


def test_build_actor_input_omits_date_filter_for_large_backfills():
    """Indeed supports fixed day buckets, so long windows should be filtered later."""
    payload = build_actor_input(
        make_settings(published_at="r2592000"),
        "GIS analyst",
    )

    assert payload == {
        "country": "de",
        "title": "GIS analyst",
        "location": "Germany",
        "limit": 500,
    }


def test_normalize_actor_item_preserves_contract_and_adds_internal_metadata():
    """Actor output should feed existing exporters without adding sheet columns."""
    job = normalize_actor_item(sample_actor_item())

    assert job["jobId"] == "abc123"
    assert job["title"] == "Data Analyst"
    assert job["companyName"] == "Acme Data"
    assert job["location"] == "Berlin, BE, Germany"
    assert job["jobType"] == "Full-time"
    assert job["postedAt"] == "2026-05-12T10:00:00Z"
    assert job["jobUrl"] == "https://www.indeed.com/viewjob?jk=abc123&from=search"
    assert job["applyUrl"] == "https://jobs.example.com/apply/abc123"

    metadata = job["_jobfinder_indeed_metadata"]
    assert metadata["salary"] == "EUR 75,000-95,000 / year"
    assert metadata["remote_work"] == "Hybrid"
    assert metadata["skills"] == ["Python", "SQL"]
    assert metadata["programming_languages"] == ["Python", "SQL"]
    assert metadata["experience_requirements"] == ["3+ years experience"]
    assert metadata["education_requirements"] == ["Bachelor's degree"]

    assert "Indeed structured metadata:" in job["description"]
    assert "- Salary: EUR 75,000-95,000 / year" in job["description"]
    assert "- Work mode: Hybrid" in job["description"]


def test_normalized_urls_keep_indeed_job_url_separate_from_apply_url():
    """Historical dedupe should see Indeed URLs, while apply links stay separate."""
    job = normalize_actor_item(sample_actor_item())

    assert get_job_url(make_settings(), job) == (
        "https://www.indeed.com/viewjob?jk=abc123&from=search"
    )
    assert get_apply_url(job) == "https://jobs.example.com/apply/abc123"


def test_run_actor_search_normalizes_actor_results():
    """Indeed execution should isolate actor-specific output conversion."""
    calls: list[tuple[str, dict[str, Any], int]] = []

    def fake_runner(settings, actor_id, payload, max_items):
        calls.append((actor_id, payload, max_items))
        return [sample_actor_item()]

    jobs = run_actor_search(
        make_settings(),
        "valig~indeed-jobs-scraper",
        {"title": "GIS"},
        500,
        actor_runner=fake_runner,
    )

    assert calls == [("valig~indeed-jobs-scraper", {"title": "GIS"}, 500)]
    assert jobs[0]["jobId"] == "abc123"
    assert jobs[0]["companyName"] == "Acme Data"
