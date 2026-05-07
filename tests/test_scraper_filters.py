"""Tests for scraper final filters."""

from __future__ import annotations

from types import SimpleNamespace

from jobscraper.scraper.filters import filter_excluded_companies


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
