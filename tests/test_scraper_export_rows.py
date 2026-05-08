"""Tests for spreadsheet row generation."""

from __future__ import annotations

from jobscraper.evaluator.models import OUTPUT_COLUMNS
from jobscraper.scraper.export_rows import HEADER, make_job_rows


class MinimalSettings:
    """Small settings double for row-generation tests."""

    posted_tz = None


def test_generated_spreadsheet_headers_include_evaluator_output_columns():
    """Fresh scraper exports should include the final evaluator columns."""
    assert HEADER[-len(OUTPUT_COLUMNS) :] == OUTPUT_COLUMNS


def test_generated_spreadsheet_rows_include_blank_evaluator_cells():
    """Job rows should align with headers before the evaluator fills AI cells."""
    rows = make_job_rows(
        MinimalSettings(),  # type: ignore[arg-type]
        [
            {
                "_source_label": "LinkedIn",
                "title": "GIS Analyst",
                "companyName": "Acme",
                "location": "Berlin",
                "description": "Analyze spatial data.",
                "keywords_matched": ["GIS"],
            }
        ],
    )

    assert len(rows[1]) == len(HEADER)
    assert rows[1][-len(OUTPUT_COLUMNS) :] == [""] * len(OUTPUT_COLUMNS)
