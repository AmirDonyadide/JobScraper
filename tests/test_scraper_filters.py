"""Tests for scraper final filters."""

from __future__ import annotations

from types import SimpleNamespace

from jobfinder.scraper.filters import filter_applicant_count, filter_excluded_companies


def test_filter_excluded_companies_matches_case_insensitive_substrings():
    """Company exclusions should match names inside longer company names."""
    settings = SimpleNamespace(
        excluded_company_terms=[
            "Zeiss",
            "Boston Consulting Group",
            "BCG",
            "Fraunhofer",
            "German Aerospace Center",
            "DLR",
            "Siemens",
            "Tesla",
        ]
    )
    jobs = [
        {"title": "Analyst", "companyName": "ZEISS Group"},
        {"title": "Consultant", "companyName": "BCG X"},
        {"title": "Researcher", "companyName": "Fraunhofer IOSB"},
        {"title": "Engineer", "companyName": "German Aerospace Center (DLR)"},
        {"title": "Developer", "companyName": "GeoSoft GmbH"},
    ]

    kept, excluded_count = filter_excluded_companies(settings, jobs)

    assert [job["companyName"] for job in kept] == ["GeoSoft GmbH"]
    assert excluded_count == 4


def test_filter_excluded_companies_matches_punctuation_variants():
    """Normalized matching should catch filtered names split by punctuation."""
    settings = SimpleNamespace(excluded_company_terms=["Airbus Aircraft", "IBM"])
    jobs = [
        {"title": "Engineer", "companyName": "Airbus-Aircraft GmbH"},
        {"title": "Consultant", "companyName": "I.B.M. Consulting"},
        {"title": "Engineer", "companyName": "Open Systems GmbH"},
    ]

    kept, excluded_count = filter_excluded_companies(settings, jobs)

    assert [job["companyName"] for job in kept] == ["Open Systems GmbH"]
    assert excluded_count == 2


def test_filter_applicant_count_zero_disables_limit():
    """A zero applicant cap is used by the workflow's no-limit option."""
    settings = SimpleNamespace(max_applicants=0)
    jobs = [
        {"title": "Busy role", "applicantsCount": 500},
        {"title": "Quiet role", "applicantsCount": 1},
    ]

    kept, excluded_count = filter_applicant_count(settings, jobs)

    assert kept == jobs
    assert excluded_count == 0
