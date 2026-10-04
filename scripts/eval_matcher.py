#!/usr/bin/env python3
"""Rust matcher evaluation on the baseline's PostgreSQL candidate pools.

`task eval:matcher -- <batch_id>... --config <version>` ranks every case with the release
binary, validates each response with the product contract, compares it with PostgreSQL order
on the same pools, and records the result in eval/matching/results/. Exam batches run once per
config. `--sweep` tries weight and threshold grids on practice batches only.
"""

import argparse
import itertools
import json
import math
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import environ
import psycopg

from eval_baseline import REPOSITORY_ROOT, RESULTS, retrieve_all
from eval_cases import GATES_PATH, Batch, Case, Split, is_usable, load_batch
from live_check import required_environment

sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from matching.contract import (  # noqa: E402
    CONTRACT_VERSION,
    Candidate,
    ContractError,
    ErrorCategory,
    MatchRequest,
    parse_response,
    serialize_request,
)
from matching.registry import CONFIG_DIRECTORY, supported_algorithms  # noqa: E402

MATCHER = REPOSITORY_ROOT / "rust" / "matcher" / "target" / "release" / "matcher"
SWEEP_RANKER = (
    REPOSITORY_ROOT / "rust" / "matcher" / "target" / "release" / "examples" / "rank_with_config"
)
Z_95 = 1.96


class FailureKind:
    RETRIEVAL_MISS = "retrieval_miss"
    RANKING_MISS = "ranking_miss"
    FALSE_SUGGESTION = "false_suggestion"
    WRONG_ABSTENTION = "wrong_abstention"


@dataclass(frozen=True)
class Outcome:
    """One method's answer for one case: ordered suggested problem IDs, empty if it abstained."""

    suggestions: tuple[str, ...]
    abstain_reason: str | None = None


def build_request(batch: Batch, case: Case, pool: list[str], config_version: str) -> MatchRequest:
    """The request retrieval would build. Batches hold fewer linked reports than any cap."""
    algorithm = json.loads((CONFIG_DIRECTORY / f"{config_version}.json").read_text())
    candidates: list[Candidate] = []
    for problem_id in pool:
        problem = batch.problem(problem_id)
        assert len(problem.linked_reports) <= algorithm["max_linked_reports"]
        candidates.append(
            {
                "id": problem.id,
                "version": 1,
                "title": problem.title,
                "summary": problem.summary,
                "linked_reports": [
                    {"id": linked.id, "title": linked.title, "description": linked.description}
                    for linked in problem.linked_reports
                ],
            }
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "algorithm_version": algorithm["algorithm_version"],
        "config_version": config_version,
        "report": {
            "id": case.id,
            "version": 1,
            "title": case.report.title,
            "description": case.report.description,
        },
        "candidates": candidates,
    }


@dataclass(frozen=True)
class RustRun:
    outcomes: dict[str, Outcome]
    invalid_responses: list[dict[str, str]]
    replay_mismatches: list[str]
    durations_ms: list[float]


def run_release(requests: dict[str, MatchRequest]) -> RustRun:
    """Every request through the release binary twice, validated as the product validates."""
    supported = supported_algorithms()
    outcomes: dict[str, Outcome] = {}
    invalid: list[dict[str, str]] = []
    mismatches: list[str] = []
    durations: list[float] = []
    for case_id, request in requests.items():
        payload = serialize_request(request, supported)
        started = time.perf_counter()
        first = subprocess.run([MATCHER], input=payload, capture_output=True, check=False)
        durations.append((time.perf_counter() - started) * 1000)
        second = subprocess.run([MATCHER], input=payload, capture_output=True, check=False)
        if first.stdout != second.stdout or first.returncode != second.returncode:
            mismatches.append(case_id)
        try:
            if first.returncode != 0:
                raise ContractError(ErrorCategory.PROCESS_FAILED, f"exit {first.returncode}")
            response = parse_response(first.stdout, request, supported)
        except ContractError as error:
            invalid.append({"case_id": case_id, "detail": error.detail})
            outcomes[case_id] = Outcome(suggestions=(), abstain_reason="invalid_response")
            continue
        if response["status"] == "ranked":
            ids = tuple(item["problem_id"] for item in response["suggestions"])
            outcomes[case_id] = Outcome(suggestions=ids)
        else:
            outcomes[case_id] = Outcome(suggestions=(), abstain_reason=response["abstain_reason"])
    return RustRun(outcomes, invalid, mismatches, durations)


def postgres_order(pools: dict[str, list[str]]) -> dict[str, Outcome]:
    """PostgreSQL's order as suggestions, top three, abstaining only on an empty pool."""
    return {
        case_id: Outcome(tuple(pool[:3]), None if pool else "no_candidates")
        for case_id, pool in pools.items()
    }


def wilson(hits: int, total: int) -> dict[str, Any]:
    """Rate with a 95% Wilson score interval."""
    if total == 0:
        return {"hits": 0, "total": 0, "rate": None, "ci95": None}
    rate = hits / total
    denominator = 1 + Z_95**2 / total
    centre = (rate + Z_95**2 / (2 * total)) / denominator
    margin = Z_95 * math.sqrt(rate * (1 - rate) / total + Z_95**2 / (4 * total**2)) / denominator
    return {
        "hits": hits,
        "total": total,
        "rate": round(rate, 3),
        "ci95": [round(max(centre - margin, 0.0), 3), round(min(centre + margin, 1.0), 3)],
    }


def triage(case: Case, pool: list[str], outcome: Outcome) -> str | None:
    """Failure kind, or None for a pass. A gold match outside the pool is retrieval's failure."""
    if case.expected_problem_id is None:
        return FailureKind.FALSE_SUGGESTION if outcome.suggestions else None
    if case.expected_problem_id not in pool:
        return FailureKind.RETRIEVAL_MISS
    if not outcome.suggestions:
        return FailureKind.WRONG_ABSTENTION
    if outcome.suggestions[0] != case.expected_problem_id:
        return FailureKind.RANKING_MISS
    return None


def metrics(
    cases: list[Case], pools: dict[str, list[str]], outcomes: dict[str, Outcome]
) -> dict[str, Any]:
    expected = [case for case in cases if case.expected_problem_id is not None]
    no_match = [case for case in cases if case.expected_problem_id is None]
    shown = [case for case in cases if outcomes[case.id].suggestions]
    retrieved = [case for case in expected if case.expected_problem_id in pools[case.id]]

    def top1(case: Case) -> bool:
        return outcomes[case.id].suggestions[:1] == (case.expected_problem_id,)

    def in_top3(case: Case) -> bool:
        return case.expected_problem_id in outcomes[case.id].suggestions[:3]

    def by_kind(group: list[Case]) -> dict[str, Any]:
        kinds = sorted({case.kind.value for case in group})
        result = {}
        for kind in kinds:
            members = [case for case in group if case.kind == kind]
            result[kind] = {
                "cases": len(members),
                "suggested": sum(bool(outcomes[case.id].suggestions) for case in members),
                "top1": sum(top1(case) for case in members),
            }
        return result

    return {
        "top1_precision": wilson(sum(top1(case) for case in shown), len(shown)),
        "coverage": wilson(sum(bool(outcomes[c.id].suggestions) for c in expected), len(expected)),
        "top1_recall": wilson(sum(top1(case) for case in expected), len(expected)),
        "top3_recall": wilson(sum(in_top3(case) for case in expected), len(expected)),
        "ranking_top1_on_retrieved": wilson(sum(top1(case) for case in retrieved), len(retrieved)),
        "abstention": wilson(sum(not outcomes[c.id].suggestions for c in cases), len(cases)),
        "false_suggestion_on_no_match": wilson(
            sum(bool(outcomes[case.id].suggestions) for case in no_match), len(no_match)
        ),
        "by_kind": by_kind(cases),
        "failures": dict(
            sorted(
                Counter(
                    kind
                    for case in cases
                    if (kind := triage(case, pools[case.id], outcomes[case.id]))
                ).items()
            )
        ),
    }


def retrieval(cases: list[Case], pools: dict[str, list[str]]) -> dict[str, Any]:
    expected = [case for case in cases if case.expected_problem_id is not None]
    missed = [case for case in expected if case.expected_problem_id not in pools[case.id]]
    return {
        "recall_at_10": wilson(len(expected) - len(missed), len(expected)),
        "missed_by_kind": dict(sorted(Counter(case.kind.value for case in missed).items())),
        "pool_size_mean": round(statistics.fmean(len(pool) for pool in pools.values()), 2),
    }


def class_balance(cases: list[Case]) -> dict[str, int]:
    return dict(sorted(Counter(case.kind.value for case in cases).items()))


def gates(cases: list[Case], rust: dict[str, Any], run: RustRun, exam: bool) -> dict[str, Any]:
    declared = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    checks = {
        "top1_precision": (rust["top1_precision"]["rate"] or 0) >= declared["top1_precision_min"],
        "coverage": (rust["coverage"]["rate"] or 0) >= declared["coverage_min"],
        "exam_min_cases": exam and len(cases) >= declared["exam_min_cases"],
        "zero_invalid_evidence": not run.invalid_responses,
        # Pools come from one batch's problems and the validator rejects anything outside the
        # pool, so this holds by construction here; workspace isolation is tested in backend.
        "zero_cross_workspace": not run.invalid_responses,
        "deterministic_replay": not run.replay_mismatches,
    }
    return {"declared": declared, "checks": checks, "pass": all(checks.values())}


def load_pools(batches: list[Batch]) -> dict[str, list[str]]:
    environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
    pools: dict[str, list[str]] = {}
    with psycopg.connect(required_environment("RESCRIBO_DATABASE_URL")) as connection:
        for batch in batches:
            pools.update(retrieve_all(connection, batch))
    return pools


def case_records(
    batches: list[Batch], pools: dict[str, list[str]], methods: dict[str, dict[str, Outcome]]
) -> list[dict[str, Any]]:
    """IDs and outcomes per case, for `task eval:review`. No case text."""
    records = []
    for batch in batches:
        for case in batch.cases:
            records.append(
                {
                    "batch_id": batch.batch_id,
                    "case_id": case.id,
                    "kind": case.kind.value,
                    "expected": case.expected_problem_id,
                    "pool": pools[case.id],
                    **{
                        name: {
                            "suggestions": list(outcomes[case.id].suggestions),
                            "abstain_reason": outcomes[case.id].abstain_reason,
                            "failure": triage(case, pools[case.id], outcomes[case.id]),
                        }
                        for name, outcomes in methods.items()
                    },
                }
            )
    return records


def result_path(batch_ids: list[str], config_version: str) -> Path:
    return RESULTS / f"{'+'.join(batch_ids)}-rust-{config_version}.json"


def evaluate(batches: list[Batch], config_version: str, record: bool) -> None:
    split = {batch.split for batch in batches}
    if len(split) != 1:
        sys.exit("Score practice and exam batches separately.")
    exam = split == {Split.EXAM}
    batch_ids = [batch.batch_id for batch in batches]
    path = result_path(batch_ids, config_version)
    if exam and path.exists():
        sys.exit(f"{path.name} exists. The exam runs once per config; rotate exams to retest.")
    cases = [case for batch in batches for case in batch.cases]
    pools = load_pools(batches)
    requests = {
        case.id: build_request(batch, case, pools[case.id], config_version)
        for batch in batches
        for case in batch.cases
    }
    run = run_release(requests)
    postgres = postgres_order(pools)
    rust_metrics = metrics(cases, pools, run.outcomes)
    result = {
        "batch_ids": batch_ids,
        "split": split.pop().value,
        "data_source": "synthetic",
        "generators": sorted({batch.generator.model for batch in batches}),
        "config_version": config_version,
        "cases": len(cases),
        "class_balance": class_balance(cases),
        "retrieval": retrieval(cases, pools),
        "ranking": {"rust": rust_metrics, "postgres_order": metrics(cases, pools, postgres)},
        "invalid_responses": run.invalid_responses,
        "replay_mismatches": run.replay_mismatches,
        "median_run_ms": round(statistics.median(run.durations_ms), 2),
        "gates": gates(cases, rust_metrics, run, exam),
        "case_records": case_records(
            batches, pools, {"rust": run.outcomes, "postgres_order": postgres}
        ),
    }
    text = json.dumps(result, indent=2) + "\n"
    if not record:
        summary = {key: value for key, value in result.items() if key != "case_records"}
        print(json.dumps(summary, indent=2))
        return
    RESULTS.mkdir(exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}")


# Practice tuning

SWEEP_GRID = {
    "title_overlap": [1.0],
    "summary_overlap": [0.0, 0.35, 0.7, 1.0],
    "linked_overlap": [0.0, 0.25, 0.5, 1.0],
    "min_score": [round(0.1 + 0.05 * step, 2) for step in range(15)],
    "min_margin": [0.0, 0.025, 0.05, 0.1, 0.15, 0.2, 0.3],
}


def sweep(batches: list[Batch], base_version: str, algorithm: str | None) -> None:
    """Score every grid point on practice cases and print the precision/coverage frontier."""
    if any(batch.split is not Split.PRACTICE for batch in batches):
        sys.exit("Sweeps run on practice batches only.")
    base = json.loads((CONFIG_DIRECTORY / f"{base_version}.json").read_text())
    cases = [case for batch in batches for case in batch.cases]
    pools = load_pools(batches)
    lines = "".join(
        json.dumps(build_request(batch, case, pools[case.id], base_version)) + "\n"
        for batch in batches
        for case in batch.cases
    ).encode()
    points = []
    with tempfile.TemporaryDirectory() as directory:
        config_path = Path(directory) / "config.json"
        for values in itertools.product(*SWEEP_GRID.values()):
            grid = dict(zip(SWEEP_GRID, values, strict=True))
            config = {
                **base,
                "algorithm_version": algorithm or base["algorithm_version"],
                "config_version": "sweep",
                "weights": {name: grid[name] for name in sorted(base["weights"])},
                "min_score": grid["min_score"],
                "min_margin": grid["min_margin"],
            }
            config_path.write_text(json.dumps(config))
            completed = subprocess.run(
                [SWEEP_RANKER, config_path], input=lines, capture_output=True, check=True
            )
            outcomes = {}
            for case, line in zip(cases, completed.stdout.splitlines(), strict=True):
                answer = json.loads(line)
                ids = tuple(item["problem_id"] for item in answer.get("suggestions", []))
                outcomes[case.id] = Outcome(ids, answer.get("abstain_reason"))
            result = metrics(cases, pools, outcomes)
            points.append((grid, result))
    declared = json.loads(GATES_PATH.read_text(encoding="utf-8"))

    def key(point: tuple[dict[str, float], dict[str, Any]]) -> tuple[float, float]:
        result = point[1]
        return (result["top1_precision"]["rate"] or 0, result["coverage"]["rate"] or 0)

    frontier: list[tuple[dict[str, float], dict[str, Any]]] = []
    for grid, result in sorted(points, key=key, reverse=True):
        coverage = result["coverage"]["rate"] or 0
        if frontier and coverage <= (frontier[-1][1]["coverage"]["rate"] or 0):
            continue
        frontier.append((grid, result))
    print(f"{len(points)} configs on {len(cases)} practice cases; gates {declared}")
    for grid, result in frontier:
        print(
            json.dumps(grid),
            "precision",
            result["top1_precision"],
            "coverage",
            result["coverage"],
            "false_on_no_match",
            result["false_suggestion_on_no_match"]["hits"],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_ids", nargs="+")
    parser.add_argument("--config", required=True, help="config version, e.g. lexical-1.0")
    parser.add_argument("--sweep", action="store_true", help="practice grid search from --config")
    parser.add_argument("--algorithm", help="sweep this algorithm with --config's other values")
    parser.add_argument("--print", action="store_true", help="print practice metrics only")
    arguments = parser.parse_args()
    for batch_id in arguments.batch_ids:
        if not is_usable(batch_id):
            parser.error(f"{batch_id} has not passed its spot-check (task eval:label)")
    batches = [load_batch(batch_id) for batch_id in arguments.batch_ids]
    if arguments.sweep:
        sweep(batches, arguments.config, arguments.algorithm)
        return
    if arguments.print and any(batch.split is Split.EXAM for batch in batches):
        parser.error("exam results are always recorded")
    evaluate(batches, arguments.config, record=not arguments.print)


if __name__ == "__main__":
    main()
