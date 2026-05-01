"""
LinkedIn Job Scraper
====================
Uses Apify's LinkedIn Jobs Scraper actor to search for jobs
across multiple keywords with predefined filters, then deduplicates
and exports results to a Google Sheet in your Google Drive.

Requirements:
    pip install -r requirements.txt

Usage:
    1. Put APIFY_API_TOKEN in .env (or set it as an environment variable)
    2. Put Google OAuth credentials in google_client_secret.json
    3. Run: python linkedin_job_scraper.py
    4. Open the Google Sheet URL printed at the end
"""

import json
import os
import time
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

# ─────────────────────────────────────────────
#  CONFIGURATION — edit these
# ─────────────────────────────────────────────

TOKEN_ENV_VAR = "APIFY_API_TOKEN"
TOKEN_FILE = Path(__file__).with_name(".env")
TOKEN_PLACEHOLDER = "apify_api_XXXXXXXXXXXX"
GOOGLE_CLIENT_SECRET_FILE = Path(__file__).with_name("google_client_secret.json")
GOOGLE_TOKEN_FILE = Path(__file__).with_name("google_token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def load_apify_token() -> str:
    """
    Load the Apify token from the environment first, then from local .env.

    Supported .env formats:
        APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
        export APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
    """
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if token:
        return token

    if not TOKEN_FILE.exists():
        return ""

    for line in TOKEN_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key.strip() == TOKEN_ENV_VAR:
            return value.strip().strip("\"'")

    return ""


APIFY_API_TOKEN = load_apify_token()

# Apify actor for LinkedIn Jobs (Curious Coder scraper)
# Apify's raw REST API uses "~" between username and actor name.
ACTOR_ID = "curious_coder~linkedin-jobs-scraper"

# Max jobs to fetch per search URL (increase if you want more, costs more credits)
MAX_RESULTS_PER_SEARCH = 500

# Seconds to wait between keyword requests (be polite to the API)
DELAY_BETWEEN_REQUESTS = 3

# Output Google Sheet title
SPREADSHEET_TITLE = f"LinkedIn Jobs {datetime.now().strftime('%Y-%m-%d')}"

# ─────────────────────────────────────────────
#  SEARCH FILTERS (LinkedIn URL parameters)
# ─────────────────────────────────────────────
# f_TPR=r86400 -> Posted in last 24 hours
# f_E values   -> 1=Internship, 2=Entry level
# f_JT values  -> F=Full-time, P=Part-time, I=Internship

LOCATION = "Germany"
GEO_ID = "101282230"
PUBLISHED_AT = "r86400"
EXPERIENCE_LEVELS = ["1", "2"]
CONTRACT_TYPES = ["F", "P", "I"]
SCRAPE_COMPANY_DETAILS = True
USE_INCOGNITO_MODE = True
SPLIT_BY_LOCATION = False
SPLIT_COUNTRY = "DE"

# ─────────────────────────────────────────────
#  KEYWORDS
# ─────────────────────────────────────────────

KEYWORDS = [
    "3D Mapping",
    "Bauvermessung",
    "Cartography",
    "Earth Observation",
    "Erdbeobachtung",
    "Fernerkundung",
    "GeoAI",
    "Geoanalytics",
    "Geodaten",
    "Geodatenanalyse",
    "Geodatenbank",
    "Geodatenmanagement",
    "Geodäsie",
    "Geoinformatik",
    "Geoinformatiker",
    "Geoinformationssysteme",
    "Geomatik",
    "Geomatics",
    "Geomatiker",
    "Geospatial",
    "Geovisualisierung",
    "GIS",
    "GIS Analyst",
    "GIS Entwickler",
    "GIS Spezialist",
    "Kartografie",
    "Laserscanning",
    "Mapping",
    "Photogrammetrie",
    "Raumdaten",
    "Remote Sensing",
    "Spatial",
    "Surveying",
    "Topografie",
    "Trassierung",
    "Umweltplanung",
    "Vermessung",
    "Vermessungsingenieur",
    "Vermessungstechniker",
]

# ─────────────────────────────────────────────
#  APIFY API CALL
# ─────────────────────────────────────────────

class ApifyConfigurationError(RuntimeError):
    """Raised when Apify rejects the token, actor access, or paid actor setup."""


def apify_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {APIFY_API_TOKEN}"}


def apify_error_message(response: requests.Response) -> str:
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


def build_search_url(keyword: str) -> str:
    params = {
        "keywords": keyword,
        "location": LOCATION,
        "geoId": GEO_ID,
        "f_TPR": PUBLISHED_AT,
        "f_E": ",".join(EXPERIENCE_LEVELS),
        "f_JT": ",".join(CONTRACT_TYPES),
        "position": "1",
        "pageNum": "0",
    }
    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def get_searches() -> tuple[str, list[tuple[str, str]]]:
    generated_searches = [(keyword, build_search_url(keyword)) for keyword in KEYWORDS]
    return "generated keyword URLs", generated_searches


def build_actor_input(search_url: str) -> dict:
    payload = {
        "urls": [search_url],
        "count": MAX_RESULTS_PER_SEARCH,
        "scrapeCompany": SCRAPE_COMPANY_DETAILS,
        "useIncognitoMode": USE_INCOGNITO_MODE,
        "splitByLocation": SPLIT_BY_LOCATION,
    }
    if SPLIT_BY_LOCATION:
        payload["splitCountry"] = SPLIT_COUNTRY
    return payload


def run_actor(payload: dict) -> list[dict]:
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    params = {
        "timeout": 300,
        "memory": 512,
        "maxItems": MAX_RESULTS_PER_SEARCH,
    }

    response = requests.post(
        url,
        params=params,
        headers=apify_headers(),
        json=payload,
        timeout=180,
    )

    if response.status_code in (401, 403):
        message = apify_error_message(response)
        raise ApifyConfigurationError(
            "Apify rejected the request. Check that APIFY_API_TOKEN is valid, "
            f"that your account can run {ACTOR_ID}, and that billing/trial "
            f"access is active. Apify said: {message}"
        )

    response.raise_for_status()
    data = response.json()

    # Apify returns a list directly for run-sync-get-dataset-items.
    if isinstance(data, list):
        return data
    # Some actors wrap results in a dict.
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return []


def fetch_jobs_for_search(label: str, search_url: str) -> list[dict]:
    """
    Calls the Apify LinkedIn Jobs Scraper actor synchronously
    and returns a list of job dicts for the given LinkedIn search URL.
    """
    try:
        return run_actor(build_actor_input(search_url))
    except requests.exceptions.Timeout:
        print(f"  ⚠ Timeout for search '{label}' — skipping.")
        return []
    except requests.exceptions.ConnectionError as e:
        raise ApifyConfigurationError(
            f"Could not connect to Apify API while searching '{label}'. "
            f"Check your internet connection/DNS and try again. Details: {e}"
        ) from e
    except ApifyConfigurationError:
        raise
    except requests.exceptions.HTTPError as e:
        response = e.response
        details = f" {apify_error_message(response)}" if response is not None else ""
        print(f"  ⚠ HTTP error for search '{label}': {e}.{details} — skipping.")
        return []
    except Exception as e:
        print(f"  ⚠ Unexpected error for search '{label}': {e} — skipping.")
        return []


# ─────────────────────────────────────────────
#  DEDUPLICATION
# ─────────────────────────────────────────────

def make_dedup_key(job: dict) -> str:
    """
    Primary key: jobId (if available).
    Fallback key: title + company + location (lowercased, stripped).
    """
    job_id = job.get("jobId") or job.get("job_id") or job.get("id") or ""
    if job_id:
        return str(job_id).strip()

    title   = str(job.get("title") or job.get("jobTitle") or job.get("job_title") or "").lower().strip()
    company = str(job.get("company") or job.get("companyName") or job.get("company_name") or "").lower().strip()
    location= str(job.get("location") or job.get("jobLocation") or job.get("job_location") or "").lower().strip()
    return f"{title}|{company}|{location}"


def merge_and_deduplicate(all_results: dict[str, list]) -> list[dict]:
    """
    all_results: { keyword: [job, job, ...], ... }
    Returns a deduplicated list of jobs, each annotated with
    'keywords_matched' = list of keywords that found it.
    """
    seen: dict[str, dict] = {}   # dedup_key → job dict

    for keyword, jobs in all_results.items():
        for job in jobs:
            key = make_dedup_key(job)
            if key in seen:
                # Job already recorded — just add keyword to its matched list
                seen[key]["keywords_matched"].append(keyword)
            else:
                job_copy = dict(job)
                job_copy["keywords_matched"] = [keyword]
                seen[key] = job_copy

    return list(seen.values())


# ─────────────────────────────────────────────
#  FIELD EXTRACTION HELPERS
# ─────────────────────────────────────────────

def safe(job: dict, *keys) -> str:
    """Try multiple key names and return first non-empty value."""
    for k in keys:
        v = job.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return "N/A"


def get_job_url(job: dict) -> str:
    url = (
        job.get("jobUrl")
        or job.get("job_url")
        or job.get("linkedinUrl")
        or job.get("linkedin_url")
        or job.get("url")
        or job.get("link")
        or ""
    )
    if url:
        return url
    job_id = job.get("jobId") or job.get("job_id") or job.get("id") or ""
    if job_id:
        return f"https://www.linkedin.com/jobs/view/{job_id}/"
    return "N/A"


def get_posted(job: dict) -> str:
    return safe(job, "postedAt", "posted_at", "publishedAt", "published_at", "datePosted", "date_posted", "posted", "listedAt", "listed_at")


def get_job_type(job: dict) -> str:
    return safe(job, "employmentType", "employment_type", "jobType", "job_type", "contractType", "contract_type", "type")


def get_experience(job: dict) -> str:
    return safe(job, "experienceLevel", "experience_level", "seniorityLevel", "seniority_level", "seniority")


# ─────────────────────────────────────────────
#  GOOGLE SHEETS EXPORT
# ─────────────────────────────────────────────

HEADER = [
    "#", "Job Title", "Company", "Location", "Job Type", "Posted",
    "Experience Level", "Job Function", "Industries", "Salary",
    "Applicants", "Benefits", "Workplace Types", "Remote Allowed",
    "Keywords Matched", "LinkedIn URL", "Apply URL", "Company Website",
    "Company Employees", "Job Poster", "Job Poster Title", "Description",
]

MAX_CELL_CHARS = 49000


class GoogleSheetsExportError(RuntimeError):
    """Raised when Google Sheets export is not configured correctly."""


def sheet_safe(value) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value if item is not None and str(item).strip())
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)

    text = text.strip()
    if not text:
        return "N/A"
    if len(text) > MAX_CELL_CHARS:
        return text[:MAX_CELL_CHARS - 20] + " ... [truncated]"
    if text[0] in "=+-@":
        return "'" + text
    return text


def field(job: dict, *keys) -> str:
    for key in keys:
        value = job.get(key)
        if value is not None and sheet_safe(value) != "N/A":
            return sheet_safe(value)
    return "N/A"


def sheets_string(value: str) -> str:
    return str(value).replace('"', '""')


def hyperlink_formula(url: str, label: str) -> str:
    if not url or url == "N/A":
        return "N/A"
    return f'=HYPERLINK("{sheets_string(url)}", "{sheets_string(label)}")'


def make_job_rows(jobs: list[dict]) -> list[list]:
    rows = [HEADER]
    for i, job in enumerate(jobs, start=1):
        linkedin_url = get_job_url(job)
        apply_url = field(job, "applyUrl", "apply_url")
        rows.append([
            i,
            field(job, "title", "jobTitle", "name"),
            field(job, "companyName", "company", "organization"),
            field(job, "location", "jobLocation", "place"),
            get_job_type(job),
            get_posted(job),
            get_experience(job),
            field(job, "jobFunction", "job_function"),
            field(job, "industries", "industry"),
            field(job, "salaryInfo", "salary_info", "salaryInsights", "salary_insights"),
            field(job, "applicantsCount", "applicants_count"),
            field(job, "benefits"),
            field(job, "workplaceTypes", "workplace_types"),
            field(job, "workRemoteAllowed", "work_remote_allowed"),
            ", ".join(job.get("keywords_matched", [])),
            hyperlink_formula(linkedin_url, "Open LinkedIn"),
            hyperlink_formula(apply_url, "Open Apply"),
            hyperlink_formula(field(job, "companyWebsite", "company_website"), "Open Company"),
            field(job, "companyEmployeesCount", "company_employees_count"),
            field(job, "jobPosterName", "job_poster_name"),
            field(job, "jobPosterTitle", "job_poster_title"),
            field(job, "descriptionText", "description_text"),
        ])
    return rows


def build_google_sheets_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise GoogleSheetsExportError(
            "Missing Google API packages. Install them with:\n"
            "   pip install -r requirements.txt"
        ) from e

    creds = None
    if GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_FILE), GOOGLE_SCOPES)
        if not creds.has_scopes(GOOGLE_SCOPES):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not GOOGLE_CLIENT_SECRET_FILE.exists():
                raise GoogleSheetsExportError(
                    f"Missing {GOOGLE_CLIENT_SECRET_FILE.name}. Create a Google OAuth "
                    "Desktop client, download its JSON credentials, and save it in this folder."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CLIENT_SECRET_FILE), GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        GOOGLE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("sheets", "v4", credentials=creds)


def quote_sheet_name(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def update_values(service, spreadsheet_id: str, sheet_name: str, rows: list[list]):
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{quote_sheet_name(sheet_name)}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()


def format_spreadsheet(service, spreadsheet_id: str, sheet_ids: dict[str, int], job_row_count: int):
    jobs_sheet_id = sheet_ids["Jobs"]
    requests_body = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": jobs_sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {
                    "sheetId": jobs_sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.063, "green": 0.173, "blue": 0.325},
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "bold": True,
                            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)",
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {
                        "sheetId": jobs_sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": max(job_row_count, 1),
                        "startColumnIndex": 0,
                        "endColumnIndex": len(HEADER),
                    }
                }
            }
        },
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": jobs_sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": len(HEADER),
                }
            }
        },
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests_body},
    ).execute()


def export_to_google_sheets(service, jobs: list[dict], zero_searches: list[str], search_count: int) -> str:
    jobs_sheet_name = f"Jobs {datetime.now().strftime('%Y-%m-%d')}"
    spreadsheet = service.spreadsheets().create(
        body={
            "properties": {"title": SPREADSHEET_TITLE},
            "sheets": [
                {"properties": {"title": jobs_sheet_name}},
                {"properties": {"title": "Summary"}},
                {"properties": {"title": "No Results"}},
            ],
        },
        fields="spreadsheetId,spreadsheetUrl,sheets(properties(sheetId,title))",
    ).execute()

    spreadsheet_id = spreadsheet["spreadsheetId"]
    sheet_ids = {
        sheet["properties"]["title"]: sheet["properties"]["sheetId"]
        for sheet in spreadsheet["sheets"]
    }
    sheet_ids["Jobs"] = sheet_ids[jobs_sheet_name]

    job_rows = make_job_rows(jobs)
    summary_rows = [
        ["Run date", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Searches run", search_count],
        ["Unique jobs found", len(jobs)],
        ["Searches with 0 results", len(zero_searches)],
        ["Actor", ACTOR_ID],
    ]
    no_result_rows = [["Search", "Status"]] + [[label, "0 results found"] for label in zero_searches]

    update_values(service, spreadsheet_id, jobs_sheet_name, job_rows)
    update_values(service, spreadsheet_id, "Summary", summary_rows)
    update_values(service, spreadsheet_id, "No Results", no_result_rows)
    format_spreadsheet(service, spreadsheet_id, sheet_ids, len(job_rows))

    return spreadsheet["spreadsheetUrl"]


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    if not APIFY_API_TOKEN or APIFY_API_TOKEN == TOKEN_PLACEHOLDER:
        print(f"❌ Please set {TOKEN_ENV_VAR} in {TOKEN_FILE.name} or as an environment variable.")
        print(f"   Add this line to {TOKEN_FILE.name}:")
        print(f"   {TOKEN_ENV_VAR}={TOKEN_PLACEHOLDER}")
        return

    search_source, searches = get_searches()
    if not searches:
        print("❌ No LinkedIn searches configured.")
        print("   Add keywords in the script.")
        return

    print("Checking Google Sheets access ...")
    try:
        google_sheets_service = build_google_sheets_service()
    except GoogleSheetsExportError as e:
        print(f"\n❌ {e}")
        return

    print("=" * 60)
    print(f"  LinkedIn Job Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Actor: {ACTOR_ID}")
    print(f"  Search source: {search_source}")
    print(f"  Searches: {len(searches)}  |  Job types: {', '.join(CONTRACT_TYPES)}")
    print(f"  Experience levels: {', '.join(EXPERIENCE_LEVELS)}")
    print(f"  Max results per search: {MAX_RESULTS_PER_SEARCH}")
    print("=" * 60)

    all_results:   dict[str, list] = {}
    zero_searches: list[str]       = []

    for idx, (label, search_url) in enumerate(searches, start=1):
        print(f"\n[{idx:02d}/{len(searches)}] Searching: '{label}' ...", end=" ", flush=True)

        try:
            jobs = fetch_jobs_for_search(label, search_url)
        except ApifyConfigurationError as e:
            print(f"\n❌ {e}")
            print("   Fix the issue above, then run the script again.")
            return

        all_results[label] = jobs

        if jobs:
            print(f"✓ {len(jobs)} job(s) found")
        else:
            print(f"— 0 results")
            zero_searches.append(label)

        if idx < len(searches):
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # ── Deduplicate ──────────────────────────────
    print("\n" + "─" * 60)
    print("Deduplicating results ...")
    unique_jobs = merge_and_deduplicate(all_results)

    # ── Sort by posted date (most recent first) ──
    # Keep N/A entries at the bottom
    def sort_key(job):
        posted = get_posted(job)
        return posted if posted != "N/A" else "0000"

    unique_jobs.sort(key=sort_key, reverse=True)

    # ── Export ───────────────────────────────────
    print("Creating Google Sheet ...")
    try:
        spreadsheet_url = export_to_google_sheets(
            google_sheets_service,
            unique_jobs,
            zero_searches,
            len(searches),
        )
    except GoogleSheetsExportError as e:
        print(f"\n❌ {e}")
        return

    # ── Summary ──────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Searched {len(searches)} search URL(s) → Found {len(unique_jobs)} unique job postings.")
    if zero_searches:
        print(f"  Searches with 0 results ({len(zero_searches)}):")
        for label in zero_searches:
            print(f"    • {label}")
    print(f"  Google Sheet: {spreadsheet_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
