#!/usr/bin/env python3
"""Jev baseline: evaluation tooling only, never called by the product.

`task eval:jev -- <batch_id>... --run <n>` asks Jev one Choice question per case over the
case's PostgreSQL candidate pool plus "none", and records answers, model version, and cost in
eval/matching/results/. Paid: it prints an estimate and needs --yes to spend.
API: https://openrouter.ai/docs/guides/community/jev-tutorial
"""

import argparse
import json
from pathlib import Path
from typing import Any

import environ
import httpx

from eval_baseline import REPOSITORY_ROOT, RESULTS
from eval_cases import Batch, Case, Split, is_usable, load_batch
from eval_matcher import (
    Outcome,
    case_records,
    class_balance,
    load_pools,
    metrics,
    retrieval,
)
from live_check import required_environment

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
# Pinned; the -latest alias would change under a recorded result.
MODEL = "typesafe/jev-1.13"
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000
TRANSPORT_ATTEMPTS = 3
NONE = "none"
INSTRUCTIONS = (
    "Which existing problem is this customer report about? "
    f"Answer {NONE} if the report is not about any listed problem."
)


def question(batch: Batch, pool: list[str]) -> dict[str, Any]:
    """Keys are pool positions, so problem IDs never reach the model."""
    criteria = {}
    for position, problem_id in enumerate(pool, start=1):
        problem = batch.problem(problem_id)
        criteria[f"p{position}"] = f"{problem.title}. {problem.summary}".strip()
    criteria[NONE] = "None of the listed problems."
    return {"type": "choice", "instructions": INSTRUCTIONS, "criteria": criteria}


def request_body(batch: Batch, case: Case, pool: list[str]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "state": {"report_title": case.report.title, "report": case.report.description},
        "questions": {"problem": question(batch, pool)},
    }


def outcome(answer: dict[str, Any], pool: list[str]) -> Outcome:
    """ "none" abstains; otherwise problems ordered by probability, top three, ties by position."""
    if answer.get("type") != "choice" or answer.get("choice") not in answer["probabilities"]:
        raise ValueError(f"unexpected Jev answer {answer!r}")
    if answer["choice"] == NONE:
        return Outcome(suggestions=(), abstain_reason=NONE)
    ranked = sorted(
        (-answer["probabilities"].get(f"p{position}", 0.0), position)
        for position in range(1, len(pool) + 1)
    )
    chosen = int(answer["choice"].removeprefix("p"))
    order = [chosen] + [position for _, position in ranked if position != chosen]
    return Outcome(suggestions=tuple(pool[position - 1] for position in order[:3]))


def estimate_tokens(bodies: list[dict[str, Any]]) -> int:
    """About four characters per token; the bill comes from the response's usage."""
    return sum(len(json.dumps(body)) for body in bodies) // 4


def ask(client: httpx.Client, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    # A dropped connection costs nothing to retry; an HTTP error is raised at once.
    for attempt in range(TRANSPORT_ATTEMPTS):
        try:
            response = client.post(
                DECISIONS_URL, headers={"Authorization": f"Bearer {api_key}"}, json=body
            )
        except httpx.TransportError:
            if attempt == TRANSPORT_ATTEMPTS - 1:
                raise
            continue
        response.raise_for_status()
        return response.json()
    raise AssertionError("unreachable")


def run(
    batches: list[Batch],
    pools: dict[str, list[str]],
    run_number: int,
    client: httpx.Client,
    api_key: str,
) -> dict[str, Any]:
    outcomes: dict[str, Outcome] = {}
    answers: dict[str, Any] = {}
    models: set[str] = set()
    cost = 0.0
    tokens = 0
    for batch in batches:
        for case in batch.cases:
            pool = pools[case.id]
            if not pool:
                outcomes[case.id] = Outcome(suggestions=(), abstain_reason="no_candidates")
                continue
            reply = ask(client, api_key, request_body(batch, case, pool))
            models.add(reply["model"])
            usage = reply.get("usage", {})
            cost += float(usage.get("cost", 0.0))
            tokens += int(usage.get("input_tokens", 0))
            answer = reply["answers"]["problem"]
            answers[case.id] = answer
            outcomes[case.id] = outcome(answer, pool)
    cases = [case for batch in batches for case in batch.cases]
    return {
        "batch_ids": [batch.batch_id for batch in batches],
        "split": batches[0].split.value,
        "data_source": "synthetic",
        "method": f"{MODEL}, one Choice per case over the PostgreSQL pool plus {NONE}",
        "requested_model": MODEL,
        "served_models": sorted(models),
        "run": run_number,
        "cases": len(cases),
        "class_balance": class_balance(cases),
        "input_tokens": tokens,
        "cost_usd": round(cost, 6),
        "retrieval": retrieval(cases, pools),
        "ranking": {"jev": metrics(cases, pools, outcomes)},
        "answers": answers,
        "case_records": case_records(batches, pools, {"jev": outcomes}),
    }


def result_path(batch_ids: list[str], run_number: int) -> Path:
    return RESULTS / f"{'+'.join(batch_ids)}-jev-1.13-run{run_number}.json"


def agreement(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """Share of cases where both runs gave the same top suggestion or both abstained."""
    one = {record["case_id"]: record["jev"]["suggestions"][:1] for record in first["case_records"]}
    two = {record["case_id"]: record["jev"]["suggestions"][:1] for record in second["case_records"]}
    same = sum(one[case_id] == two[case_id] for case_id in one)
    return {"same_top1_or_abstain": same, "cases": len(one), "rate": round(same / len(one), 3)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_ids", nargs="+")
    parser.add_argument("--run", type=int, required=True, choices=[1, 2])
    parser.add_argument("--limit", type=int, help="first N cases per batch (practice smoke test)")
    parser.add_argument("--yes", action="store_true", help="spend; without it only estimate")
    arguments = parser.parse_args()
    for batch_id in arguments.batch_ids:
        if not is_usable(batch_id):
            parser.error(f"{batch_id} has not passed its spot-check (task eval:label)")
    batches = [load_batch(batch_id) for batch_id in arguments.batch_ids]
    if len({batch.split for batch in batches}) != 1:
        parser.error("score practice and exam batches separately")
    if arguments.limit is not None:
        if batches[0].split is Split.EXAM:
            parser.error("--limit is for practice smoke tests")
        batches = [
            Batch(**{**vars(batch), "cases": batch.cases[: arguments.limit]}) for batch in batches
        ]
    path = result_path(arguments.batch_ids, arguments.run)
    if batches[0].split is Split.EXAM and path.exists():
        parser.error(f"{path.name} exists")
    pools = load_pools(batches)
    bodies = [
        request_body(batch, case, pools[case.id])
        for batch in batches
        for case in batch.cases
        if pools[case.id]
    ]
    tokens = estimate_tokens(bodies)
    print(
        f"{len(bodies)} requests, about {tokens} input tokens, about "
        f"${tokens * PRICE_PER_INPUT_TOKEN:.4f} at {MODEL} list price"
    )
    if not arguments.yes:
        return
    environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
    with httpx.Client(timeout=60) as client:
        result = run(
            batches, pools, arguments.run, client, required_environment("OPENROUTER_API_KEY")
        )
    other = result_path(arguments.batch_ids, 3 - arguments.run)
    if other.exists():
        result["agreement_with_other_run"] = agreement(
            result, json.loads(other.read_text(encoding="utf-8"))
        )
    if arguments.limit is not None:
        summary = {
            key: value for key, value in result.items() if key not in {"answers", "case_records"}
        }
        print(json.dumps(summary, indent=2))
        return
    RESULTS.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}: ${result['cost_usd']}, served {result['served_models']}")


if __name__ == "__main__":
    main()
