"""Tests for deterministic cross-provider duplicate detection."""

from __future__ import annotations

from jobfinder.scraper.export_rows import make_job_rows
from jobfinder.scraper.normalize import merge_and_deduplicate
from jobfinder.scraper.run_history import (
    job_identity_keys_from_values,
    remove_jobs_seen_in_history,
)


class MinimalSettings:
    """Small settings double for dedupe-facing helpers."""

    posted_tz = None


def test_linkedin_indeed_duplicates_merge_with_combined_app_column():
    """The same real-world job on LinkedIn and Indeed should become one row."""
    jobs = [
        (
            "GIS",
            [
                {
                    "_source": "linkedin",
                    "_source_label": "LinkedIn",
                    "jobId": "123456",
                    "title": "Senior GIS Analyst (m/f/d)",
                    "companyName": "GeoCo GmbH",
                    "location": "Berlin, Germany",
                    "jobUrl": "https://www.linkedin.com/jobs/view/123456/?trk=x",
                    "description": "Analyze maps.",
                }
            ],
        ),
        (
            "Python",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "abc123",
                    "title": "Senior GIS Analyst",
                    "companyName": "GeoCo",
                    "location": "Berlin",
                    "url": "https://de.indeed.com/viewjob?jk=abc123&from=search",
                    "applyUrl": "https://careers.geoco.example/jobs/42?utm_source=indeed",
                    "description": (
                        "Analyze maps, automate GIS workflows, and publish "
                        "spatial data products."
                    ),
                }
            ],
        ),
    ]

    merged = merge_and_deduplicate(jobs)
    rows = make_job_rows(MinimalSettings(), merged)  # type: ignore[arg-type]

    assert len(merged) == 1
    assert merged[0]["_source_label"] == "LinkedIn | Indeed"
    assert merged[0]["keywords_matched"] == ["GIS", "Python"]
    assert "automate GIS workflows" in merged[0]["description"]
    assert {item["label"] for item in merged[0]["_jobfinder_provenance"]} == {
        "LinkedIn",
        "Indeed",
    }
    assert rows[1][1] == "LinkedIn | Indeed"


def test_indeed_stepstone_title_and_location_variants_merge():
    """Canonical normalization should handle naming, gender tags, and city aliases."""
    jobs = [
        (
            "Data",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "indeed-1",
                    "title": "Data Engineer - Remote (m/f/d)",
                    "companyName": "Acme Data GmbH",
                    "location": "Munich, Germany",
                    "description": "Build data pipelines for analytics.",
                }
            ],
        ),
        (
            "Engineer",
            [
                {
                    "_source": "stepstone",
                    "_source_label": "Stepstone",
                    "id": "step-1",
                    "title": "Data Engineer (all genders)",
                    "companyName": "Acme Data",
                    "location": "München",
                    "description": "Build data pipelines for analytics and reporting.",
                }
            ],
        ),
    ]

    merged = merge_and_deduplicate(jobs)

    assert len(merged) == 1
    assert merged[0]["_source_label"] == "Indeed | Stepstone"


def test_all_platform_duplicates_preserve_all_provenance():
    """A three-platform match should keep one canonical job with all platforms."""
    jobs = [
        (
            "GIS",
            [
                {
                    "_source": "linkedin",
                    "_source_label": "LinkedIn",
                    "jobId": "li-1",
                    "title": "GIS Developer",
                    "companyName": "MapWorks GmbH",
                    "location": "Cologne",
                }
            ],
        ),
        (
            "Python",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "in-1",
                    "title": "GIS Developer",
                    "companyName": "MapWorks",
                    "location": "Köln",
                }
            ],
        ),
        (
            "Maps",
            [
                {
                    "_source": "stepstone",
                    "_source_label": "Stepstone",
                    "id": "ss-1",
                    "title": "GIS Developer (m/w/d)",
                    "companyName": "MapWorks",
                    "location": "Koeln",
                }
            ],
        ),
    ]

    merged = merge_and_deduplicate(jobs)

    assert len(merged) == 1
    assert merged[0]["_source_label"] == "LinkedIn | Indeed | Stepstone"
    assert merged[0]["keywords_matched"] == ["GIS", "Python", "Maps"]
    assert [item["label"] for item in merged[0]["_jobfinder_provenance"]] == [
        "LinkedIn",
        "Indeed",
        "Stepstone",
    ]


def test_remote_and_hybrid_location_variants_merge_when_role_matches():
    """Work-mode suffixes in location should not split the same city job."""
    jobs = [
        (
            "Analytics",
            [
                {
                    "_source": "linkedin",
                    "_source_label": "LinkedIn",
                    "jobId": "li-2",
                    "title": "Analytics Engineer",
                    "companyName": "DataHaus GmbH",
                    "location": "Berlin (Hybrid)",
                }
            ],
        ),
        (
            "SQL",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "in-2",
                    "title": "Analytics Engineer",
                    "companyName": "DataHaus",
                    "location": "Berlin, Germany",
                }
            ],
        ),
    ]

    assert len(merge_and_deduplicate(jobs)) == 1


def test_conflicting_titles_do_not_merge():
    """Similar company/location alone is not enough for a safe merge."""
    jobs = [
        (
            "Data",
            [
                {
                    "_source": "linkedin",
                    "_source_label": "LinkedIn",
                    "jobId": "li-3",
                    "title": "Senior Data Analyst",
                    "companyName": "Acme",
                    "location": "Berlin",
                }
            ],
        ),
        (
            "Data",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "in-3",
                    "title": "Senior Data Engineer",
                    "companyName": "Acme GmbH",
                    "location": "Berlin",
                }
            ],
        ),
    ]

    assert len(merge_and_deduplicate(jobs)) == 2


def test_salary_conflicts_prevent_exact_profile_merge():
    """Exact company/title/location still should not override salary contradictions."""
    jobs = [
        (
            "Analyst",
            [
                {
                    "_source": "linkedin",
                    "_source_label": "LinkedIn",
                    "jobId": "li-4",
                    "title": "Data Analyst",
                    "companyName": "Acme",
                    "location": "Berlin",
                    "salary": "€50,000 - €60,000 per year",
                }
            ],
        ),
        (
            "Analyst",
            [
                {
                    "_source": "indeed",
                    "_source_label": "Indeed",
                    "key": "in-4",
                    "title": "Data Analyst",
                    "companyName": "Acme GmbH",
                    "location": "Berlin",
                    "salary": "€120,000 - €140,000 per year",
                }
            ],
        ),
    ]

    assert len(merge_and_deduplicate(jobs)) == 2


def test_historical_dedupe_matches_cross_provider_profile_keys():
    """A previous LinkedIn row should suppress the same future Indeed job."""
    historical_keys = job_identity_keys_from_values(
        source="LinkedIn",
        title="GIS Analyst (m/f/d)",
        company="GeoCo GmbH",
        location="Berlin, Germany",
        job_url="https://www.linkedin.com/jobs/view/123456/?trk=x",
    )
    jobs = [
        {
            "_source": "indeed",
            "_source_label": "Indeed",
            "key": "indeed-new-id",
            "title": "GIS Analyst",
            "companyName": "GeoCo",
            "location": "Berlin",
            "url": "https://de.indeed.com/viewjob?jk=indeed-new-id",
        }
    ]

    kept, duplicate_count = remove_jobs_seen_in_history(
        MinimalSettings(),  # type: ignore[arg-type]
        jobs,
        historical_keys,
    )

    assert kept == []
    assert duplicate_count == 1
