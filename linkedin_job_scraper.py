"""
LinkedIn Job Scraper
====================
Uses Apify's LinkedIn Jobs Scraper actor to search for jobs
across multiple keywords with predefined filters, then deduplicates
and exports results to a dated Excel file.

Requirements:
    pip install requests openpyxl

Usage:
    1. Put APIFY_API_TOKEN in .env (or set it as an environment variable)
    2. Run: python linkedin_job_scraper.py
    3. Find your output in: jobs_YYYY-MM-DD.xlsx
"""

import os
import time
import requests
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
#  CONFIGURATION — edit these
# ─────────────────────────────────────────────

TOKEN_ENV_VAR = "APIFY_API_TOKEN"
TOKEN_FILE = Path(__file__).with_name(".env")
TOKEN_PLACEHOLDER = "apify_api_XXXXXXXXXXXX"


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

# Apify actor for LinkedIn Jobs (scraper)
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"

# Max jobs to fetch per keyword/job type pair (increase if you want more, costs more credits)
MAX_RESULTS_PER_JOB_TYPE = 100

# Seconds to wait between keyword requests (be polite to the API)
DELAY_BETWEEN_REQUESTS = 3

# Output file
OUTPUT_FILE = f"jobs_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

# ─────────────────────────────────────────────
#  SEARCH FILTERS (Apify actor input parameters)
# ─────────────────────────────────────────────
# publishedAt=r86400  -> Posted in last 24 hours
# experienceLevel=1   -> Entry level
# contractType options: F=Full-time, P=Part-time, I=Internship

LOCATION = "Germany"
PUBLISHED_AT = "r86400"
EXPERIENCE_LEVEL = "1"
CONTRACT_TYPES = ["F", "P", "I"]

# ─────────────────────────────────────────────
#  KEYWORDS
# ─────────────────────────────────────────────

KEYWORDS = [
    "Geoinformationssysteme",
    "Geoinformatik",
    "Geodaten",
    "Geodäsie",
    "Vermessung",
    "Geomatik",
    "Kartografie",
    "Fernerkundung",
    "Stadtplanung",
    "Erdbeobachtung",
    "Raumdaten",
    "GIS",
    "Geovisualisierung",
    "Topografie",
    "Infrastrukturplanung",
    "Trassierung",
    "Standortanalyse",
    "Umweltplanung",
    "Surveying",
    "Geomatics",
    "Cartography",
    "Remote Sensing",
    "Earth Observation",
    "Spatial",
    "Geoanalytics",
    "Geospatial",
    "Mapping",
    "GeoAI",
    "CAD",
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


def build_actor_input(keyword: str, contract_type: str) -> dict:
    return {
        "title": keyword,
        "location": LOCATION,
        "publishedAt": PUBLISHED_AT,
        "rows": MAX_RESULTS_PER_JOB_TYPE,
        "experienceLevel": EXPERIENCE_LEVEL,
        "contractType": contract_type,
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"],
        },
    }


def run_actor(payload: dict) -> list[dict]:
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    params = {
        "timeout": 120,
        "memory": 512,
        "maxItems": MAX_RESULTS_PER_JOB_TYPE,
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
            f"that your account can run {ACTOR_ID}, and that the actor/proxy "
            f"subscription is active. Apify said: {message}"
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


def fetch_jobs_for_keyword(keyword: str) -> list[dict]:
    """
    Calls the Apify LinkedIn Jobs Scraper actor synchronously
    and returns a list of job dicts for the given keyword.
    """
    jobs = []
    try:
        for contract_type in CONTRACT_TYPES:
            payload = build_actor_input(keyword, contract_type)
            jobs.extend(run_actor(payload))
        return jobs
    except requests.exceptions.Timeout:
        print(f"  ⚠ Timeout for keyword '{keyword}' — skipping.")
        return []
    except ApifyConfigurationError:
        raise
    except requests.exceptions.HTTPError as e:
        response = e.response
        details = f" {apify_error_message(response)}" if response is not None else ""
        print(f"  ⚠ HTTP error for keyword '{keyword}': {e}.{details} — skipping.")
        return []
    except Exception as e:
        print(f"  ⚠ Unexpected error for keyword '{keyword}': {e} — skipping.")
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
#  EXCEL EXPORT
# ─────────────────────────────────────────────

HEADER = [
    "#", "Job Title", "Company", "Location",
    "Job Type", "Posted", "Experience Level",
    "Keywords Matched", "LinkedIn URL"
]

# Colour palette matching your thesis :)
COLOR_HEADER_BG  = "102C53"   # navy
COLOR_HEADER_FG  = "FFFFFF"   # white
COLOR_ROW_ODD    = "CADCFC"   # ice blue
COLOR_ROW_EVEN   = "FFFFFF"   # white
COLOR_ACCENT     = "C9A84C"   # gold (used for URL cells)

THIN = Side(style="thin", color="AAAAAA")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def style_header_cell(cell):
    cell.font      = Font(bold=True, color=COLOR_HEADER_FG, name="Calibri", size=11)
    cell.fill      = PatternFill("solid", fgColor=COLOR_HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border    = BORDER


def style_data_cell(cell, row_idx: int, is_url: bool = False):
    bg = COLOR_ROW_ODD if row_idx % 2 == 1 else COLOR_ROW_EVEN
    cell.fill      = PatternFill("solid", fgColor=bg)
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    cell.border    = BORDER
    if is_url:
        cell.font  = Font(color=COLOR_ACCENT, name="Calibri", size=10, underline="single")
    else:
        cell.font  = Font(name="Calibri", size=10)


def export_to_excel(jobs: list[dict], zero_keywords: list[str], filename: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Jobs {datetime.now().strftime('%Y-%m-%d')}"

    # ── Header row ──────────────────────────────
    ws.append(HEADER)
    for col_idx, _ in enumerate(HEADER, start=1):
        style_header_cell(ws.cell(row=1, column=col_idx))
    ws.row_dimensions[1].height = 30

    # ── Data rows ───────────────────────────────
    for i, job in enumerate(jobs, start=1):
        keywords_str = ", ".join(job.get("keywords_matched", []))
        url          = get_job_url(job)

        row_data = [
            i,
            safe(job, "title", "jobTitle", "name"),
            safe(job, "company", "companyName", "organization"),
            safe(job, "location", "jobLocation", "place"),
            get_job_type(job),
            get_posted(job),
            get_experience(job),
            keywords_str,
            url,
        ]
        ws.append(row_data)

        excel_row = i + 1  # +1 because row 1 is header
        for col_idx, value in enumerate(row_data, start=1):
            cell    = ws.cell(row=excel_row, column=col_idx)
            is_url  = (col_idx == len(HEADER))  # last column
            style_data_cell(cell, i, is_url=is_url)

            # Make URL a clickable hyperlink
            if is_url and value != "N/A":
                cell.hyperlink = value
                cell.value     = "Open →"

        ws.row_dimensions[excel_row].height = 45

    # ── Column widths ────────────────────────────
    col_widths = [5, 40, 28, 22, 16, 18, 18, 40, 12]
    for col_idx, width in enumerate(col_widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # ── Freeze header row ────────────────────────
    ws.freeze_panes = "A2"

    # ── Auto-filter ──────────────────────────────
    ws.auto_filter.ref = ws.dimensions

    # ── Zero-results sheet ───────────────────────
    if zero_keywords:
        ws2 = wb.create_sheet("No Results")
        ws2.append(["Keyword", "Status"])
        for kw in zero_keywords:
            ws2.append([kw, "0 results found"])

    # ── Summary sheet ────────────────────────────
    ws3 = wb.create_sheet("Summary")
    ws3.append(["Run date",        datetime.now().strftime("%Y-%m-%d %H:%M")])
    ws3.append(["Keywords searched", len(KEYWORDS)])
    ws3.append(["Unique jobs found",  len(jobs)])
    ws3.append(["Keywords with 0 results", len(zero_keywords)])

    wb.save(filename)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    if not APIFY_API_TOKEN or APIFY_API_TOKEN == TOKEN_PLACEHOLDER:
        print(f"❌ Please set {TOKEN_ENV_VAR} in {TOKEN_FILE.name} or as an environment variable.")
        print(f"   Add this line to {TOKEN_FILE.name}:")
        print(f"   {TOKEN_ENV_VAR}={TOKEN_PLACEHOLDER}")
        return

    print("=" * 60)
    print(f"  LinkedIn Job Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Keywords: {len(KEYWORDS)}  |  Job types: {', '.join(CONTRACT_TYPES)}")
    print(f"  Max results per keyword/job type: {MAX_RESULTS_PER_JOB_TYPE}")
    print("=" * 60)

    all_results:   dict[str, list] = {}
    zero_keywords: list[str]       = []

    for idx, keyword in enumerate(KEYWORDS, start=1):
        print(f"\n[{idx:02d}/{len(KEYWORDS)}] Searching: '{keyword}' ...", end=" ", flush=True)

        try:
            jobs = fetch_jobs_for_keyword(keyword)
        except ApifyConfigurationError as e:
            print(f"\n❌ {e}")
            print("   Fix the Apify token/subscription, then run the script again.")
            return

        all_results[keyword] = jobs

        if jobs:
            print(f"✓ {len(jobs)} job(s) found")
        else:
            print(f"— 0 results")
            zero_keywords.append(keyword)

        if idx < len(KEYWORDS):
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
    print(f"Exporting to '{OUTPUT_FILE}' ...")
    export_to_excel(unique_jobs, zero_keywords, OUTPUT_FILE)

    # ── Summary ──────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Searched {len(KEYWORDS)} keywords → Found {len(unique_jobs)} unique job postings.")
    if zero_keywords:
        print(f"  Keywords with 0 results ({len(zero_keywords)}):")
        for kw in zero_keywords:
            print(f"    • {kw}")
    print(f"  Output saved to: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
