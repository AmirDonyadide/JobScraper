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
8. By default, keeps `Not Suitable` rows only when they have exactly one unsuitable-reason label.
9. By default, removes the other `Not Suitable` rows from the final output.
10. Removes the long job-description/details column after evaluation.

## How To Run

Choose the runbook that matches how you want to use JobFinder:

| Run mode | Best for | Guide |
|---|---|---|
| GitHub Actions | Routine scheduled runs, hands-off production use, and running without keeping your laptop open. | [Run with GitHub Actions](README.github-actions.md) |
| Local machine | First-time setup, debugging, changing filters, testing prompts, and one-off manual runs. | [Run locally](README.local.md) |

The GitHub Actions workflow is the recommended production path. Local runs are
the easiest way to verify configuration and safely test changes before pushing.

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
├── README.local.md
├── README.github-actions.md
└── README.md
```

The Python package is named `jobfinder` internally. The scraper component remains under `jobfinder.scraper`.

## Run Windows And Duplicates

When Google Sheets output is enabled, JobFinder reads the existing timestamped tabs before scraping. The newest previous tab name is treated as the previous exact run time in `JOBSCRAPER_TIMEZONE`, which defaults to `Europe/Berlin`.

Provider searches then use the configured posted-time window. LinkedIn uses a dynamic second-based window from the previous run with `JOBSCRAPER_SEARCH_WINDOW_BUFFER_SECONDS` padding; Indeed uses the actor's supported day bucket when the window fits. After scraping, JobFinder filters rows back to the exact previous-run/current-run posted interval, then removes jobs already present in older tabs before the evaluator runs.

Final scraper filters in `configs/filters.json` also remove jobs whose company names contain any `excluded_company_terms`, ignoring case and punctuation.

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

After evaluation, the default final-output policy keeps `Not Suitable` rows only
when they have exactly one unsuitable-reason label. Other `Not Suitable` rows are
removed. Manual GitHub Actions runs can choose `keep_all` to preserve every
evaluated row.

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
