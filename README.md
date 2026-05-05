# JobScraper

JobScraper scrapes recent geo/GIS job postings from Apify-powered LinkedIn and
Indeed actors, deduplicates them across keywords, filters unwanted titles and
high-applicant jobs, and exports each run to Excel, Google Sheets, or both. It
can also evaluate saved jobs with the OpenAI API and write AI fit results back
to the same worksheet or Google Sheet tab.

The repository is intentionally pragmatic: the application code lives in a
standard `src/` package, editable search settings live in `configs/`, and the
historical root commands remain as compatibility wrappers.

## Project Structure

```text
JobScraper/
├── configs/
│   ├── filters.json
│   └── keywords.txt
├── cv/
│   └── master_cv.tex
├── prompts/
│   └── master_prompt.txt
├── scripts/
│   ├── evaluate_jobs.py
│   ├── run_pipeline.py
│   └── scrape_jobs.py
├── src/
│   └── jobscraper/
│       ├── config_files.py
│       ├── env.py
│       ├── google_sheets.py
│       ├── paths.py
│       ├── evaluator/
│       │   ├── cli.py
│       │   ├── models.py
│       │   ├── openai_client.py
│       │   ├── parsing.py
│       │   └── storage.py
│       ├── pipeline/
│       │   └── cli.py
│       └── scraper/
│           ├── cli.py
│           ├── export_excel.py
│           ├── export_google_sheets.py
│           ├── export_rows.py
│           ├── filters.py
│           ├── normalize.py
│           ├── search.py
│           └── settings.py
├── tests/
├── linkedin_job_scraper.py
├── job_fit_evaluator.py
├── run_job_pipeline.py
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## What It Does

1. Builds one Apify search per keyword and selected source.
2. Runs searches concurrently.
3. Normalizes fields from LinkedIn and Indeed actor outputs.
4. Deduplicates by source and job ID, with a title/company/location fallback.
5. Tracks every keyword that matched each job.
6. Removes excluded titles such as `Werkstudent` or `Working Student`.
7. Removes jobs above the configured applicant limit.
8. Writes a timestamped tab to `jobs.xlsx`, Google Sheets, or both.
9. Optionally evaluates jobs with OpenAI and appends AI result columns.

## Setup

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

For local development tools:

```bash
python -m pip install -r requirements-dev.txt
```

## Required Secrets

Set secrets in real environment variables or in `.env`. Real environment
variables take precedence.

```bash
APIFY_API_TOKEN=apify_api_XXXXXXXXXXXX
OPENAI_API_KEY=sk-...
```

Google Sheets output also needs `google_client_secret.json` for first local
OAuth login. After login, `google_token.json` and `google_spreadsheet_id.txt`
are generated locally and ignored by Git.

## Configuration

Edit these files for normal scraper behavior:

| Path | Purpose |
|---|---|
| `configs/keywords.txt` | Search keywords, one per line. Blank lines and comments are ignored. |
| `configs/filters.json` | LinkedIn search filters, title exclusions, applicant limit, and spreadsheet dropdown values. |
| `.env` | Secrets, runtime overrides, output mode, sources, and concurrency settings. |
| `prompts/master_prompt.txt` | Master prompt used by the evaluator. |
| `cv/master_cv.tex` | Master LaTeX CV included in evaluator prompts. |

Common `.env` settings:

| Name | Default | Description |
|---|---:|---|
| `JOBSCRAPER_OUTPUT_MODE` | `excel` | `excel`, `google_sheets`, or `both` |
| `JOBSCRAPER_SOURCES` | `linkedin` | `linkedin`, `indeed`, or `both` |
| `JOBSCRAPER_SEARCH_CONCURRENCY` | `15` | Number of keyword searches started in parallel |
| `JOBSCRAPER_MAX_RESULTS_PER_SEARCH` | `500` | LinkedIn result cap per keyword |
| `JOBSCRAPER_MAX_APPLICANTS` | `filters.json` value | Optional env override for applicant filtering |
| `JOBSCRAPER_TIMEZONE` | `Europe/Rome` | Log and output tab timezone |
| `JOBSCRAPER_POSTED_TIMEZONE` | `Europe/Berlin` | `Posted` column timezone |
| `GOOGLE_SPREADSHEET_ID` | blank | Optional existing Google Sheet ID |

## Usage

The original commands still work:

```bash
python linkedin_job_scraper.py
python job_fit_evaluator.py --source excel --excel-file jobs.xlsx --sheet latest
python run_job_pipeline.py --limit 3
```

The same commands are also available from `scripts/`:

```bash
python scripts/scrape_jobs.py
python scripts/evaluate_jobs.py --source google_sheets --sheet latest
python scripts/run_pipeline.py --sources both --limit 3
```

If the project is installed as a package, console entry points are available:

```bash
jobscraper-scrape
jobscraper-evaluate --source excel --excel-file jobs.xlsx --sheet latest
jobscraper-pipeline --sources linkedin --limit 3
```

## Output Columns

Scraper exports keep the existing output schema:

| Column | Description |
|---|---|
| `Application Status` | Empty Excel cell or Google Sheets dropdown |
| `App` | Source app, such as LinkedIn or Indeed |
| `Job Title` | Position name |
| `Company` | Employer name |
| `Location` | City or region |
| `Job Type` | Source employment type text |
| `Job Description` | Plain-text job description when returned by the source; removed after evaluator runs |
| `Posted` | Date/time in `JOBSCRAPER_POSTED_TIMEZONE` |
| `Applicants` | Applicant count text if visible |
| `Keywords Matched` | All keywords that returned the job |
| `Job URL` | Clickable job posting link |
| `Apply URL` | Clickable external application link when available |

Evaluator output columns are appended only when missing. After evaluation, the
evaluator keeps only:

`AI Verdict`, `AI Fit Score`, and `AI Tailored CV`.

It also deletes legacy AI metadata columns such as `AI Category`, `AI Reason`,
`AI Raw Verdict`, `AI Evaluated At`, `AI Model`, and `AI Error`, plus the job
description/details column used to build the prompt.

## Development

Run the test and quality checks:

```bash
python -m pytest
python -m black .
python -m ruff check .
```

The main structural decisions are:

- `src/jobscraper/scraper/` separates Apify search execution, normalization,
  filtering, row construction, and exporters.
- `src/jobscraper/evaluator/` separates row parsing, OpenAI calls, result
  models, and storage adapters.
- `src/jobscraper/env.py`, `config_files.py`, and `google_sheets.py` contain
  reusable infrastructure shared by scraper, evaluator, and pipeline commands.
- Root scripts are compatibility shims so existing manual runs, cron jobs, and
  GitHub Actions commands do not need to change.

## Troubleshooting

| Problem | What to Check |
|---|---|
| `Please set APIFY_API_TOKEN` | `.env` exists and the token is not the placeholder |
| Apify `401` or `403` | Token validity, actor access, billing, or trial status |
| Many timeouts | Lower `JOBSCRAPER_SEARCH_CONCURRENCY` or increase Apify timeout settings |
| Google credential error | `google_client_secret.json` exists locally or GitHub has `GOOGLE_TOKEN_JSON` |
| Spreadsheet not found | Check `GOOGLE_SPREADSHEET_ID` or delete `google_spreadsheet_id.txt` to create a new spreadsheet |
| Missing config file | Check `configs/keywords.txt` and `configs/filters.json` |
