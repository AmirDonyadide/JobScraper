# Operations

This package contains small operational helpers used by local and GitHub Actions
runs.

## Reports

`reports.py` writes sanitized JSON report files when report paths are configured
through environment variables:

- `JOBFINDER_PIPELINE_REPORT_FILE`
- `JOBFINDER_SCRAPER_REPORT_FILE`
- `JOBFINDER_EVALUATOR_REPORT_FILE`

Reports contain:

| Field | Description |
|---|---|
| `status` | `succeeded` or `failed`. |
| `category` | Report category such as `preflight`, `scrape`, or `evaluation`. |
| `generated_at` | UTC timestamp. |
| `details` | Dataclass or dictionary payload from the caller. |

The helper serializes dataclasses with `dataclasses.asdict()` and sorts JSON
keys for stable artifacts.

## Constraints

- Do not write secrets into report details.
- Use reports for summaries and diagnostics, not raw scraped job data.
- Keep report payloads durable enough for CI artifact review.
