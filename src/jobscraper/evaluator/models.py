"""Domain models and constants for job-fit evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MODEL = "gpt-5-mini"
MAX_CELL_CHARS = 49_000

OUTPUT_COLUMNS = [
    "AI Verdict",
    "AI Fit Score",
    "AI Tailored CV",
]
"""AI columns kept in the final spreadsheet."""

REMOVED_AI_OUTPUT_COLUMNS = [
    "AI Category",
    "AI Reason",
    "AI Raw Verdict",
    "AI Evaluated At",
    "AI Model",
    "AI Error",
]
"""Legacy AI columns removed from the final spreadsheet after evaluation."""

AI_OUTPUT_COLUMNS = OUTPUT_COLUMNS + REMOVED_AI_OUTPUT_COLUMNS
"""All AI output columns, including legacy columns, for prompt filtering."""

DETAIL_COLUMNS = [
    "Job Description",
    "Description",
    "Details",
    "Job Details",
]
"""Job detail/description columns removed from the spreadsheet after evaluation."""

UNHELPFUL_COLUMNS = {
    "application status",
    "applicants",
    "applicant",
    "applicant count",
    "applicants count",
    "number of applicants",
    "num applicants",
    "formatted applicants count",
    "job url",
    "apply url",
}


class EvaluationError(RuntimeError):
    """Raised when a row cannot be evaluated or parsed."""


class OpenAIQuotaError(EvaluationError):
    """Raised when OpenAI reports missing/expired quota or billing."""


class GoogleSheetsError(RuntimeError):
    """Raised when Google Sheets access or update fails."""


@dataclass(frozen=True)
class JobRecord:
    """A worksheet row converted into a job advertisement prompt input."""

    row_number: int
    display_name: str
    advertisement: str


@dataclass
class JobEvaluation:
    """Parsed evaluation result for one worksheet row."""

    row_number: int
    verdict: str
    fit_score: int | None
    reason: str
    raw_verdict: str = ""
    tailored_cv: str = ""
    evaluated_at: str = ""
    model: str = ""
    error: str = ""

    @property
    def category(self) -> str:
        """Return the spreadsheet category derived from the verdict."""
        if self.verdict == "Suitable":
            return "Relevant"
        if self.verdict == "Not Suitable":
            return "Irrelevant"
        return "Error"

    def value_for_column(self, column_name: str) -> Any:
        """Return the output value for a named AI result column."""
        values = {
            "AI Verdict": self.verdict,
            "AI Fit Score": self.fit_score if self.fit_score is not None else "",
            "AI Category": self.category,
            "AI Reason": self.reason,
            "AI Raw Verdict": self.raw_verdict,
            "AI Tailored CV": self.tailored_cv,
            "AI Evaluated At": self.evaluated_at,
            "AI Model": self.model,
            "AI Error": self.error,
        }
        return sheet_safe(values[column_name])


def sheet_safe(value: Any) -> Any:
    """Convert evaluator output to a safe spreadsheet cell value."""
    if value is None:
        return ""
    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return ""
    if len(text) > MAX_CELL_CHARS:
        text = text[: MAX_CELL_CHARS - 25] + " ... [truncated]"
    if text[0] in "=+-@":
        return "'" + text
    return text
