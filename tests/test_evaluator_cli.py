"""Tests for evaluator CLI argument resolution."""

from __future__ import annotations

from jobfinder.env import EnvSettings
from jobfinder.evaluator.cli import build_arg_parser, parse_source


def test_parse_source_accepts_google_aliases():
    """Source aliases should resolve consistently across CLI and env settings."""
    env = EnvSettings({})

    assert parse_source("sheets", "", env) == "google_sheets"
    assert parse_source("drive", "", env) == "google_sheets"
    assert parse_source("local", "", env) == "excel"


def test_parse_source_defaults_to_google_when_sheet_id_is_configured(monkeypatch):
    """A configured spreadsheet ID should make Google Sheets the default source."""
    monkeypatch.delenv("JOB_EVAL_SOURCE", raising=False)

    assert parse_source(None, "spreadsheet-id", EnvSettings({})) == "google_sheets"


def test_arg_parser_accepts_google_sheet_id_option():
    """The CLI should expose the Google Sheet ID option mentioned in errors."""
    parser = build_arg_parser(EnvSettings({}))

    args = parser.parse_args(
        ["--source", "google", "--google-sheet-id", "spreadsheet-id"]
    )

    assert args.source == "google"
    assert args.google_sheet_id == "spreadsheet-id"
