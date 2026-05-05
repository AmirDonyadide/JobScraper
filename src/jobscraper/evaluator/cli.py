"""Command-line entry point for evaluating scraped jobs with OpenAI."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from jobscraper.env import EnvSettings
from jobscraper.evaluator.models import (
    DEFAULT_MODEL,
    EvaluationError,
    GoogleSheetsError,
)
from jobscraper.evaluator.openai_client import OpenAIJobEvaluator, evaluate_records
from jobscraper.evaluator.parsing import (
    ensure_output_columns,
    extract_job_records,
    read_text_asset,
)
from jobscraper.evaluator.storage import (
    build_evaluator_google_sheets_service,
    read_excel_input,
    read_google_input,
    read_google_spreadsheet_id,
    write_excel_output,
    write_google_output,
)
from jobscraper.paths import (
    DEFAULT_CV_FILE,
    DEFAULT_EXCEL_FILE,
    DEFAULT_MASTER_PROMPT_FILE,
)

LOGGER = logging.getLogger("job_fit_evaluator")


def parse_source(value: str | None, google_sheet_id: str, env: EnvSettings) -> str:
    """Resolve the evaluator source from CLI, env, or available spreadsheet ID."""
    selected = (value or env.get("JOB_EVAL_SOURCE")).strip().casefold()
    aliases = {
        "excel": "excel",
        "xlsx": "excel",
        "local": "excel",
        "google": "google_sheets",
        "google_sheets": "google_sheets",
        "sheets": "google_sheets",
        "drive": "google_sheets",
    }
    if selected:
        if selected not in aliases:
            raise EvaluationError("Unsupported source. Use 'excel' or 'google_sheets'.")
        return aliases[selected]
    if google_sheet_id:
        return "google_sheets"
    return "excel"


def build_arg_parser(env: EnvSettings | None = None) -> argparse.ArgumentParser:
    """Build the evaluator CLI argument parser."""
    env = env or EnvSettings(logger=LOGGER)
    parser = argparse.ArgumentParser(
        description="Evaluate job postings with OpenAI and update the same sheet."
    )
    parser.add_argument(
        "--source",
        choices=["excel", "google_sheets"],
        default=None,
        help=(
            "Where to read jobs from. Defaults to Google Sheets when a spreadsheet "
            "ID is configured, otherwise Excel."
        ),
    )
    parser.add_argument(
        "--sheet",
        default=env.get("JOB_EVAL_SHEET", "latest"),
        help="Worksheet or Google Sheet tab to evaluate. Defaults to the latest tab.",
    )
    return parser


def configure_logging() -> None:
    """Configure evaluator logging for CLI output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def validate_runtime_settings(
    *,
    batch_size: int,
    concurrency: int,
    retries: int,
    max_output_tokens: int,
    large_queue_threshold: int = 200,
    large_queue_sleep_ms: int = 2000,
) -> None:
    """Validate evaluator runtime settings before doing any I/O."""
    if batch_size < 1:
        raise EvaluationError("JOB_EVAL_BATCH_SIZE must be 1 or greater.")
    if concurrency < 1:
        raise EvaluationError("JOB_EVAL_CONCURRENCY must be 1 or greater.")
    if retries < 0:
        raise EvaluationError("JOB_EVAL_OPENAI_RETRIES must be 0 or greater.")
    if max_output_tokens < 500:
        raise EvaluationError(
            "JOB_EVAL_MAX_OUTPUT_TOKENS is too small for reliable parsing."
        )
    if large_queue_threshold < 0:
        raise EvaluationError("JOB_EVAL_LARGE_QUEUE_THRESHOLD must be 0 or greater.")
    if large_queue_sleep_ms < 0:
        raise EvaluationError("JOB_EVAL_LARGE_QUEUE_SLEEP_MS must be 0 or greater.")


def load_input_rows(
    args: argparse.Namespace,
    source: str,
    spreadsheet_id: str,
    excel_file: Path,
) -> tuple[Any, Any, Any, str, list[str], list[list[Any]]]:
    """Read evaluator input rows from Excel or Google Sheets."""
    google_service = None
    if source == "excel":
        workbook, worksheet, sheet_name, headers, rows = read_excel_input(
            excel_file,
            args.sheet,
        )
    else:
        if not spreadsheet_id:
            raise EvaluationError(
                "Google Sheets source selected but no spreadsheet ID was provided. "
                "Set --google-sheet-id, GOOGLE_SPREADSHEET_ID, or "
                "google_spreadsheet_id.txt."
            )
        google_service = build_evaluator_google_sheets_service()
        sheet_name, headers, rows = read_google_input(
            google_service,
            spreadsheet_id,
            args.sheet,
        )
        workbook = worksheet = None

    return google_service, workbook, worksheet, sheet_name, headers, rows


def write_outputs(
    excel_file: Path,
    source: str,
    spreadsheet_id: str,
    google_service: Any,
    workbook: Any,
    worksheet: Any,
    sheet_name: str,
    headers: list[str],
    header_map: dict[str, int],
    evaluations: dict[int, Any],
    *,
    cleanup_columns: bool = True,
) -> None:
    """Write evaluator headers and result values back to the selected source."""
    if source == "excel":
        write_excel_output(
            workbook,
            worksheet,
            excel_file,
            headers,
            header_map,
            evaluations,
            cleanup_columns=cleanup_columns,
        )
    else:
        write_google_output(
            google_service,
            spreadsheet_id,
            sheet_name,
            headers,
            header_map,
            evaluations,
            cleanup_columns=cleanup_columns,
        )


def main() -> int:
    """Run the evaluator CLI."""
    configure_logging()
    env = EnvSettings(logger=LOGGER)
    args = build_arg_parser(env).parse_args()

    try:
        excel_file = Path(env.get("JOB_EVAL_EXCEL_FILE", str(DEFAULT_EXCEL_FILE)))
        master_prompt_file = Path(
            env.get("JOB_EVAL_MASTER_PROMPT_FILE", str(DEFAULT_MASTER_PROMPT_FILE))
        )
        cv_file = Path(env.get("JOB_EVAL_CV_FILE", str(DEFAULT_CV_FILE)))
        model = env.get("JOB_EVAL_OPENAI_MODEL", DEFAULT_MODEL)
        batch_size = env.get_int("JOB_EVAL_BATCH_SIZE", 40)
        concurrency = env.get_int("JOB_EVAL_CONCURRENCY", 8)
        retries = env.get_int("JOB_EVAL_OPENAI_RETRIES", 3)
        retry_base_delay = env.get_float("JOB_EVAL_RETRY_BASE_DELAY", 2.0)
        retry_max_delay = env.get_float("JOB_EVAL_RETRY_MAX_DELAY", 60.0)
        timeout = env.get_float("JOB_EVAL_OPENAI_TIMEOUT", 120.0)
        max_output_tokens = env.get_int("JOB_EVAL_MAX_OUTPUT_TOKENS", 9000)
        large_queue_threshold = env.get_int("JOB_EVAL_LARGE_QUEUE_THRESHOLD", 200)
        large_queue_sleep_ms = env.get_int("JOB_EVAL_LARGE_QUEUE_SLEEP_MS", 2000)

        validate_runtime_settings(
            batch_size=batch_size,
            concurrency=concurrency,
            retries=retries,
            max_output_tokens=max_output_tokens,
            large_queue_threshold=large_queue_threshold,
            large_queue_sleep_ms=large_queue_sleep_ms,
        )

        master_prompt = read_text_asset(master_prompt_file, "master prompt")
        latex_cv = read_text_asset(cv_file, "LaTeX CV")
        spreadsheet_id = read_google_spreadsheet_id(
            env.get("JOB_EVAL_GOOGLE_SPREADSHEET_ID")
        )
        source = parse_source(args.source, spreadsheet_id, env)

        LOGGER.info("Loading %s input ...", source)
        google_service, workbook, worksheet, sheet_name, headers, rows = (
            load_input_rows(
                args,
                source,
                spreadsheet_id,
                excel_file,
            )
        )

        headers, header_map = ensure_output_columns(headers)
        records, skipped_existing = extract_job_records(
            headers,
            rows,
        )

        LOGGER.info("Sheet: %s", sheet_name)
        LOGGER.info("Rows queued: %s", len(records))
        if skipped_existing:
            LOGGER.info(
                "Rows skipped because AI Verdict already exists: %s",
                skipped_existing,
            )

        if not records:
            LOGGER.info("No rows need evaluation. Writing any missing AI headers only.")
            write_outputs(
                excel_file,
                source,
                spreadsheet_id,
                google_service,
                workbook,
                worksheet,
                sheet_name,
                headers,
                header_map,
                {},
            )
            return 0

        api_key = env.get("OPENAI_API_KEY")
        if not api_key:
            raise EvaluationError(
                "Missing OPENAI_API_KEY. Add it to your environment or local .env file."
            )

        evaluator = OpenAIJobEvaluator(
            model=model,
            api_key=api_key,
            timeout=timeout,
            retries=retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
            max_output_tokens=max_output_tokens,
        )

        def save_evaluation(evaluation: Any) -> None:
            LOGGER.info("Saving evaluation for row %s ...", evaluation.row_number)
            write_outputs(
                excel_file,
                source,
                spreadsheet_id,
                google_service,
                workbook,
                worksheet,
                sheet_name,
                headers,
                header_map,
                {evaluation.row_number: evaluation},
                cleanup_columns=False,
            )

        evaluations = evaluate_records(
            records,
            evaluator=evaluator,
            master_prompt=master_prompt,
            latex_cv=latex_cv,
            concurrency=concurrency,
            batch_size=batch_size,
            large_queue_threshold=large_queue_threshold,
            large_queue_sleep_ms=large_queue_sleep_ms,
            on_evaluation=save_evaluation,
        )

        LOGGER.info(
            "Finalizing output columns after %s saved evaluation(s) ...",
            len(evaluations),
        )
        write_outputs(
            excel_file,
            source,
            spreadsheet_id,
            google_service,
            workbook,
            worksheet,
            sheet_name,
            headers,
            header_map,
            {},
            cleanup_columns=True,
        )
        if source == "excel":
            LOGGER.info("Saved Excel workbook: %s (sheet: %s)", excel_file, sheet_name)
        else:
            LOGGER.info(
                "Updated Google Sheet ID %s (tab: %s)",
                spreadsheet_id,
                sheet_name,
            )

        suitable_count = sum(
            1 for evaluation in evaluations.values() if evaluation.verdict == "Suitable"
        )
        not_suitable_count = sum(
            1
            for evaluation in evaluations.values()
            if evaluation.verdict == "Not Suitable"
        )
        error_count = sum(
            1 for evaluation in evaluations.values() if evaluation.verdict == "Error"
        )
        LOGGER.info(
            "Done. Suitable=%s, Not Suitable=%s, Error=%s",
            suitable_count,
            not_suitable_count,
            error_count,
        )
        return 0

    except (EvaluationError, GoogleSheetsError) as exc:
        LOGGER.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
