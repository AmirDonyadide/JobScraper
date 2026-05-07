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
├── src/jobscraper/
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

The Python package is still named `jobscraper` internally. The product/repository name is JobFinder.

## Local Installation

Use Python 3.11 or newer.

With Conda:

```bash
cd /Users/amir/Documents/GitHub/JobFinder
conda create -n jobscraper python=3.11 -y
conda activate jobscraper
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
| `JOBSCRAPER_SEARCH_CONCURRENCY` | `15` | Number of Apify searches run at the same time. |
| `JOBSCRAPER_MAX_RESULTS_PER_SEARCH` | `500` | Maximum LinkedIn results per keyword. |
| `JOBSCRAPER_SEARCH_WINDOW_BUFFER_SECONDS` | `3600` | Extra search-window padding before exact posted-time filtering, to avoid missing jobs while the run is starting. |
| `JOBSCRAPER_TIMEZONE` | `Europe/Berlin` | Timezone for terminal logs and new Excel/Google Sheets tab names. |
| `JOBSCRAPER_POSTED_TIMEZONE` | `Europe/Berlin` | Timezone for the `Posted` column. |
| `JOB_EVAL_OPENAI_MODEL` | `gpt-5-mini` | OpenAI model used for evaluation. |
| `JOB_EVAL_CONCURRENCY` | `8` | Number of OpenAI job evaluations run at the same time. |
| `JOB_EVAL_BATCH_SIZE` | `40` | Number of jobs processed per evaluator batch. |
| `JOB_EVAL_LARGE_QUEUE_THRESHOLD` | `200` | Enable request pacing when more than this many rows are queued for OpenAI. |
| `JOB_EVAL_LARGE_QUEUE_SLEEP_MS` | `2000` | Milliseconds to wait between OpenAI request starts for large queues. |

## Google Sheets Setup For Local Use

You only need to do this once if you want to run locally or generate the token for GitHub Actions.

1. Open Google Cloud Console.
2. Enable the Google Sheets API.
3. Create an OAuth client for a Desktop app.
4. Download the OAuth client JSON.
5. Save it in this repository as:

```text
google_client_secret.json
```

6. Run locally once:

```bash
python run_job_pipeline.py
```

7. Complete the browser-based Google sign-in.

After sign-in, JobFinder creates:

```text
google_token.json
google_spreadsheet_id.txt
```

Do not commit these files. They are ignored by Git.

## Run Online With GitHub Actions

The online workflow is defined in:

```text
.github/workflows/jobs.yml
```

It runs the full pipeline on GitHub:

1. Checks out the repository.
2. Installs Python dependencies.
3. Writes your private keywords, prompt, and CV from GitHub secrets.
4. Writes your Google token from GitHub secrets.
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

### 3. Generate `google_token.json`

Run the pipeline locally once and complete Google login:

```bash
python run_job_pipeline.py
```

After the local run, copy the full token JSON:

```bash
cat google_token.json | pbcopy
```

Paste that full JSON into the GitHub secret `GOOGLE_TOKEN_JSON`.

This is required because GitHub Actions cannot open a browser for first-time Google OAuth.

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
| `GOOGLE_TOKEN_JSON` | The full contents of local `google_token.json`. |
| `JOB_KEYWORDS_TEXT` | The full contents of `configs/keywords.txt`. |
| `MASTER_PROMPT_TEXT` | The full contents of `prompts/master_prompt.txt`. |
| `MASTER_CV_TEX` | The full contents of `cv/master_cv.tex`. |

On macOS, you can copy each private file like this:

```bash
cat configs/keywords.txt | pbcopy
cat prompts/master_prompt.txt | pbcopy
cat cv/master_cv.tex | pbcopy
cat google_token.json | pbcopy
```

Paste each copied value into the matching GitHub secret.

### 5. Run The Workflow Manually

In GitHub:

```text
Repository -> Actions -> Job Scraper Pipeline -> Run workflow
```

Choose the source:

- `linkedin`
- `indeed`
- `both`

Click **Run workflow**.

The workflow will create a new dated tab in your Google Sheet and then evaluate the jobs.

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
JOB_EVAL_CONCURRENCY: "8"
JOB_EVAL_BATCH_SIZE: "40"
JOB_EVAL_LARGE_QUEUE_THRESHOLD: "200"
JOB_EVAL_LARGE_QUEUE_SLEEP_MS: "2000"
```

This means up to 8 OpenAI requests can run at the same time, with jobs grouped locally in batches of 40.

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

Final AI columns after evaluation:

- `AI Verdict`
- `AI Fit Score`
- `AI Tailored CV`

## Troubleshooting GitHub Actions

| Problem | What to check |
|---|---|
| `Missing repository secret ...` | Add the named secret under GitHub repo settings. |
| `GOOGLE_TOKEN_JSON` error | Copy the full contents of `google_token.json`, not `google_client_secret.json`. |
| Google authentication fails | Run locally once again, refresh `google_token.json`, and update the GitHub secret. |
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
google_token.json
google_spreadsheet_id.txt
configs/keywords.txt
prompts/master_prompt.txt
cv/master_cv.tex
```

Use GitHub secrets for all private online values.
