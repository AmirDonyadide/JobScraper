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
    parser.add_argument("--source", choices=["excel", "google_sheets"], default=None)
    parser.add_argument(
        "--excel-file",
        default=env.get("JOB_EVAL_EXCEL_FILE", str(DEFAULT_EXCEL_FILE)),
    )
    parser.add_argument(
        "--google-sheet-id",
        default=env.get("JOB_EVAL_GOOGLE_SPREADSHEET_ID"),
    )
    parser.add_argument("--sheet", default=env.get("JOB_EVAL_SHEET", "latest"))
    parser.add_argument(
        "--master-prompt",
        default=env.get("JOB_EVAL_MASTER_PROMPT_FILE", str(DEFAULT_MASTER_PROMPT_FILE)),
    )
    parser.add_argument(
        "--cv", default=env.get("JOB_EVAL_CV_FILE", str(DEFAULT_CV_FILE))
    )
    parser.add_argument(
        "--model",
        default=env.get("JOB_EVAL_OPENAI_MODEL", DEFAULT_MODEL),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--start-row", type=int, default=env.get_int("JOB_EVAL_START_ROW", 2)
    )
    parser.add_argument(
        "--batch-size", type=int, default=env.get_int("JOB_EVAL_BATCH_SIZE", 10)
    )
    parser.add_argument(
        "--concurrency", type=int, default=env.get_int("JOB_EVAL_CONCURRENCY", 2)
    )
    parser.add_argument(
        "--retries", type=int, default=env.get_int("JOB_EVAL_OPENAI_RETRIES", 3)
    )
    parser.add_argument(
        "--retry-base-delay",
        type=float,
        default=env.get_float("JOB_EVAL_RETRY_BASE_DELAY", 2.0),
    )
    parser.add_argument(
        "--retry-max-delay",
        type=float,
        default=env.get_float("JOB_EVAL_RETRY_MAX_DELAY", 60.0),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=env.get_float("JOB_EVAL_OPENAI_TIMEOUT", 120.0),
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=env.get_int("JOB_EVAL_MAX_OUTPUT_TOKENS", 9000),
    )
    parser.add_argument(
        "--reevaluate",
        action="store_true",
        help="Evaluate rows even when AI Verdict is already populated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read rows and build prompts, but do not call OpenAI or save output.",
    )
    return parser


def configure_logging() -> None:
    """Configure evaluator logging for CLI output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )


def validate_args(args: argparse.Namespace) -> None:
    """Validate evaluator CLI arguments before doing any I/O."""
    if args.start_row < 2:
        raise EvaluationError("--start-row must be 2 or greater.")
    if args.batch_size < 1:
        raise EvaluationError("--batch-size must be 1 or greater.")
    if args.concurrency < 1:
        raise EvaluationError("--concurrency must be 1 or greater.")
    if args.retries < 0:
        raise EvaluationError("--retries must be 0 or greater.")
    if args.max_output_tokens < 500:
        raise EvaluationError("--max-output-tokens is too small for reliable parsing.")


def load_input_rows(
    args: argparse.Namespace,
    source: str,
    spreadsheet_id: str,
) -> tuple[Any, Any, Any, str, list[str], list[list[Any]]]:
    """Read evaluator input rows from Excel or Google Sheets."""
    google_service = None
    if source == "excel":
        workbook, worksheet, sheet_name, headers, rows = read_excel_input(
            Path(args.excel_file),
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
    args: argparse.Namespace,
    source: str,
    spreadsheet_id: str,
    google_service: Any,
    workbook: Any,
    worksheet: Any,
    sheet_name: str,
    headers: list[str],
    header_map: dict[str, int],
    evaluations: dict[int, Any],
) -> None:
    """Write evaluator headers and result values back to the selected source."""
    if source == "excel":
        write_excel_output(
            workbook,
            worksheet,
            Path(args.excel_file),
            headers,
            header_map,
            evaluations,
        )
    else:
        write_google_output(
            google_service,
            spreadsheet_id,
            sheet_name,
            headers,
            header_map,
            evaluations,
        )


def main() -> int:
    """Run the evaluator CLI."""
    configure_logging()
    env = EnvSettings(logger=LOGGER)
    args = build_arg_parser(env).parse_args()

    try:
        validate_args(args)
        master_prompt = read_text_asset(Path(args.master_prompt), "master prompt")
        latex_cv = read_text_asset(Path(args.cv), "LaTeX CV")
        spreadsheet_id = read_google_spreadsheet_id(args.google_sheet_id)
        source = parse_source(args.source, spreadsheet_id, env)

        LOGGER.info("Loading %s input ...", source)
        google_service, workbook, worksheet, sheet_name, headers, rows = (
            load_input_rows(
                args,
                source,
                spreadsheet_id,
            )
        )

        headers, header_map = ensure_output_columns(headers)
        records, skipped_existing = extract_job_records(
            headers,
            rows,
            start_row=args.start_row,
            limit=args.limit,
            reevaluate=args.reevaluate,
        )

        LOGGER.info("Sheet: %s", sheet_name)
        LOGGER.info("Rows queued: %s", len(records))
        if skipped_existing:
            LOGGER.info(
                "Rows skipped because AI Verdict already exists: %s",
                skipped_existing,
            )

        if args.dry_run:
            for record in records[:5]:
                LOGGER.info(
                    "Dry run row %s: %s", record.row_number, record.display_name
                )
            LOGGER.info(
                "Dry run complete. No OpenAI calls were made and nothing was saved."
            )
            return 0

        if not records:
            LOGGER.info("No rows need evaluation. Writing any missing AI headers only.")
            write_outputs(
                args,
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
            model=args.model,
            api_key=api_key,
            timeout=args.timeout,
            retries=args.retries,
            base_delay=args.retry_base_delay,
            max_delay=args.retry_max_delay,
            max_output_tokens=args.max_output_tokens,
        )
        evaluations = evaluate_records(
            records,
            evaluator=evaluator,
            master_prompt=master_prompt,
            latex_cv=latex_cv,
            concurrency=args.concurrency,
            batch_size=args.batch_size,
        )

        LOGGER.info(
            "Writing %s evaluation(s) back to the same sheet ...",
            len(evaluations),
        )
        write_outputs(
            args,
            source,
            spreadsheet_id,
            google_service,
            workbook,
            worksheet,
            sheet_name,
            headers,
            header_map,
            evaluations,
        )
        if source == "excel":
            LOGGER.info(
                "Saved Excel workbook: %s (sheet: %s)", args.excel_file, sheet_name
            )
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
