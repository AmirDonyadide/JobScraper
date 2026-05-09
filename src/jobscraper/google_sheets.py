"""Shared Google Sheets authentication and addressing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jobscraper.paths import (
    GOOGLE_CLIENT_SECRET_FILE,
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_TOKEN_FILE,
)

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
"""OAuth scopes required to read and write Google Sheets."""


def build_google_sheets_service(
    *,
    error_cls: type[RuntimeError],
    service_account_file: Path = GOOGLE_SERVICE_ACCOUNT_FILE,
    token_file: Path = GOOGLE_TOKEN_FILE,
    client_secret_file: Path = GOOGLE_CLIENT_SECRET_FILE,
    scopes: list[str] = GOOGLE_SCOPES,
) -> Any:
    """Build an authenticated Google Sheets API service."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise error_cls(
            "Missing Google API packages. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        ) from exc

    if service_account_file.exists():
        creds = service_account.Credentials.from_service_account_file(
            str(service_account_file), scopes=scopes
        )
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if not creds.has_scopes(scopes):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secret_file.exists():
                raise error_cls(
                    f"Missing {service_account_file.name}. Create a Google service "
                    "account, download its JSON key, save it in this folder, and "
                    "share the target spreadsheet with the service-account email. "
                    f"For local OAuth fallback, create {client_secret_file.name} "
                    "instead."
                )
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow
            except ImportError as exc:
                raise error_cls(
                    "Missing Google OAuth packages for local browser auth. Install "
                    "dependencies with: python -m pip install -r requirements.txt"
                ) from exc

            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_file), scopes
            )
            creds = flow.run_local_server(port=0)

        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def quote_sheet_name(name: str) -> str:
    """Quote a Google Sheet tab name for A1 notation."""
    return "'" + name.replace("'", "''") + "'"
