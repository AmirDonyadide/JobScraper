# JobFinder

JobFinder collects recent job postings from Apify-powered LinkedIn and Indeed scrapers, removes duplicates and unwanted results, exports the jobs to Google Sheets or Excel, and evaluates each job with OpenAI using your private prompt and CV.

The simplest production workflow is the GitHub Actions workflow. After setup, you can run the whole job search online from GitHub without keeping your laptop open.

## What JobFinder Does

1. Reads your private keywords from `configs/keywords.txt` or GitHub secrets.
2. Scrapes matching jobs from LinkedIn, Indeed, or both through Apify.
3. Deduplicates jobs across keywords and previous Google Sheet run tabs.
4. Removes excluded titles and jobs above the applicant limit.
5. Writes a new dated tab to Google Sheets.
6. Evaluates every unevaluated job with OpenAI.
7. Keeps only the final AI columns:
   - `AI Verdict`
   - `AI Fit Score`
   - `AI Unsuitable Reasons`
   - `AI Tailored CV`
8. Removes the long job-description/details column after evaluation.

## Recommended Use

For normal use, run JobFinder online with GitHub Actions.

For local setup or testing, run:

```bash
python run_job_pipeline.py
```

## Project Structure

```text
JobFinder/
├── configs/
│   ├── filters.json
│   ├── keywords.example.txt
│   └── keywords.txt              # private, ignored by Git
├── cv/
│   ├── master_cv.example.tex
│   └── master_cv.tex             # private, ignored by Git
├── prompts/
│   ├── master_prompt.example.txt
│   └── master_prompt.txt         # private, ignored by Git
├── src/jobfinder/
│   ├── scraper/                  # scraping, filtering, exporting
│   ├── evaluator/                # OpenAI evaluation and sheet updates
│   └── pipeline/                 # full workflow entry point
├── .github/workflows/jobs.yml    # online GitHub Actions workflow
├── run_job_pipeline.py
├── linkedin_job_scraper.py
├── job_fit_evaluator.py
├── requirements.txt
└── README.md
```

The Python package is named `jobfinder` internally. The scraper component remains under `jobfinder.scraper`.

## Local Installation

Use Python 3.11 or newer.

With Conda:

```bash
cd /Users/amir/Documents/GitHub/JobFinder
conda create -n jobfinder python=3.11 -y
conda activate jobfinder
python -m pip install -r requirements.txt
cp .env.example .env
```

Or with `venv`:

```bash
cd /Users/amir/Documents/GitHub/JobFinder
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

## Private Local Files

Your real keywords, prompt, and CV are private. They are ignored by Git.

Create them from the examples:

```bash
cp configs/keywords.example.txt configs/keywords.txt
cp prompts/master_prompt.example.txt prompts/master_prompt.txt
cp cv/master_cv.example.tex cv/master_cv.tex
```

Then edit:

- `configs/keywords.txt`: one search keyword per line
- `configs/filters.json`: search settings, title/company exclusions, and applicant cap
- `prompts/master_prompt.txt`: your evaluator instructions
- `cv/master_cv.tex`: your private LaTeX CV

Do not commit these private files.

Your Google service-account key is private too. For local runs, keep it at the
repository root as `google_service_account.json`.

## Local `.env` Settings

Open `.env` and set at least:

```bash
APIFY_API_TOKEN=apify_api_...
OPENAI_API_KEY=sk-...
```

Common settings:

| Setting | Default | Description |
|---|---:|---|
| `JOBSCRAPER_SOURCES` | `linkedin` | Use `linkedin`, `indeed`, or `both`. |
| `JOBSCRAPER_OUTPUT_MODE` | `excel` | Use `excel`, `google_sheets`, or `both`. The full pipeline forces Google Sheets. |
| `JOBFINDER_PIPELINE_MODE` | `scrape_and_evaluate` | For `run_job_pipeline.py`, use `scrape_only` or `scrape_and_evaluate`. |
| `JOBSCRAPER_SEARCH_CONCURRENCY` | `15` | Number of Apify searches run at the same time. |
| `JOBSCRAPER_APIFY_MEMORY_LIMIT_MB` | `0` | Optional total Apify memory cap used to reduce search concurrency; `0` disables the cap. |
| `JOBSCRAPER_APIFY_BATCH_SIZE` | `1` | Optional LinkedIn search batch size. Keep `1` unless actor results expose source search URLs for attribution. |
| `JOBSCRAPER_MAX_RESULTS_PER_SEARCH` | `500` | Maximum LinkedIn results per keyword. |
| `JOBSCRAPER_SEARCH_WINDOW_BUFFER_SECONDS` | `3600` | Extra search-window padding before exact posted-time filtering, to avoid missing jobs while the run is starting. |
| `APIFY_RUN_TIMEOUT_SECONDS` | `3600` | Maximum Apify actor runtime per keyword search. |
| `APIFY_CLIENT_TIMEOUT_SECONDS` | `120` | HTTP timeout for individual Apify API calls while starting, polling, and reading results. |
| `APIFY_TRANSIENT_ERROR_RETRIES` | `5` | Number of retry attempts for temporary Apify API/run errors before failing the run. |
| `APIFY_RETRY_DELAY_SECONDS` | `30` | Base delay before retrying a temporary Apify issue; later retries back off from this value. |
| `JOBSCRAPER_TIMEZONE` | `Europe/Berlin` | Timezone for terminal logs and new Excel/Google Sheets tab names. |
| `JOBSCRAPER_POSTED_TIMEZONE` | `Europe/Berlin` | Timezone for the `Posted` column. |
| `JOB_EVAL_OPENAI_MODEL` | `gpt-5-mini` | OpenAI model used for evaluation. |
| `JOB_EVAL_CONCURRENCY` | `8` | Number of OpenAI job evaluations run at the same time. |
| `JOB_EVAL_BATCH_SIZE` | `40` | Number of jobs processed per evaluator batch. |
| `JOB_EVAL_LARGE_QUEUE_THRESHOLD` | `200` | Enable request pacing when more than this many rows are queued for OpenAI. |
| `JOB_EVAL_LARGE_QUEUE_SLEEP_MS` | `2000` | Milliseconds to wait between OpenAI request starts for large queues. |
| `JOB_EVAL_SAVE_BATCH_SIZE` | `1` | Number of completed evaluations to save per write. `1` preserves row-by-row crash recovery. |

## Google Sheets Setup

Use a Google service account for Google Sheets access. This is the preferred setup
for GitHub Actions because it does not rely on a browser-based OAuth refresh token.

1. Open Google Cloud Console.
2. Enable the Google Sheets API.
3. Go to `IAM & Admin -> Service Accounts`.
4. Create a service account.
5. Create and download a JSON key for that service account.
6. Copy the `client_email` value from the JSON key.
7. Open your target Google Sheet and share it with that email as **Editor**.

For local runs, save the downloaded JSON key in this repository as:

```text
google_service_account.json
```

If Google downloaded the key with a project-specific name such as
`jobfinder-495809-abc123.json`, rename it:

```bash
mv ~/Downloads/jobfinder-*.json google_service_account.json
```

Then set `GOOGLE_SPREADSHEET_ID` in `.env`, or save the spreadsheet ID in:

```text
google_spreadsheet_id.txt
```

Do not commit these files. They are ignored by Git.

Local OAuth with `google_client_secret.json` and `google_token.json` is still
supported as a fallback, but service-account auth is simpler for scheduled runs.

If you expose a service-account JSON key, delete that key in Google Cloud and
create a fresh one before using it in GitHub.

## Run Online With GitHub Actions

The online workflow is defined in:

```text
.github/workflows/jobs.yml
```

It runs the full pipeline on GitHub:

1. Checks out the repository.
2. Installs Python dependencies.
3. Writes your private keywords, prompt, and CV from GitHub secrets.
4. Writes your Google service-account key from GitHub secrets.
5. Scrapes jobs into Google Sheets.
6. Evaluates every unevaluated row with OpenAI.

### 1. Push The Repository To GitHub

Make sure your local repository points to the GitHub repo:

```bash
git remote -v
```

For this repository, it should look like:

```text
git@github.com:AmirDonyadide/JobFinder.git
```

Push your latest committed code:

```bash
git push
```

### 2. Create Or Choose A Google Sheet

Open the Google Sheet you want JobFinder to write to.

Copy only the spreadsheet ID from the URL.

Example URL:

```text
https://docs.google.com/spreadsheets/d/1abcDEFghiJKLmnop123/edit
```

The spreadsheet ID is:

```text
1abcDEFghiJKLmnop123
```

This value goes into the GitHub secret `GOOGLE_SPREADSHEET_ID`.

### 3. Create The Service Account Secret

Copy the full service-account JSON key into the GitHub secret:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Make sure the target spreadsheet is shared with the service-account email as
**Editor**. The email is the `client_email` field inside the JSON key.

### 4. Add GitHub Repository Secrets

In GitHub:

```text
Repository -> Settings -> Secrets and variables -> Actions -> New repository secret
```

Add these secrets exactly:

| Secret name | What to paste |
|---|---|
| `APIFY_API_TOKEN` | Your Apify API token, for example `apify_api_...`. |
| `OPENAI_API_KEY` | Your OpenAI API key, for example `sk-...` or `sk-proj-...`. |
| `GOOGLE_SPREADSHEET_ID` | The spreadsheet ID from the Google Sheet URL. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | The full contents of the service-account JSON key. |
| `JOB_KEYWORDS_TEXT` | The full contents of `configs/keywords.txt`. |
| `MASTER_PROMPT_TEXT` | The full contents of `prompts/master_prompt.txt`. |
| `MASTER_CV_TEX` | The full contents of `cv/master_cv.tex`. |

On macOS, you can copy each private file like this:

```bash
cat configs/keywords.txt | pbcopy
cat prompts/master_prompt.txt | pbcopy
cat cv/master_cv.tex | pbcopy
cat google_service_account.json | pbcopy
```

Paste each copied value into the matching GitHub secret.

### 5. Run The Workflow Manually

In GitHub:

```text
Repository -> Actions -> JobFinder Pipeline -> Run workflow
```

Choose the source:

- `linkedin`
- `indeed`
- `both`

Choose the pipeline mode:

- `scrape_and_evaluate`: scrape jobs, then evaluate them with OpenAI
- `scrape_only`: create the new scraped Google Sheet tab without running OpenAI evaluation

Click **Run workflow**.

The workflow will create a new dated tab in your Google Sheet. In `scrape_and_evaluate` mode, it then evaluates the jobs.

### 6. Scheduled Runs

The workflow also runs automatically once per day during the 07:00 UTC hour.

The schedule is in `.github/workflows/jobs.yml`:

```yaml
schedule:
  - cron: "17 7 * * *"
```

GitHub may delay scheduled workflows slightly. That is normal.

### 7. Speed Settings In GitHub Actions

The current workflow uses:

```yaml
APIFY_RUN_TIMEOUT_SECONDS: "3600"
APIFY_CLIENT_TIMEOUT_SECONDS: "120"
APIFY_TRANSIENT_ERROR_RETRIES: "5"
APIFY_RETRY_DELAY_SECONDS: "30"
JOB_EVAL_CONCURRENCY: "8"
JOB_EVAL_BATCH_SIZE: "40"
JOB_EVAL_LARGE_QUEUE_THRESHOLD: "200"
JOB_EVAL_LARGE_QUEUE_SLEEP_MS: "2000"
```

This keeps 15 Apify keyword searches running in parallel, with 512 MB assigned to each actor run. That uses up to 7680 MB of Apify memory at once, which fits inside an 8 GB Apify limit. Each keyword search gets up to 60 minutes of actor runtime, so keywords with many matching positions have much more time before that keyword is marked as timed out. Temporary Apify API issues such as 502/503/504 responses, rate limits, HTTP timeouts, and short memory-limit pressure are retried before the workflow fails. The evaluator allows up to 8 OpenAI requests at the same time, with jobs grouped locally in batches of 40.

When more than 200 rows are queued, the evaluator also spaces OpenAI request starts by 2000 ms. Each row is saved back to the same sheet immediately after it is evaluated, so a later failure keeps the completed rows.

If you see OpenAI rate-limit or retry warnings, reduce them in `.github/workflows/jobs.yml`:

```yaml
JOB_EVAL_CONCURRENCY: "5"
JOB_EVAL_BATCH_SIZE: "20"
```

## Run Windows And Duplicates

When Google Sheets output is enabled, JobFinder reads the existing timestamped tabs before scraping. The newest previous tab name is treated as the previous exact run time in `JOBSCRAPER_TIMEZONE`, which defaults to `Europe/Berlin`.

LinkedIn searches then use a dynamic posted window from that previous run to the current run, plus `JOBSCRAPER_SEARCH_WINDOW_BUFFER_SECONDS` as safety padding. After scraping, JobFinder filters rows back to the exact previous-run/current-run posted interval, then removes jobs already present in older tabs before the evaluator runs.

Final scraper filters in `configs/filters.json` also remove jobs whose company names contain any `excluded_company_terms`, ignoring case and punctuation.

## Running Locally

Full Google Sheets pipeline:

```bash
python run_job_pipeline.py
```

If you install the package locally with `python -m pip install -e .`, the
packaged console-script equivalent is:

```bash
jobfinder-pipeline
```

Scrape to Google Sheets without evaluation:

```bash
python run_job_pipeline.py --mode scrape_only
```

Scrape only:

```bash
python linkedin_job_scraper.py
```

Evaluate the latest Google Sheet tab:

```bash
python job_fit_evaluator.py --source google_sheets --sheet latest
```

Evaluate the latest local Excel worksheet:

```bash
python job_fit_evaluator.py --source excel --sheet latest
```

## Development Checks

Before changing behavior, run the same checks used by CI:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m compileall src tests scripts run_job_pipeline.py linkedin_job_scraper.py job_fit_evaluator.py job_scraper_config.py
python -m json.tool configs/filters.json
python -m pytest
```

## Output Columns

Scraper output columns before evaluation:

| Column | Description |
|---|---|
| `Application Status` | Empty status cell or Google Sheets dropdown. |
| `App` | Source app, such as LinkedIn or Indeed. |
| `Job Title` | Position name. |
| `Company` | Employer name. |
| `Location` | City or region. |
| `Job Type` | Employment type text from the source. |
| `Job Description` | Used for AI evaluation, then removed after evaluation. |
| `Posted` | Posting date/time in `JOBSCRAPER_POSTED_TIMEZONE`. |
| `Applicants` | Applicant count when available. |
| `Keywords Matched` | Keywords that returned the job. |
| `Job URL` | Link to the job posting. |
| `Apply URL` | External application link when available. |
| `AI Verdict` | Empty until evaluation fills the fit verdict. |
| `AI Fit Score` | Empty until evaluation fills the fit percentage. |
| `AI Unsuitable Reasons` | Empty until evaluation explains rows marked `Not Suitable`. |
| `AI Tailored CV` | Empty until evaluation writes suitable-role CV content. |

Final AI columns after evaluation:

- `AI Verdict`
- `AI Fit Score`
- `AI Unsuitable Reasons`
- `AI Tailored CV`

## Troubleshooting GitHub Actions

| Problem | What to check |
|---|---|
| `Missing repository secret ...` | Add the named secret under GitHub repo settings. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` error | Copy the full service-account JSON key, not an OAuth client JSON. |
| Google authentication fails | Confirm the spreadsheet is shared with the service-account `client_email` as Editor. |
| Spreadsheet not found | Check that `GOOGLE_SPREADSHEET_ID` is only the ID, not the full URL. |
| Workflow cannot push or fetch repo | Check GitHub authentication and repository permissions. |
| OpenAI rate-limit retries | Lower `JOB_EVAL_CONCURRENCY` and `JOB_EVAL_BATCH_SIZE`. |
| No jobs found | Check keywords, filters, Apify actor status, source selection, and posted-date filters. |
| Private keywords/prompt/CV missing | Confirm `JOB_KEYWORDS_TEXT`, `MASTER_PROMPT_TEXT`, and `MASTER_CV_TEX` secrets are set. |
| Workflow does not run on schedule | Check that GitHub Actions are enabled for the repository. Scheduled workflows can be delayed by GitHub. |

## Security Notes

Never commit these files:

```text
.env
google_client_secret.json
google_service_account*.json
*service_account*.json
*service-account*.json
jobfinder-*.json
google_token.json
google_spreadsheet_id.txt
configs/keywords.txt
prompts/master_prompt.txt
cv/master_cv.tex
```

Use GitHub secrets for all private online values.
