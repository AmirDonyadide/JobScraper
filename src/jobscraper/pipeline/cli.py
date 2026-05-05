"""Command-line entry point for the one-step scrape/evaluate pipeline."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from jobscraper.env import load_local_env
from jobscraper.paths import ENV_FILE, PROJECT_ROOT
from jobscraper.scraper.settings import TOKEN_PLACEHOLDER


def setting(local_env: dict[str, str], name: str, default: str = "") -> str:
    """Read a setting from environment variables with local env fallback."""
    return os.environ.get(name, local_env.get(name, default)).strip()


def validate_required_settings(local_env: dict[str, str]) -> None:
    """Ensure the pipeline has the secrets required by both child steps."""
    apify_token = setting(local_env, "APIFY_API_TOKEN")
    openai_key = setting(local_env, "OPENAI_API_KEY")

    missing = []
    if not apify_token or apify_token == TOKEN_PLACEHOLDER:
        missing.append("APIFY_API_TOKEN")
    if not openai_key:
        missing.append("OPENAI_API_KEY")

    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing required setting(s): {names}. Add them to {ENV_FILE.name}."
        )


def validate_python_dependencies() -> None:
    """Fail early when optional pipeline dependencies are missing."""
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
    print("\n" + "=" * 70, flush=True)
    print(label, flush=True)
    print("=" * 70, flush=True)
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the pipeline CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scrape LinkedIn jobs to Google Sheets, then evaluate them with OpenAI."
        )
    )
    parser.add_argument(
        "--sources",
        choices=["linkedin", "indeed", "both"],
        default="linkedin",
        help="Job source(s) to scrape before evaluation. Default: linkedin.",
    )
    parser.add_argument(
        "--sheet",
        default="latest",
        help="Google Sheet tab to evaluate after scraping. Default: latest.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-mini",
        help="OpenAI model for evaluation. Default: gpt-5-mini.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional evaluation limit for testing. Omit to evaluate all rows.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help="Concurrent OpenAI evaluation requests. Default: 2.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Evaluation batch size. Default: 10.",
    )
    parser.add_argument(
        "--reevaluate",
        action="store_true",
        help="Re-evaluate rows even if AI Verdict already exists.",
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
    """Run the two-step scraper and evaluator pipeline."""
    args = build_arg_parser().parse_args()
    local_env = load_local_env()
    validate_required_settings(local_env)
    validate_python_dependencies()

    env = os.environ.copy()
    env.update(local_env)
    env["PYTHONPATH"] = child_pythonpath()
    env["JOBSCRAPER_OUTPUT_MODE"] = "google_sheets"
    env["JOBSCRAPER_SOURCES"] = args.sources
    env["JOB_EVAL_OPENAI_MODEL"] = args.model

    scrape_command = [sys.executable, "-m", "jobscraper.scraper.cli"]
    evaluate_command = [
        sys.executable,
        "-m",
        "jobscraper.evaluator.cli",
        "--source",
        "google_sheets",
        "--sheet",
        args.sheet,
        "--model",
        args.model,
        "--concurrency",
        str(args.concurrency),
        "--batch-size",
        str(args.batch_size),
    ]
    if args.limit is not None:
        evaluate_command.extend(["--limit", str(args.limit)])
    if args.reevaluate:
        evaluate_command.append("--reevaluate")

    run_step(scrape_command, env, "Step 1/2: Scraping jobs to Google Sheets")
    run_step(evaluate_command, env, "Step 2/2: Evaluating jobs with OpenAI")

    print(
        "\nPipeline complete. Your Google Sheet now includes the AI evaluation columns."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
