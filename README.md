# JobScraper

JobScraper collects recent job postings from Apify-powered LinkedIn and Indeed
scrapers, removes duplicates and unwanted results, exports the jobs to Excel or
Google Sheets, and can evaluate each job with OpenAI using your private prompt
and CV.

The default customer workflow is one command:

```bash
python run_job_pipeline.py
```

That command scrapes jobs into Google Sheets, evaluates every unevaluated job,
keeps only the final AI columns, and removes the long job-description column
after evaluation.

## What You Need

- Python 3.11 or newer
- An Apify API token
- An OpenAI API key
- Google Sheets access if you want the full pipeline

## Installation

```bash
cd /path/to/JobScraper
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

If you use Conda:

```bash
cd /path/to/JobScraper
conda create -n jobscraper python=3.11 -y
conda activate jobscraper
python -m pip install -r requirements.txt
cp .env.example .env
```

## Private Inputs

Your real keywords, master prompt, and CV are private and ignored by Git. Create
them from the examples:

```bash
cp configs/keywords.example.txt configs/keywords.txt
cp prompts/master_prompt.example.txt prompts/master_prompt.txt
cp cv/master_cv.example.tex cv/master_cv.tex
```

Then edit:

- `configs/keywords.txt`: one search keyword per line
- `prompts/master_prompt.txt`: the prompt used for AI job evaluation
- `cv/master_cv.tex`: your private LaTeX CV

## Environment Settings

Open `.env` and set at least:

```bash
APIFY_API_TOKEN=apify_api_...
OPENAI_API_KEY=sk-...
```

For Google Sheets, also set or generate:

```bash
GOOGLE_SPREADSHEET_ID=
```

If `GOOGLE_SPREADSHEET_ID` is blank, the first Google Sheets export creates a
spreadsheet named `jobs` and stores its ID in `google_spreadsheet_id.txt`.

Common settings:

| Setting | Default | Description |
|---|---:|---|
| `JOBSCRAPER_SOURCES` | `linkedin` | Use `linkedin`, `indeed`, or `both`. |
| `JOBSCRAPER_OUTPUT_MODE` | `excel` | Use `excel`, `google_sheets`, or `both`. The full pipeline forces Google Sheets. |
| `JOBSCRAPER_SEARCH_CONCURRENCY` | `15` | Number of Apify searches run at the same time. |
| `JOBSCRAPER_MAX_RESULTS_PER_SEARCH` | `500` | Maximum LinkedIn results per keyword. |
| `JOBSCRAPER_POSTED_TIMEZONE` | `Europe/Berlin` | Timezone for the `Posted` column. |
| `JOB_EVAL_OPENAI_MODEL` | `gpt-5-mini` | OpenAI model used for evaluation. |
| `JOB_EVAL_CONCURRENCY` | `2` | Number of OpenAI job evaluations run at the same time. |
| `JOB_EVAL_BATCH_SIZE` | `10` | Number of jobs processed per evaluator batch. |

## Running

Run the full Google Sheets pipeline:

```bash
python run_job_pipeline.py
```

Scrape only, using `JOBSCRAPER_OUTPUT_MODE` from `.env`:

```bash
python linkedin_job_scraper.py
```

Evaluate an existing sheet:

```bash
python job_fit_evaluator.py --source google_sheets --sheet latest
```

Evaluate an existing Excel workbook:

```bash
python job_fit_evaluator.py --source excel --sheet latest
```

## Google Sheets Setup

For local Google Sheets use:

1. Enable the Google Sheets API in Google Cloud.
2. Create a Desktop OAuth client.
3. Download the client JSON as `google_client_secret.json`.
4. Run `python run_job_pipeline.py`.
5. Complete the browser sign-in once.

After that, `google_token.json` is saved locally and future runs are automatic.
Do not commit Google credential files.

## GitHub Actions

The workflow runs the full pipeline and processes every unevaluated row. Add
these repository secrets under `Settings > Secrets and variables > Actions`:

| Secret | Value |
|---|---|
| `APIFY_API_TOKEN` | Your Apify token. |
| `OPENAI_API_KEY` | Your OpenAI API key. |
| `GOOGLE_SPREADSHEET_ID` | The target Google spreadsheet ID. |
| `GOOGLE_TOKEN_JSON` | The full contents of your local `google_token.json`. |
| `JOB_KEYWORDS_TEXT` | The full contents of your private `configs/keywords.txt`. |
| `MASTER_PROMPT_TEXT` | The full contents of your private `prompts/master_prompt.txt`. |
| `MASTER_CV_TEX` | The full contents of your private `cv/master_cv.tex`. |

The workflow can run manually or on its daily schedule. Manual runs allow you to
choose `linkedin`, `indeed`, or `both` as the source.

## Output

Scraper output columns:

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

Final AI columns:

- `AI Verdict`
- `AI Fit Score`
- `AI Tailored CV`

## Troubleshooting

| Problem | What to Check |
|---|---|
| Missing Apify token | Set `APIFY_API_TOKEN` in `.env` or GitHub secrets. |
| Missing OpenAI key | Set `OPENAI_API_KEY` in `.env` or GitHub secrets. |
| Missing keywords | Copy `configs/keywords.example.txt` to `configs/keywords.txt`. |
| Missing prompt or CV | Copy the example files in `prompts/` and `cv/`, then edit them. |
| Google credential error | Ensure `google_client_secret.json` exists locally, or `GOOGLE_TOKEN_JSON` exists in GitHub secrets. |
| Spreadsheet not found | Check `GOOGLE_SPREADSHEET_ID` or delete `google_spreadsheet_id.txt` to create a new spreadsheet. |
| Too many API retries | Lower `JOBSCRAPER_SEARCH_CONCURRENCY` or `JOB_EVAL_CONCURRENCY` in `.env`. |
