"""Tests for evaluator orchestration."""

from __future__ import annotations

from jobscraper.evaluator.models import JobEvaluation, JobRecord
from jobscraper.evaluator.openai_client import RequestPacer, evaluate_records


class FakeEvaluator:
    """Small evaluator double for orchestration tests."""

    model = "test-model"

    def evaluate(
        self,
        record: JobRecord,
        master_prompt: str,
        latex_cv: str,
    ) -> JobEvaluation:
        return JobEvaluation(
            row_number=record.row_number,
            verdict="Suitable",
            fit_score=90,
            reason=f"Evaluated {record.display_name}",
            model=self.model,
        )


def make_records(count: int) -> list[JobRecord]:
    return [
        JobRecord(
            row_number=idx + 2,
            display_name=f"row {idx + 2}",
            advertisement="Job Title: GIS Analyst\nCompany: Acme",
        )
        for idx in range(count)
    ]


def test_evaluate_records_calls_save_callback_for_each_result():
    """Each evaluated row should be made available for immediate persistence."""
    saved_rows: list[int] = []

    results = evaluate_records(
        make_records(3),
        evaluator=FakeEvaluator(),
        master_prompt="Prompt",
        latex_cv="CV",
        concurrency=1,
        batch_size=2,
        large_queue_threshold=200,
        large_queue_sleep_ms=1000,
        on_evaluation=lambda evaluation: saved_rows.append(evaluation.row_number),
    )

    assert saved_rows == [2, 3, 4]
    assert list(results) == [2, 3, 4]


def test_evaluate_records_paces_only_large_queues(monkeypatch):
    """Request pacing should activate only above the configured record threshold."""
    waits: list[float] = []

    def record_wait(self: RequestPacer) -> None:
        waits.append(self.delay_seconds)

    monkeypatch.setattr(RequestPacer, "wait", record_wait)

    evaluate_records(
        make_records(2),
        evaluator=FakeEvaluator(),
        master_prompt="Prompt",
        latex_cv="CV",
        concurrency=1,
        batch_size=2,
        large_queue_threshold=2,
        large_queue_sleep_ms=250,
    )
    assert waits == []

    evaluate_records(
        make_records(3),
        evaluator=FakeEvaluator(),
        master_prompt="Prompt",
        latex_cv="CV",
        concurrency=1,
        batch_size=3,
        large_queue_threshold=2,
        large_queue_sleep_ms=250,
    )

    assert waits == [0.25, 0.25, 0.25]
