#!/usr/bin/env python3
"""Step through a recorded result's failures, then a seeded sample of passes.

`task eval:review -- <result file name> [--method rust] [--passes 10]`. Failures are already
triaged by `eval_matcher.triage`. Keys: any key next, q quit.
"""

import argparse
import json
import random
from collections.abc import Callable, Iterable
from typing import Any

from eval_baseline import RESULTS
from eval_cases import Batch, load_batch
from eval_label import _block, read_terminal_key

FAILURE_ORDER = ["retrieval_miss", "ranking_miss", "false_suggestion", "wrong_abstention"]


def chosen_records(
    records: list[dict[str, Any]], method: str, passes: int, seed: int
) -> list[dict[str, Any]]:
    failures = sorted(
        (record for record in records if record[method]["failure"]),
        key=lambda record: (FAILURE_ORDER.index(record[method]["failure"]), record["case_id"]),
    )
    passed = sorted(
        (record for record in records if not record[method]["failure"]),
        key=lambda record: record["case_id"],
    )
    return failures + random.Random(seed).sample(passed, min(passes, len(passed)))


def render(batch: Batch, record: dict[str, Any], method: str, position: int, total: int) -> str:
    case = next(case for case in batch.cases if case.id == record["case_id"])
    answer = record[method]
    label = answer["failure"] or "pass"

    def title(problem_id: str) -> str:
        rank = record["pool"].index(problem_id) + 1 if problem_id in record["pool"] else None
        return f"{batch.problem(problem_id).title} (pool rank {rank or 'not retrieved'})"

    lines = [
        f"\n=== {position} of {total} · {label} · {case.kind} · {batch.batch_id} ===",
        "REPORT",
        _block(case.report.title),
        "",
        _block(case.report.description),
        "",
        "EXPECTED",
        _block(title(case.expected_problem_id) if case.expected_problem_id else "No match"),
    ]
    if case.expected_problem_id is None and case.source_problem_id:
        lines.append(
            _block(f"Says it does not have: {batch.problem(case.source_problem_id).title}")
        )
    lines += ["", f"{method.upper()} ANSWER"]
    if answer["suggestions"]:
        lines += [
            _block(f"{index}. {title(problem_id)}")
            for index, problem_id in enumerate(answer["suggestions"], start=1)
        ]
    else:
        lines.append(_block(f"Abstained: {answer['abstain_reason']}"))
    return "\n".join(lines)


def step(
    result: dict[str, Any],
    method: str,
    passes: int,
    seed: int,
    read_key: Callable[[], str],
    write: Callable[[str], None],
) -> int:
    """Shows records until the end or q. Returns how many were shown."""
    records = chosen_records(result["case_records"], method, passes, seed)
    batches = {batch_id: load_batch(batch_id) for batch_id in result["batch_ids"]}
    shown = 0
    for position, record in enumerate(records, start=1):
        write(render(batches[record["batch_id"]], record, method, position, len(records)))
        shown += 1
        write("\n[any key] next  [q] quit")
        if read_key().lower() == "q":
            break
    return shown


def methods(records: Iterable[dict[str, Any]]) -> list[str]:
    first = next(iter(records))
    return [key for key, value in first.items() if isinstance(value, dict) and "failure" in value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", help="file name in eval/matching/results/")
    parser.add_argument("--method", default="rust")
    parser.add_argument("--passes", type=int, default=10, help="passing cases to sample")
    parser.add_argument("--seed", type=int, default=0)
    arguments = parser.parse_args()
    result = json.loads((RESULTS / arguments.result).read_text(encoding="utf-8"))
    available = methods(result["case_records"])
    if arguments.method not in available:
        parser.error(f"--method must be one of {available}")
    step(result, arguments.method, arguments.passes, arguments.seed, read_terminal_key, print)


if __name__ == "__main__":
    main()
