# Contributing

Thanks for improving JobScraper. Keep changes small and easy to reason about; this project is meant to stay simple enough that someone can read it in one sitting.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Add your own `APIFY_API_TOKEN` to `.env` before running the scraper.

## Before You Commit

Run these checks:

```bash
python -m ruff check linkedin_job_scraper.py
python -m pyflakes linkedin_job_scraper.py
python -m compileall linkedin_job_scraper.py
```

For documentation-only changes, read the rendered Markdown and make sure commands and environment variable names match the script.

## Change Guidelines

- Preserve the existing input and output columns unless the README and downstream users are updated together.
- Keep `.env.example` in sync with supported environment variables.
- Prefer `.env` settings for operational tuning and script constants for search strategy.
- Keep generated files and credentials out of Git.
- Do not print or commit tokens, Google credential files, generated workbooks, or local spreadsheet IDs.
- If changing deduplication, date parsing, or export formatting, add a small manual smoke test note to the pull request.

## Common Changes

| Change | Where |
|---|---|
| Add or remove search terms | `KEYWORDS` in `linkedin_job_scraper.py` |
| Change LinkedIn location | `LOCATION` and `GEO_ID` |
| Change title exclusions | `EXCLUDED_TITLE_TERMS` |
| Tune speed or timeouts | `.env` or GitHub Actions environment variables |
| Change default local settings | `.env.example` |
| Explain user-facing behavior | `README.md` |
