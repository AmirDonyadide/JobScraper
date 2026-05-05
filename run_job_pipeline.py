"""Compatibility wrapper for the one-step JobScraper pipeline.

The pipeline implementation lives in ``src/jobscraper/pipeline``. This wrapper
preserves the historical command:

    python run_job_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobscraper.pipeline.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
