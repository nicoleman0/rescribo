#!/usr/bin/env python3
"""PostgreSQL text-search baseline for one evaluation batch.

`task eval:baseline -- <batch_id>` records retrieval and ordering metrics in
eval/matching/results/. `--preliminary` prints them for an unreviewed batch without recording.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import environ
import psycopg

from eval_cases import EVAL_ROOT, Batch, Case, is_usable, load_batch
from live_check import required_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RESULTS = EVAL_ROOT / "results"
POOL_SIZE = 10

# Title outweighs summary outweighs linked report text. Report words are OR-ed, because
# plainto_tsquery ANDs every word and a long report would match nothing.
CREATE = "CREATE TEMP TABLE eval_problem (id uuid PRIMARY KEY, document tsvector NOT NULL)"
INSERT = """
INSERT INTO eval_problem (id, document) VALUES (
  %(id)s,
  setweight(to_tsvector('english', %(title)s), 'A')
  || setweight(to_tsvector('english', %(summary)s), 'B')
  || setweight(to_tsvector('english', %(linked)s), 'C')
)
"""
RETRIEVE = """
WITH query AS (
  SELECT replace(plainto_tsquery('english', %(text)s)::text, ' & ', ' | ')::tsquery AS q
)
SELECT id::text FROM eval_problem, query
WHERE document @@ q
ORDER BY ts_rank_cd(document, q) DESC, id ASC
LIMIT %(limit)s
"""


def retrieve_all(connection: psycopg.Connection[Any], batch: Batch) -> dict[str, list[str]]:
    with connection.cursor() as cursor:
        cursor.execute(CREATE)
        for problem in batch.problems:
            linked = "\n".join(
                f"{report.title}\n{report.description}" for report in problem.linked_reports
            )
            cursor.execute(
                INSERT,
                {
                    "id": problem.id,
                    "title": problem.title,
                    "summary": problem.summary,
                    "linked": linked,
                },
            )
        pools: dict[str, list[str]] = {}
        for case in batch.cases:
            text = f"{case.report.title}\n{case.report.description}"
            cursor.execute(RETRIEVE, {"text": text, "limit": POOL_SIZE})
            pools[case.id] = [row[0] for row in cursor.fetchall()]
    connection.rollback()
    return pools


def _rate(hits: int, total: int) -> dict[str, Any]:
    return {"hits": hits, "total": total, "rate": round(hits / total, 3) if total else None}


def metrics(cases: tuple[Case, ...], pools: dict[str, list[str]]) -> dict[str, Any]:
    """Retrieval: is the answer in the pool. Ordering: PostgreSQL's top result as the suggestion."""
    expected = [case for case in cases if case.expected_problem_id is not None]
    no_match = [case for case in cases if case.expected_problem_id is None]

    def summary(group: list[Case]) -> dict[str, Any]:
        return {
            "recall_at_10": _rate(
                sum(case.expected_problem_id in pools[case.id] for case in group), len(group)
            ),
            "top1": _rate(
                sum(pools[case.id][:1] == [case.expected_problem_id] for case in group),
                len(group),
            ),
            "top3": _rate(
                sum(case.expected_problem_id in pools[case.id][:3] for case in group), len(group)
            ),
        }

    by_kind: dict[str, list[Case]] = defaultdict(list)
    for case in expected:
        by_kind[case.kind].append(case)
    return {
        "expected_match": summary(expected),
        "by_kind": {kind: summary(group) for kind, group in sorted(by_kind.items())},
        "no_match": {
            # Without abstention, any retrieved candidate becomes a false suggestion.
            "false_suggestion": _rate(
                sum(bool(pools[case.id]) for case in no_match), len(no_match)
            ),
            "by_kind": {
                kind: _rate(
                    sum(bool(pools[case.id]) for case in no_match if case.kind == kind),
                    sum(case.kind == kind for case in no_match),
                )
                for kind in sorted({case.kind for case in no_match})
            },
        },
        "pool_size": {
            "max": POOL_SIZE,
            "mean": round(sum(len(pool) for pool in pools.values()) / len(pools), 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_id")
    parser.add_argument("--preliminary", action="store_true", help="print only; batch unreviewed")
    arguments = parser.parse_args()
    if not arguments.preliminary and not is_usable(arguments.batch_id):
        parser.error(f"{arguments.batch_id} has not passed its spot-check (task eval:label)")
    batch = load_batch(arguments.batch_id)
    environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
    with psycopg.connect(required_environment("RESCRIBO_DATABASE_URL")) as connection:
        pools = retrieve_all(connection, batch)
        server = connection.info.parameter_status("server_version")
    result = {
        "batch_id": batch.batch_id,
        "split": batch.split.value,
        "method": "postgres text search, english config, OR query, ts_rank_cd, id tie-break",
        "postgres_version": server,
        "cases": len(batch.cases),
        "metrics": metrics(batch.cases, pools),
    }
    text = json.dumps(result, indent=2) + "\n"
    if arguments.preliminary:
        print(text)
        return
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{batch.batch_id}-postgres.json"
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
