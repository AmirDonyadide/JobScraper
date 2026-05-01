# LinkedIn Job Scraper

Scrapes LinkedIn jobs daily across geo/GIS-related keywords,
deduplicates results, and exports a clean Excel file per day.

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
pip install requests openpyxl
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

---

## Running

### Manual (one-off run)
```bash
python linkedin_job_scraper.py
```
Output: `jobs_2026-05-01.xlsx` (today's date)

### Mac/Linux: use cron instead (cleaner)
```bash
crontab -e
```
Add this line (runs at 8am daily):
```
0 8 * * * cd /path/to/your/folder && python linkedin_job_scraper.py
```

---

## Output: Excel file columns

| Column | Description |
|---|---|
| # | Row number |
| Job Title | Position name |
| Company | Employer name |
| Location | City / region |
| Job Type | Full-time / Part-time / Internship |
| Posted | When posted |
| Experience Level | Entry level etc. |
| Keywords Matched | All keywords that returned this job |
| LinkedIn URL | Clickable link → opens job posting |

---

## Filters applied (every search)

- Posted: Last 24 hours
- Experience level: Internship OR Entry level
- Job type: Internship OR Part-time OR Full-time
- Location: Germany

---

## Customisation

All settings are at the top of `linkedin_job_scraper.py`:

```python
MAX_RESULTS_PER_SEARCH = 500  # increase for more results (uses more credits)
CONTRACT_TYPES = ["F", "P", "I"]  # full-time, part-time, internship
EXPERIENCE_LEVELS = ["1", "2"]  # internship, entry level
LOCATION = "Germany"
GEO_ID = "101282230"
SCRAPE_COMPANY_DETAILS = True
USE_INCOGNITO_MODE = True
SPLIT_BY_LOCATION = False
SPLIT_COUNTRY = "DE"
DELAY_BETWEEN_REQUESTS = 3
OUTPUT_FILE = f"jobs_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
```

To add/remove keywords, edit the `KEYWORDS` list.
To change location, edit `LOCATION`.

---

## Apify usage

The selected actor is priced per result. The default setup runs each search
with up to 500 jobs each, so check your Apify Console before
increasing limits.
