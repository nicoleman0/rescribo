"""Small builders for matching evaluation tests."""

import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import eval_cases


def _id() -> str:
    return str(uuid.uuid4())


def batch_data(batch_id: str = "practice-test", cases_per_kind: int = 2) -> dict[str, Any]:
    first, second = _id(), _id()
    problems = [
        {
            "id": first,
            "title": "CSV export times out",
            "summary": "Exports over 10,000 rows hit the gateway timeout.",
            "confusable_with": second,
            "linked_reports": [{"id": _id(), "title": "Export hangs", "description": "Spins."}],
        },
        {
            "id": second,
            "title": "CSV export drops rows",
            "summary": "Rows with emoji are skipped.",
            "confusable_with": first,
            "linked_reports": [],
        },
    ]
    cases: list[dict[str, Any]] = []
    for kind in eval_cases.CaseKind:
        for _ in range(cases_per_kind):
            case: dict[str, Any] = {
                "id": _id(),
                "kind": kind.value,
                "report": {"title": f"{kind} report", "description": "Details."},
            }
            if kind is eval_cases.CaseKind.NO_MATCH:
                case |= {
                    "expected_problem_id": None,
                    "unlisted_problem": {"title": "SSO loop", "summary": "Login repeats."},
                }
            elif kind in eval_cases.EXPECTS_NO_MATCH:
                case |= {"source_problem_id": first, "expected_problem_id": None}
            else:
                case |= {"source_problem_id": first, "expected_problem_id": first}
            cases.append(case)
    return {
        "batch_id": batch_id,
        "split": "practice",
        "data_source": "synthetic",
        "generator": {
            "provider": "openrouter",
            "model": "example/model",
            "prompt_version": "abc123",
            "created_at": "2026-10-03T00:00:00Z",
        },
        "problems": problems,
        "cases": cases,
    }


def write_batch(root: Path, data: dict[str, Any]) -> None:
    directory = root / "batches" / data["batch_id"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "batch.json").write_text(json.dumps(data))


def first_case(data: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(case for case in data["cases"] if case["kind"] == kind)


def keys(*pressed: str) -> Iterator[str]:
    yield from pressed
