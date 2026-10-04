from pathlib import Path
from typing import Any

import pytest
from eval_builders import batch_data, keys, write_batch

import eval_cases
from eval_cases import Batch, parse_batch
from eval_review import chosen_records, render, step


def _records(batch: Batch, failing: int) -> list[dict[str, Any]]:
    first = batch.problems[0].id
    kinds = ["ranking_miss", "retrieval_miss", "wrong_abstention", "false_suggestion"]
    return [
        {
            "batch_id": batch.batch_id,
            "case_id": case.id,
            "kind": case.kind.value,
            "expected": case.expected_problem_id,
            "pool": [first],
            "rust": {
                "suggestions": [first],
                "abstain_reason": None,
                "failure": kinds[index % 4] if index < failing else None,
            },
        }
        for index, case in enumerate(batch.cases)
    ]


def test_failures_come_first_in_triage_order_then_sampled_passes() -> None:
    batch = parse_batch(batch_data(cases_per_kind=2))
    records = _records(batch, failing=4)

    chosen = chosen_records(records, "rust", passes=3, seed=1)

    assert [record["rust"]["failure"] for record in chosen[:4]] == [
        "retrieval_miss",
        "ranking_miss",
        "false_suggestion",
        "wrong_abstention",
    ]
    assert len(chosen) == 7
    assert all(record["rust"]["failure"] is None for record in chosen[4:])
    assert chosen == chosen_records(records, "rust", passes=3, seed=1)


def test_render_names_expected_and_suggested_problems() -> None:
    batch = parse_batch(batch_data(cases_per_kind=1))
    record = _records(batch, failing=1)[0]

    text = render(batch, record, "rust", 1, 1)

    assert "ranking_miss" in text
    assert "CSV export times out (pool rank 1)" in text


def test_step_stops_on_q(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = batch_data(cases_per_kind=1)
    write_batch(tmp_path, data)
    monkeypatch.setattr(eval_cases, "BATCHES_ROOT", tmp_path / "batches")
    batch = parse_batch(data)
    result = {"batch_ids": [batch.batch_id], "case_records": _records(batch, failing=3)}
    pressed = keys("n", "q")
    output: list[str] = []

    shown = step(result, "rust", 2, 0, lambda: next(pressed), output.append)

    assert shown == 2
