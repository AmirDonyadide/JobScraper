# Pipeline

The pipeline package runs JobFinder as one coordinated workflow: scrape jobs to
Google Sheets, then optionally evaluate the newly created latest tab.

The CLI entry point is:

```bash
python run_job_pipeline.py
```

or, after editable install:

```bash
jobfinder-pipeline
```

## Files

| File | Responsibility |
|---|---|
| `cli.py` | Pipeline mode parsing, required setting validation, child process execution, and report writing. |
| `preflight.py` | Configuration, Google Sheets, prompt/CV, and OpenAI key readiness checks. |

## Modes

| Mode | Behavior |
|---|---|
| `scrape_only` | Run scraper only. The pipeline still forces Google Sheets output. |
| `scrape_and_evaluate` | Run scraper, then run evaluator against `--source google_sheets --sheet latest`. |

Aliases such as `scrape`, `scraper_only`, `full`, and `both` are accepted and
resolved in `parse_pipeline_mode()`.

## Execution Flow

```mermaid
flowchart TD
    A["run_job_pipeline.py"] --> B["pipeline/cli.py"]
    B --> C["load .env fallback"]
    C --> D["validate APIFY_API_TOKEN<br/>and OPENAI_API_KEY when needed"]
    D --> E{"--preflight?"}
    E -- yes --> F["run_preflight()"]
    E -- no --> G["python -m jobfinder.scraper.cli"]
    G --> H{"scrape_only?"}
    H -- yes --> I["done"]
    H -- no --> J["python -m jobfinder.evaluator.cli<br/>--source google_sheets --sheet latest"]
```

Child commands are run with:

- `cwd` set to the repository root.
- `PYTHONPATH` containing the local `src` directory.
- Local `.env` values merged into the child environment without overriding real
  environment variables.
- `JOBSCRAPER_OUTPUT_MODE=google_sheets`.
- `JOBFINDER_PIPELINE_MODE` set to the resolved mode.

## Preflight

`python run_job_pipeline.py --preflight` validates:

- Scraper settings and keyword/filter files.
- Apify token presence and token-count limit before settings load.
- Google Sheets authentication and spreadsheet access.
- Prompt and CV files when evaluation is enabled.
- `OPENAI_API_KEY` when evaluation is enabled.

Preflight reads Google Sheets history but does not seed the hidden
`_jobfinder_seen_jobs` tab.

## Report Output

When these env vars are set, the pipeline writes sanitized JSON reports:

| Variable | Report |
|---|---|
| `JOBFINDER_PIPELINE_REPORT_FILE` | Preflight status. |
| `JOBFINDER_SCRAPER_REPORT_FILE` | Scraper result or failure. |
| `JOBFINDER_EVALUATOR_REPORT_FILE` | Evaluator summary or failure. |

GitHub Actions sets these to paths under `reports/` and uploads them as
artifacts.

## Constraints

- The pipeline is Google Sheets oriented. Use `linkedin_job_scraper.py` directly
  for local Excel-only scraping.
- The evaluator always targets the latest Google Sheets tab created by the
  scraper step.
- `validate_python_dependencies()` currently only checks the OpenAI package for
  evaluation mode; runtime imports still validate other dependencies when used.
