"""Compatibility wrapper for the JobScraper evaluator CLI.

The evaluator implementation lives in ``src/jobscraper/evaluator``. This
wrapper preserves the historical command:

    python job_fit_evaluator.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobscraper.evaluator.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
