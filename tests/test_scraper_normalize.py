"""Tests for scraper normalization and deduplication behavior."""

from __future__ import annotations

from jobfinder.scraper.normalize import (
    clean_job_description,
    merge_and_deduplicate,
    parse_applicant_count_value,
)


def test_parse_applicant_count_handles_text_units_and_plus():
    """Applicant parser should handle common labels from scraper actors."""
    assert parse_applicant_count_value("25 applicants") == 25
    assert parse_applicant_count_value("1.2k applicants") == 1200
    assert parse_applicant_count_value("Over 100 applicants") == 101
    assert parse_applicant_count_value({"label": "51+ applicants"}) == 52


def test_clean_job_description_removes_html_without_flattening_lists():
    """HTML descriptions should become readable plain text."""
    raw = "<p>Hello<br>World</p><ul><li>GIS</li><li>Python</li></ul>"

    assert clean_job_description(raw) == "Hello\nWorld\n* GIS\n* Python"


def test_merge_and_deduplicate_collects_all_matched_keywords():
    """Deduplication should keep one job and remember all matching keywords."""
    jobs = [
        ("GIS", [{"_source": "linkedin", "jobId": "1", "title": "Analyst"}]),
        ("Python", [{"_source": "linkedin", "jobId": "1", "title": "Analyst"}]),
    ]

    merged = merge_and_deduplicate(jobs)

    assert len(merged) == 1
    assert merged[0]["keywords_matched"] == ["GIS", "Python"]
