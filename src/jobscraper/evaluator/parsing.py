"""Parsing helpers for evaluator worksheet rows and model responses."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobscraper.evaluator.models import (
    AI_OUTPUT_COLUMNS,
    OUTPUT_COLUMNS,
    UNHELPFUL_COLUMNS,
    EvaluationError,
    JobEvaluation,
    JobRecord,
)

LOGGER = logging.getLogger("job_fit_evaluator")

VERDICT_RE = re.compile(r"(?im)^\s*Verdict\s*:\s*(?P<value>.+?)\s*$")
FIT_SCORE_RE = re.compile(r"(?im)^\s*Fit\s+Score\s*:\s*(?P<score>\d{1,3})\s*%")
UNSUITABLE_REASONS_LABEL_RE = re.compile(
    r"(?i)^(?:\d+\.\s*)?unsuitable\s+reasons?\s*:\s*(?P<value>.*)$"
)
CV_SECTION_RE = re.compile(
    r"(?is)\n?\s*(?:\d+\.\s*)?Customized\s+CV\s*\(LaTeX\)\s*:\s*"
)
LATEX_CODE_BLOCK_RE = re.compile(r"(?is)```(?:latex)?\s*(?P<cv>.*?)```")


def normalize_header(value: Any) -> str:
    """Normalize a spreadsheet header for robust lookup."""
    text = "" if value is None else str(value)
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def trim_trailing_blank_headers(headers: list[Any]) -> list[str]:
    """Drop blank header cells after the last meaningful header."""
    last_idx = 0
    for idx, header in enumerate(headers, start=1):
        if str(header or "").strip():
            last_idx = idx
    return [str(header or "").strip() for header in headers[:last_idx]]


def build_header_map(headers: list[str]) -> dict[str, int]:
    """Build a normalized-header to zero-based-index map."""
    header_map: dict[str, int] = {}
    for idx, header in enumerate(headers):
        normalized = normalize_header(header)
        if normalized and normalized not in header_map:
            header_map[normalized] = idx
    return header_map


def ensure_output_columns(headers: list[str]) -> tuple[list[str], dict[str, int]]:
    """Append missing evaluator output columns to an existing header row."""
    updated_headers = list(headers)
    header_map = build_header_map(updated_headers)
    for column in OUTPUT_COLUMNS:
        normalized = normalize_header(column)
        if normalized not in header_map:
            header_map[normalized] = len(updated_headers)
            updated_headers.append(column)
    return updated_headers, header_map


def get_row_value(row: list[Any], idx: int) -> Any:
    """Return a row value by index or an empty string when absent."""
    if idx >= len(row):
        return ""
    value = row[idx]
    return "" if value is None else value


def row_is_empty(row: list[Any]) -> bool:
    """Return true when a worksheet row has no visible values."""
    return not any(str(value or "").strip() for value in row)


def clean_cell_text(value: Any) -> str:
    """Normalize worksheet cell text for prompt construction."""
    if value is None:
        return ""
    text = str(value).strip()
    if text == "N/A":
        return ""
    return re.sub(r"\s+", " ", text)


def include_job_column(header: str) -> bool:
    """Return true when a column is useful for the job advertisement prompt."""
    normalized = normalize_header(header)
    if not normalized:
        return False
    if normalized in UNHELPFUL_COLUMNS:
        return False
    if normalized in {normalize_header(column) for column in AI_OUTPUT_COLUMNS}:
        return False
    return True


def row_to_job_advertisement(headers: list[str], row: list[Any]) -> str:
    """Build the prompt advertisement text from a worksheet row."""
    lines = []
    for idx, header in enumerate(headers):
        if not include_job_column(header):
            continue
        value = clean_cell_text(get_row_value(row, idx))
        if value:
            lines.append(f"{header}: {value}")
    return "\n".join(lines)


def display_name_for_row(headers: list[str], row: list[Any], row_number: int) -> str:
    """Return a concise human-readable label for logging a worksheet row."""
    header_map = build_header_map(headers)
    title_idx = header_map.get("job title")
    if title_idx is None:
        title_idx = header_map.get("title")
    company_idx = header_map.get("company")
    title = (
        clean_cell_text(get_row_value(row, title_idx)) if title_idx is not None else ""
    )
    company = (
        clean_cell_text(get_row_value(row, company_idx))
        if company_idx is not None
        else ""
    )
    label = " / ".join(part for part in (title, company) if part)
    return label or f"row {row_number}"


def extract_job_records(
    headers: list[str],
    rows: list[list[Any]],
    *,
    reevaluate_existing: bool = False,
) -> tuple[list[JobRecord], int]:
    """Extract queued evaluator records from worksheet rows."""
    header_map = build_header_map(headers)
    verdict_idx = header_map.get(normalize_header("AI Verdict"))
    records: list[JobRecord] = []
    skipped_existing = 0

    for offset, row in enumerate(rows, start=2):
        if row_is_empty(row):
            continue

        if (
            not reevaluate_existing
            and verdict_idx is not None
            and clean_cell_text(get_row_value(row, verdict_idx))
            and clean_cell_text(get_row_value(row, verdict_idx)) != "Error"
        ):
            skipped_existing += 1
            continue

        advertisement = row_to_job_advertisement(headers, row)
        if len(advertisement) < 20:
            LOGGER.warning("Skipping row %s because it has no usable job data.", offset)
            continue

        records.append(
            JobRecord(
                row_number=offset,
                display_name=display_name_for_row(headers, row, offset),
                advertisement=advertisement,
            )
        )

    return records, skipped_existing


def read_text_asset(path: Path, label: str) -> str:
    """Read a required prompt or CV text asset from disk."""
    if not path.exists():
        raise EvaluationError(f"Missing {label}: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise EvaluationError(f"{label} is empty: {path}")
    return text


def build_full_prompt(master_prompt: str, job_advertisement: str, latex_cv: str) -> str:
    """Compose the final model prompt for one job record."""
    return "\n\n".join(
        [
            master_prompt.rstrip(),
            "%==================================================\n"
            "% 1. Job Advertisement\n"
            "%==================================================\n\n"
            f"{job_advertisement.strip()}",
            "%==================================================\n"
            "% 2. Master LaTeX CV\n"
            "%==================================================\n\n"
            "```latex\n"
            f"{latex_cv.strip()}\n"
            "```",
        ]
    )


def normalize_verdict(raw_value: str) -> str | None:
    """Normalize a model verdict into the supported output labels."""
    text = raw_value.casefold()
    text_without_negative = re.sub(r"\bnot\s+suitable\b", "", text)
    has_not_suitable = "not suitable" in text or "❌" in raw_value
    has_maybe = "maybe" in text or "⚠" in raw_value
    has_suitable = bool(re.search(r"\bsuitable\b", text_without_negative)) or (
        "✅" in raw_value
    )

    labels = set()
    if has_not_suitable:
        labels.add("Not Suitable")
    if has_maybe:
        labels.add("Maybe")
    if has_suitable:
        labels.add("Suitable")

    if labels == {"Suitable"}:
        return "Suitable"
    if labels in ({"Not Suitable"}, {"Maybe"}):
        return "Not Suitable"
    return None


def extract_tailored_cv(response_text: str) -> str:
    """Extract the optional tailored LaTeX CV section from a model response."""
    parts = CV_SECTION_RE.split(response_text, maxsplit=1)
    if len(parts) == 1:
        return ""

    cv_text = parts[1].strip()
    block = LATEX_CODE_BLOCK_RE.search(cv_text)
    if block:
        return block.group("cv").strip()
    return cv_text


def remove_tailored_cv(response_text: str) -> str:
    """Remove the optional tailored CV section from a model response."""
    return CV_SECTION_RE.split(response_text, maxsplit=1)[0].strip()


def extract_reason(response_text: str) -> str:
    """Extract the human-readable reason from a model response."""
    evaluation_text = remove_tailored_cv(response_text)
    lines = []
    for line in evaluation_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1]:
                lines.append("")
            continue
        if re.match(r"(?i)^(?:\d+\.\s*)?fit evaluation$", stripped):
            continue
        if re.match(r"(?i)^verdict\s*:", stripped):
            continue
        if re.match(r"(?i)^fit\s+score\s*:", stripped):
            continue
        unsuitable_reasons_match = UNSUITABLE_REASONS_LABEL_RE.match(stripped)
        if unsuitable_reasons_match:
            label_value = unsuitable_reasons_match.group("value").strip()
            if label_value:
                lines.append(label_value)
            continue
        lines.append(line.rstrip())

    return "\n".join(lines).strip()


def extract_unsuitable_reasons(response_text: str) -> str:
    """Extract the labeled reasons for rejecting a not-suitable job."""
    evaluation_text = remove_tailored_cv(response_text)
    lines = []
    collecting = False

    for line in evaluation_text.splitlines():
        stripped = line.strip()
        label_match = UNSUITABLE_REASONS_LABEL_RE.match(stripped)
        if label_match:
            collecting = True
            label_value = label_match.group("value").strip()
            if label_value:
                lines.append(label_value)
            continue

        if not collecting:
            continue
        if re.match(r"(?i)^verdict\s*:", stripped):
            break
        if re.match(r"(?i)^fit\s+score\s*:", stripped):
            break
        if not stripped:
            if lines and lines[-1]:
                lines.append("")
            continue
        lines.append(line.rstrip())

    return "\n".join(lines).strip()


def parse_model_response(
    response_text: str,
    *,
    row_number: int,
    model: str,
) -> JobEvaluation:
    """Parse the model response into a structured evaluation."""
    evaluated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    verdict_match = VERDICT_RE.search(response_text)
    score_match = FIT_SCORE_RE.search(response_text)

    if not verdict_match or not score_match:
        return JobEvaluation(
            row_number=row_number,
            verdict="Error",
            fit_score=None,
            reason="",
            evaluated_at=evaluated_at,
            model=model,
            error="Parsing failed: missing required Verdict or Fit Score line.",
        )

    raw_verdict = verdict_match.group("value").strip()
    verdict = normalize_verdict(raw_verdict)
    try:
        score = int(score_match.group("score"))
    except ValueError:
        score = -1

    if verdict is None or not 0 <= score <= 100:
        return JobEvaluation(
            row_number=row_number,
            verdict="Error",
            fit_score=None,
            reason=extract_reason(response_text),
            unsuitable_reasons=extract_unsuitable_reasons(response_text),
            raw_verdict=raw_verdict,
            tailored_cv=extract_tailored_cv(response_text),
            evaluated_at=evaluated_at,
            model=model,
            error="Parsing failed: invalid verdict or score.",
        )

    return JobEvaluation(
        row_number=row_number,
        verdict=verdict,
        fit_score=score,
        reason=extract_reason(response_text),
        unsuitable_reasons=(
            extract_unsuitable_reasons(response_text)
            if verdict == "Not Suitable"
            else ""
        ),
        raw_verdict=raw_verdict,
        tailored_cv=extract_tailored_cv(response_text),
        evaluated_at=evaluated_at,
        model=model,
    )


def get_response_text(response: Any) -> str:
    """Extract text from OpenAI Responses API result shapes."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts).strip()
