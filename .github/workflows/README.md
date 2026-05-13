# GitHub Workflows

This directory contains the repository's CI workflow and production JobFinder
pipeline workflow.

## `ci.yml`

Runs on:

- Pull requests.
- Pushes to `main`.

Checks:

1. Checkout.
2. Set up Python 3.11 with pip cache.
3. Install `requirements-dev.txt`.
4. Run Ruff lint.
5. Run Ruff formatting check.
6. Run mypy on `src`.
7. Compile Python files.
8. Smoke-test CLI help with `PYTHONPATH=src`.
9. Validate `configs/filters.json`.
10. Run `pytest`.

This workflow does not require Apify, Google, or OpenAI secrets. Tests use fakes
and monkeypatching for external services.

## `jobs.yml`

Runs JobFinder in GitHub Actions.

Triggers:

- Manual `workflow_dispatch`.
- Daily schedule at `17 7 * * *`.

Manual inputs:

| Input | Options |
|---|---|
| `sources` | `linkedin`, `indeed`, `stepstone`, `both`, `all` |
| `posted_time_window` | `since_previous_run`, `last_24h`, `last_7d`, `backfill` |
| `max_applicants` | `50`, `100`, `200`, `no_limit` |
| `run_mode` | `scrape_and_evaluate`, `scrape_only` |
| `unsuitable_rows` | `single_label_only`, `keep_all` |

## Production Job Flow

```mermaid
flowchart TD
    A["checkout"] --> B["setup Python 3.11"]
    B --> C["install requirements.txt"]
    C --> D["validate required secrets"]
    D --> E["write private keyword/prompt/CV files"]
    E --> F["write Google service account and spreadsheet ID"]
    F --> G["preflight provider and sheet access"]
    G --> H["run selected pipeline"]
    H --> I["write workflow summary"]
    I --> J["upload report artifacts"]
    J --> K["remove private runtime files"]
```

The workflow sets `JOBSCRAPER_OUTPUT_MODE=google_sheets` and writes private
runtime files from secrets. Cleanup removes those files in an `always()` step.

## Required Secrets

| Secret | Required when | Description |
|---|---|---|
| `APIFY_API_TOKEN` | Always | One Apify token or up to 12 semicolon-separated tokens. |
| `GOOGLE_SPREADSHEET_ID` | Always | Target spreadsheet ID. |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Always | Full service-account JSON key. |
| `JOB_KEYWORDS_TEXT` | Always | Contents of private `configs/keywords.txt`. |
| `OPENAI_API_KEY` | `scrape_and_evaluate` | OpenAI API key. |
| `MASTER_PROMPT_TEXT` | `scrape_and_evaluate` | Contents of private evaluator prompt. |
| `MASTER_CV_TEX` | `scrape_and_evaluate` | Contents of private LaTeX CV. |

## Report Artifacts

`jobs.yml` uploads `jobfinder-run-reports` with:

- `reports/pipeline_preflight.json`
- `reports/scraper.json`
- `reports/evaluator.json`
- `reports/workflow_summary.md`

Reports are generated only when the corresponding env var path is configured.

## Operational Constraints

- `concurrency.cancel-in-progress` is `false`, so scheduled/manual runs do not
  cancel an already running pipeline.
- The job timeout is 360 minutes.
- Scheduled runs use default workflow inputs, not the last manual selections.
- The workflow writes service-account JSON to a temporary runner file and
  applies restrictive file permissions before use.
- Do not echo secret values while debugging.
