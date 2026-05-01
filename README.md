# LinkedIn Job Scraper

Scrapes LinkedIn jobs daily across geo/GIS-related keywords,
deduplicates results, and saves them locally as Excel, in Google Sheets,
or both.

Uses Apify actor `curious_coder/linkedin-jobs-scraper`.

---

## Files

| File | Purpose |
|---|---|
| `linkedin_job_scraper.py` | Main scraper — run this manually or via scheduler |

---

## Setup (one time)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Get your Apify token
1. Sign up free at https://apify.com
2. Go to Settings → API & Integrations
3. Copy your Personal API Token

### 3. Set your token

Use a local `.env` file. It is ignored by Git, so your token stays out of GitHub.

```bash
# Mac/Linux
cp .env.example .env
```

Then open `.env` and replace the placeholder:

```bash
APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
```

The script checks the environment variable first, then falls back to `.env`.

You can also override `.env` with an environment variable:

```bash
export APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
```

### 4. Set output mode

At the top of `linkedin_job_scraper.py`, choose:

```python
OUTPUT_MODE = "excel"          # save runs as tabs in local jobs.xlsx
OUTPUT_MODE = "google_sheets"  # save runs as tabs in one Drive spreadsheet named jobs
OUTPUT_MODE = "both"           # do both
```

You can also override it from the terminal:

```bash
export JOBSCRAPER_OUTPUT_MODE=both
```

### 5. Set up Google Sheets access (only for `google_sheets` or `both`)

In Google Cloud, enable the Google Sheets API, create an OAuth client for a
desktop app, download the JSON file, and save it in this folder as:

```text
google_client_secret.json
```

On the first run, the script opens a Google login page. After you approve access,
it saves a local `google_token.json` file so future runs can create Sheets
without asking again. Local Google credential/token/id files are ignored by Git.

The first Google Sheets run creates one spreadsheet named `jobs` and stores its
ID in `google_spreadsheet_id.txt`. Future runs add new tabs to that same
spreadsheet.

If you use cron or another scheduler, run the script manually once first so
`google_token.json` is created.

---

## Running

### Manual (one-off run)
```bash
python linkedin_job_scraper.py
```
Output: `jobs.xlsx`, a Google Sheet URL, or both, depending on `OUTPUT_MODE`.
Each run is saved as a new tab named with the run date and time.

### Mac/Linux: use cron instead (cleaner)
```bash
crontab -e
```
Add this line (runs at 8am daily):
```
0 8 * * * cd /path/to/your/folder && python linkedin_job_scraper.py
```

---

## Output columns

| Column | Description |
|---|---|
| # | Row number |
| Job Title | Position name |
| Company | Employer name |
| Location | City / region |
| Job Type | Full-time / Part-time / Internship |
| Posted | When posted |
| Experience Level | Entry level etc. |
| Job Function | Department or discipline |
| Industries | Job industries |
| Salary | Salary or salary insights if available |
| Applicants | Applicant count if visible |
| Benefits | LinkedIn insight tags |
| Workplace Types | On-site / remote / hybrid info if available |
| Remote Allowed | Whether remote work is allowed |
| Keywords Matched | All keywords that returned this job |
| LinkedIn URL | Clickable link → opens job posting |
| Apply URL | Clickable external application link if available |
| Company Website | Clickable company website if available |
| Company Employees | Company employee count if available |
| Job Poster | Recruiter/poster name if available |
| Job Poster Title | Recruiter/poster title if available |
| Description | Plain-text job description |

---

## Filters applied (every search)

- Posted: Last 24 hours
- Experience level: Internship OR Entry level
- Job type: Internship OR Part-time OR Full-time
- Location: Germany
- Excluded titles: any job title containing `Werkstudent` (case-insensitive)

---

## Customisation

All settings are at the top of `linkedin_job_scraper.py`:

```python
MAX_RESULTS_PER_SEARCH = 500  # increase for more results (uses more credits)
OUTPUT_MODE = "excel"  # choose: excel, google_sheets, both
CONTRACT_TYPES = ["F", "P", "I"]  # full-time, part-time, internship
EXPERIENCE_LEVELS = ["1", "2"]  # internship, entry level
LOCATION = "Germany"
GEO_ID = "101282230"
SCRAPE_COMPANY_DETAILS = True
USE_INCOGNITO_MODE = True
SPLIT_BY_LOCATION = False
SPLIT_COUNTRY = "DE"
EXCLUDED_TITLE_TERMS = ["Werkstudent"]
DELAY_BETWEEN_REQUESTS = 3
EXCEL_OUTPUT_FILE = Path(__file__).with_name("jobs.xlsx")
SPREADSHEET_TITLE = "jobs"
```

To add/remove keywords, edit the `KEYWORDS` list.
To change location, edit `LOCATION`.

---

## Apify usage

The selected actor is priced per result. The default setup runs each search
with up to 500 jobs each, so check your Apify Console before
increasing limits.
