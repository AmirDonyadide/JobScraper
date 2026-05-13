# Scripts

The `scripts/` directory contains thin compatibility entry points that mirror
the root scripts from a conventional scripts folder.

| Script | Calls |
|---|---|
| `run_pipeline.py` | `jobfinder.pipeline.cli:main` |
| `scrape_jobs.py` | `jobfinder.scraper.cli:main` |
| `evaluate_jobs.py` | `jobfinder.evaluator.cli:main` |

Each script prepends the repository `src` directory to `sys.path`, so it can run
without an editable package install as long as dependencies are installed.

Examples:

```bash
python scripts/run_pipeline.py --preflight
python scripts/run_pipeline.py --mode scrape_only
python scripts/scrape_jobs.py
python scripts/evaluate_jobs.py --source google_sheets --sheet latest
```

## Maintainer Notes

- Keep these scripts as wrappers only. Workflow logic belongs in
  `src/jobfinder`.
- If CLI names or module paths change, update root wrappers and these scripts
  together.
- CI compiles these scripts but does not run them as separate smoke tests.
