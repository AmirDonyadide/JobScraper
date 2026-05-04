# JobScraper

Scrape recent geo/GIS job postings from Apify-powered LinkedIn and Indeed actors, deduplicate them across keywords, filter unwanted titles, and export each run to Excel, Google Sheets, or both.

The project is intentionally small: one Python script, one dependency file, one example environment file, and an optional GitHub Actions workflow for scheduled runs.

## What It Does

1. Builds one search per keyword and selected source.
2. Runs Apify actors in parallel.
3. Normalizes fields from LinkedIn and Indeed.
4. Deduplicates jobs by source and job ID, with a title/company/location fallback.
5. Tracks every keyword that matched each job.
6. Removes excluded job titles such as `Werkstudent`.
7. Saves a new timestamped tab in `jobs.xlsx`, Google Sheets, or both.

Default search behavior:

| Setting | Default |
|---|---|
| Sources | LinkedIn only |
| Location | Germany |
| Posted window | Last 24 hours |
| LinkedIn experience levels | Internship, Entry level |
| LinkedIn job types | Full-time, Part-time, Internship |
| Excluded titles | `Werkstudent` |

## Repository Map

| Path | Purpose |
|---|---|
| `linkedin_job_scraper.py` | Main scraper and exporters |
| `requirements.txt` | Python dependencies |
| `requirements-dev.txt` | Runtime dependencies plus local code-check tools |
| `.env.example` | Copy this to `.env` for local settings |
| `CONTRIBUTING.md` | Maintainer checklist for safe changes |
| `.github/workflows/jobs.yml` | Optional daily/manual GitHub Actions run |
| `jobs.xlsx` | Local output file, generated and ignored by Git |
| `google_token.json` | Local Google OAuth token, generated and ignored by Git |
| `google_spreadsheet_id.txt` | Google Sheet ID cache, generated and ignored by Git |

## Quick Start

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Open `.env`, replace the Apify placeholder, then run:

```bash
python linkedin_job_scraper.py
```

With the default settings, the scraper writes a new sheet tab to `jobs.xlsx`.

## Required Setup

### Apify Token

Create an Apify account, copy your personal API token, and put it in `.env`:

```bash
APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
```

The script reads real environment variables first and then falls back to `.env`.

### Output Mode

Choose one:

```bash
JOBSCRAPER_OUTPUT_MODE=excel
JOBSCRAPER_OUTPUT_MODE=google_sheets
JOBSCRAPER_OUTPUT_MODE=both
```

`excel` needs only local dependencies. `google_sheets` and `both` need Google setup.

## Google Sheets Setup

Use this only when `JOBSCRAPER_OUTPUT_MODE` is `google_sheets` or `both`.

1. In Google Cloud, enable the Google Sheets API.
2. Create an OAuth client for a desktop app.
3. Download the client JSON.
4. Save it in this repository as `google_client_secret.json`.
5. Run the scraper locally once.
6. Complete the browser-based Google login.

After the first approved run, the script creates `google_token.json`. Future local runs reuse it.

The first Google Sheets export creates a spreadsheet named `jobs` and writes its ID to `google_spreadsheet_id.txt`. Future runs add new tabs to the same spreadsheet. You can also set `GOOGLE_SPREADSHEET_ID` in `.env` to force a specific spreadsheet.

## Configuration

Prefer `.env` for settings that are likely to change. Edit constants in `linkedin_job_scraper.py` only for deeper changes such as keywords, LinkedIn filters, output filenames, or title exclusion rules.

### Common `.env` Settings

| Name | Default | Description |
|---|---:|---|
| `APIFY_API_TOKEN` | required | Apify API token |
| `JOBSCRAPER_OUTPUT_MODE` | `excel` | `excel`, `google_sheets`, or `both` |
| `JOBSCRAPER_SOURCES` | `linkedin` | `linkedin`, `indeed`, or `both` |
| `JOBSCRAPER_SEARCH_CONCURRENCY` | `15` | Number of keyword searches started in parallel |
| `JOBSCRAPER_MAX_RESULTS_PER_SEARCH` | `500` | LinkedIn result cap per keyword |
| `APIFY_RUN_MEMORY_MB` | `512` | Memory assigned to each Apify actor run |
| `APIFY_RUN_TIMEOUT_SECONDS` | `300` | Apify actor timeout per search |
| `APIFY_CLIENT_TIMEOUT_SECONDS` | `360` | Local HTTP timeout for Apify API calls |
| `JOBSCRAPER_DELAY_BETWEEN_REQUESTS` | `0` | Delay between starting keyword searches |
| `JOBSCRAPER_SCRAPE_COMPANY_DETAILS` | `false` | Ask LinkedIn actor for extra company details |
| `JOBSCRAPER_USE_INCOGNITO_MODE` | `true` | LinkedIn actor incognito mode |
| `JOBSCRAPER_SPLIT_BY_LOCATION` | `false` | LinkedIn actor split-by-location mode |
| `JOBSCRAPER_TIMEZONE` | `Europe/Rome` | Terminal logs and output tab names |
| `JOBSCRAPER_POSTED_TIMEZONE` | `Europe/Berlin` | `Posted` column timezone |
| `GOOGLE_SPREADSHEET_ID` | blank | Optional existing Google Sheet ID |

### Indeed `.env` Settings

These apply when `JOBSCRAPER_SOURCES` is `indeed` or `both`.

| Name | Default | Description |
|---|---:|---|
| `INDEED_COUNTRY` | `DE` | Indeed country code |
| `INDEED_LOCATION` | `Germany` | Indeed location query |
| `INDEED_MAX_RESULTS_PER_SEARCH` | `500` | Indeed result cap per keyword |
| `INDEED_MAX_CONCURRENCY` | `5` | Actor-level Indeed concurrency |
| `INDEED_SAVE_ONLY_UNIQUE_ITEMS` | `true` | Ask actor to keep unique results only |

### Script Constants

Edit these directly in `linkedin_job_scraper.py` when you want to change the actual search strategy:

| Constant | Purpose |
|---|---|
| `KEYWORDS` | Search phrases |
| `LOCATION` / `GEO_ID` | LinkedIn location |
| `PUBLISHED_AT` | LinkedIn posted-time filter |
| `EXPERIENCE_LEVELS` | LinkedIn experience filters |
| `CONTRACT_TYPES` | LinkedIn job type filters |
| `EXCLUDED_TITLE_TERMS` | Final case-insensitive title filters |
| `EXCEL_OUTPUT_FILE` | Local workbook path |
| `SPREADSHEET_TITLE` | Google spreadsheet title for first creation |

## Running

### One-Off Local Run

```bash
python linkedin_job_scraper.py
```

### Run Both Sources Once

```bash
JOBSCRAPER_SOURCES=both python linkedin_job_scraper.py
```

### Local Cron Example

```bash
crontab -e
```

Run daily at 08:00:

```cron
0 8 * * * cd /path/to/JobScraper && /path/to/JobScraper/.venv/bin/python linkedin_job_scraper.py
```

## GitHub Actions

The workflow in `.github/workflows/jobs.yml` can run manually or once daily during the 07:00 UTC hour. It exports to Google Sheets.

Required repository secrets:

| Secret | Purpose |
|---|---|
| `APIFY_API_TOKEN` | Apify token |
| `GOOGLE_TOKEN_JSON` | Contents of a locally generated `google_token.json` |
| `GOOGLE_SPREADSHEET_ID` | Target Google spreadsheet ID |

Recommended setup:

1. Configure Google Sheets locally first.
2. Confirm a local `google_sheets` run works.
3. Copy the contents of `google_token.json` into the GitHub secret `GOOGLE_TOKEN_JSON`.
4. Copy the target spreadsheet ID into `GOOGLE_SPREADSHEET_ID`.
5. Add `APIFY_API_TOKEN`.
6. Run the workflow manually from the Actions tab.

GitHub-hosted runners are temporary, so they cannot complete browser-based Google OAuth during a workflow run. That is why `GOOGLE_TOKEN_JSON` must come from a local first-time login.

## Output Columns

| Column | Description |
|---|---|
| Application Status | Empty Excel cell or Google Sheets dropdown: applied, rejected, interview, accepted |
| App | Source app, such as LinkedIn or Indeed |
| Job Title | Position name |
| Company | Employer name |
| Location | City or region |
| Job Type | Text from the job source |
| Posted | Date and time in `JOBSCRAPER_POSTED_TIMEZONE` |
| Applicants | Applicant count if visible |
| Keywords Matched | All keywords that returned this job |
| Job URL | Clickable link to the job posting |
| Apply URL | Clickable external application link if available |

## Troubleshooting

| Problem | What to Check |
|---|---|
| `Please set APIFY_API_TOKEN` | `.env` exists and `APIFY_API_TOKEN` is not the placeholder |
| Apify returns `401` or `403` | Token is valid, account can run the actor, billing or trial access is active |
| Many timeouts | Lower `JOBSCRAPER_SEARCH_CONCURRENCY`, increase `APIFY_RUN_TIMEOUT_SECONDS`, or increase `APIFY_CLIENT_TIMEOUT_SECONDS` |
| Google credential error | `google_client_secret.json` exists locally, or GitHub has `GOOGLE_TOKEN_JSON` |
| Spreadsheet not found | Check `GOOGLE_SPREADSHEET_ID` or delete local `google_spreadsheet_id.txt` to create a new `jobs` spreadsheet |
| `tzdata` or timezone error | Install dependencies from `requirements.txt` and use valid IANA timezones |
| Empty or low results | Check source filters, Apify actor health, posted-time window, and title exclusions |

## Notes For Maintainers

- Do not commit `.env`, Google credential files, generated workbooks, or token files.
- Keep `.env.example` in sync when adding environment settings.
- Keep output columns stable unless downstream users are ready for the change.
- The scraper intentionally uses simple local files instead of a database.
- Apify actors may cost money per result or run; review actor pricing before raising limits.
