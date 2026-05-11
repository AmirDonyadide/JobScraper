"""Command-line entry point for the one-step scrape/evaluate pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys

from jobfinder.env import load_local_env
from jobfinder.paths import ENV_FILE, PROJECT_ROOT
from jobfinder.scraper.settings import TOKEN_PLACEHOLDER

LOGGER = logging.getLogger("jobfinder.pipeline")

PIPELINE_MODE_SCRAPE_ONLY = "scrape_only"
PIPELINE_MODE_SCRAPE_AND_EVALUATE = "scrape_and_evaluate"
DEFAULT_PIPELINE_MODE = PIPELINE_MODE_SCRAPE_AND_EVALUATE
PIPELINE_MODE_ALIASES = {
    "scrape": PIPELINE_MODE_SCRAPE_ONLY,
    "scrape_only": PIPELINE_MODE_SCRAPE_ONLY,
    "scrape-only": PIPELINE_MODE_SCRAPE_ONLY,
    "scraper": PIPELINE_MODE_SCRAPE_ONLY,
    "scraper_only": PIPELINE_MODE_SCRAPE_ONLY,
    "scraper-only": PIPELINE_MODE_SCRAPE_ONLY,
    "both": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
    "full": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
    "scrape_and_evaluate": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
    "scrape-and-evaluate": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
    "scrape_evaluate": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
    "scrape-evaluate": PIPELINE_MODE_SCRAPE_AND_EVALUATE,
}


def setting(local_env: dict[str, str], name: str, default: str = "") -> str:
    """Read a setting from environment variables with local env fallback."""
    return os.environ.get(name, local_env.get(name, default)).strip()


def parse_pipeline_mode(value: str | None) -> str:
    """Resolve user-facing pipeline mode aliases into canonical mode names."""
    normalized = (value or DEFAULT_PIPELINE_MODE).strip().lower()
    mode = PIPELINE_MODE_ALIASES.get(normalized)
    if mode:
        return mode

    allowed = ", ".join(sorted(PIPELINE_MODE_ALIASES))
    raise SystemExit(f"Unknown pipeline mode {value!r}. Use one of: {allowed}.")


def resolve_pipeline_mode(args: argparse.Namespace, local_env: dict[str, str]) -> str:
    """Resolve the selected mode from CLI args, env, or the default."""
    mode_value = args.mode or setting(local_env, "JOBFINDER_PIPELINE_MODE")
    return parse_pipeline_mode(mode_value)


def validate_required_settings(local_env: dict[str, str], pipeline_mode: str) -> None:
    """Ensure the selected pipeline mode has the secrets it needs."""
    apify_token = setting(local_env, "APIFY_API_TOKEN")

    missing = []
    if not apify_token or apify_token == TOKEN_PLACEHOLDER:
        missing.append("APIFY_API_TOKEN")

    if pipeline_mode == PIPELINE_MODE_SCRAPE_AND_EVALUATE:
        openai_key = setting(local_env, "OPENAI_API_KEY")
        if not openai_key:
            missing.append("OPENAI_API_KEY")

    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing required setting(s): {names}. Add them to {ENV_FILE.name}."
        )


def validate_python_dependencies(pipeline_mode: str) -> None:
    """Fail early when dependencies for the selected mode are missing."""
    if pipeline_mode == PIPELINE_MODE_SCRAPE_ONLY:
        return

    missing_packages = []
    try:
        import openai  # noqa: F401
    except ImportError:
        missing_packages.append("openai")

    if missing_packages:
        packages = ", ".join(missing_packages)
        raise SystemExit(
            f"Missing Python package(s): {packages}. Run this inside your Conda "
            "environment: python -m pip install -r requirements.txt"
        )


def run_step(command: list[str], env: dict[str, str], label: str) -> None:
    """Run one pipeline child command and stop on non-zero exit."""
    LOGGER.info(label)
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the pipeline CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run JobFinder: scrape jobs to Google Sheets, optionally followed by "
            "OpenAI evaluation."
        )
    )
    parser.add_argument(
        "--mode",
        help=(
            "Use 'scrape_only' to stop after scraping, or "
            "'scrape_and_evaluate' to run both steps. Defaults to "
            "JOBFINDER_PIPELINE_MODE or scrape_and_evaluate."
        ),
    )
    return parser


def child_pythonpath() -> str:
    """Return a PYTHONPATH value that includes the local src directory."""
    src_path = str(PROJECT_ROOT / "src")
    existing = os.environ.get("PYTHONPATH")
    if existing:
        return os.pathsep.join([src_path, existing])
    return src_path


def main() -> int:
    """Run the scraper pipeline in the selected mode."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = build_arg_parser().parse_args()
    local_env = load_local_env()
    pipeline_mode = resolve_pipeline_mode(args, local_env)
    validate_required_settings(local_env, pipeline_mode)
    validate_python_dependencies(pipeline_mode)

    env = os.environ.copy()
    for key, value in local_env.items():
        env.setdefault(key, value)
    env["PYTHONPATH"] = child_pythonpath()
    env["JOBSCRAPER_OUTPUT_MODE"] = "google_sheets"
    env["JOBFINDER_PIPELINE_MODE"] = pipeline_mode

    scrape_command = [sys.executable, "-m", "jobfinder.scraper.cli"]
    evaluate_command = [
        sys.executable,
        "-m",
        "jobfinder.evaluator.cli",
        "--source",
        "google_sheets",
        "--sheet",
        "latest",
    ]

    if pipeline_mode == PIPELINE_MODE_SCRAPE_ONLY:
        run_step(scrape_command, env, "Step 1/1: Scraping jobs to Google Sheets")
        LOGGER.info("Scrape-only pipeline complete. Evaluation was skipped.")
        return 0

    run_step(scrape_command, env, "Step 1/2: Scraping jobs to Google Sheets")
    run_step(evaluate_command, env, "Step 2/2: Evaluating jobs with OpenAI")

    LOGGER.info(
        "Pipeline complete. Your Google Sheet now includes the AI evaluation columns."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
