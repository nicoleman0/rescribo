#!/usr/bin/env python3
"""Generate a synthetic matching evaluation batch through OpenRouter.

Run with `task eval:generate -- --model <id> --split practice --product "<fictional product>"`.
Reads OPENROUTER_API_KEY from `.env`. Writes eval/matching/batches/<batch_id>/batch.json.
"""

import argparse
import hashlib
import json
import secrets
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import Any

import environ
import httpx

from eval_cases import EVAL_ROOT, EXCLUDED_MODEL, CaseKind, Split, batch_directory, parse_batch
from live_check import required_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = EVAL_ROOT / "prompts"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PER_PROBLEM_KINDS = [
    CaseKind.MATCH,
    CaseKind.PARAPHRASE,
    CaseKind.MISSING_CONTEXT,
    CaseKind.MISLEADING_VERSION,
    CaseKind.NEGATION,
]

# Takes system and user prompts and returns the parsed JSON reply.
Complete = Callable[[str, str], dict[str, Any]]


class GenerationError(Exception):
    pass


def prompt_version() -> str:
    digest = hashlib.sha256()
    for path in sorted(PROMPTS.iterdir()):
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()[:12]


def _prompt(name: str, **values: object) -> str:
    return Template((PROMPTS / name).read_text(encoding="utf-8")).substitute(values)


def _texts(items: Any, keys: tuple[str, ...], what: str) -> list[dict[str, str]]:
    if not isinstance(items, list):
        raise GenerationError(f"{what} is not a list")
    for item in items:
        if not isinstance(item, dict) or not all(
            isinstance(item.get(key), str) and item[key].strip() for key in keys
        ):
            raise GenerationError(f"{what} item lacks {', '.join(keys)}")
    return items


def _report(reply: dict[str, Any], key: str) -> dict[str, str]:
    return _texts([reply.get(key)], ("title", "description"), f"report {key!r}")[0]


def generate_batch(
    complete: Complete,
    *,
    model: str,
    split: Split,
    product: str,
    batch_id: str,
    listed_count: int,
    pair_count: int,
    unlisted_count: int,
) -> dict[str, Any]:
    system = _prompt("system.md")
    listing = complete(
        system,
        _prompt(
            "problems.md",
            product=product,
            listed_count=listed_count,
            pair_count=pair_count,
            unlisted_count=unlisted_count,
        ),
    )
    name = listing.get("product_name")
    if not isinstance(name, str) or not name.strip():
        raise GenerationError("problem list lacks product_name")
    # Later prompts reuse the name so every report is about the same product.
    product = f"{name}, {product}"
    drafts = _texts(listing.get("problems"), ("key", "title"), "problems")
    unlisted = _texts(listing.get("unlisted"), ("title", "summary"), "unlisted")
    ids = {draft["key"]: str(uuid.uuid4()) for draft in drafts}
    if len(ids) != len(drafts):
        raise GenerationError("problem keys repeat")
    problems = [
        {
            "id": ids[draft["key"]],
            "title": draft["title"],
            "summary": draft.get("summary") or "",
            "confusable_with": ids.get(draft.get("confusable_with") or ""),
            "linked_reports": [
                {"id": str(uuid.uuid4()), **report}
                for report in _texts(
                    draft.get("linked_reports", []), ("title", "description"), "linked_reports"
                )
            ],
        }
        for draft in drafts
    ]
    by_id = {problem["id"]: problem for problem in problems}
    kinds = json.loads((PROMPTS / "kinds.json").read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = []
    for problem in problems:
        wanted = list(PER_PROBLEM_KINDS)
        sibling = ""
        if problem["confusable_with"]:
            wanted.append(CaseKind.CONFUSABLE)
            sibling = f"Confusable problem: {by_id[problem['confusable_with']]['title']}\n"
        reply = complete(
            system,
            _prompt(
                "reports.md",
                product=product,
                title=problem["title"],
                summary=problem["summary"],
                sibling=sibling,
                other_titles="\n".join(
                    f"- {other['title']}" for other in problems if other is not problem
                ),
                instructions="\n".join(f"- {kinds[kind]}" for kind in wanted),
                keys=", ".join(
                    f'"{kind}": {{"title": "...", "description": "..."}}' for kind in wanted
                ),
            ),
        )
        for kind in wanted:
            expected = None if kind is CaseKind.NEGATION else problem["id"]
            cases.append(
                {
                    "id": str(uuid.uuid4()),
                    "kind": kind.value,
                    "report": _report(reply, kind.value),
                    "source_problem_id": problem["id"],
                    "expected_problem_id": expected,
                }
            )
    reply = complete(
        system,
        _prompt(
            "no_match.md",
            product=product,
            problems="\n".join(
                f"{number}. {item['title']}: {item['summary']}"
                for number, item in enumerate(unlisted, start=1)
            ),
        ),
    )
    reports = _texts(reply.get("reports"), ("title", "description"), "no_match reports")
    if len(reports) != len(unlisted):
        raise GenerationError("no_match reply has the wrong number of reports")
    for item, report in zip(unlisted, reports, strict=True):
        cases.append(
            {
                "id": str(uuid.uuid4()),
                "kind": CaseKind.NO_MATCH.value,
                "report": {"title": report["title"], "description": report["description"]},
                "expected_problem_id": None,
                "unlisted_problem": {"title": item["title"], "summary": item["summary"]},
            }
        )
    batch = {
        "batch_id": batch_id,
        "split": split.value,
        "data_source": "synthetic",
        "generator": {
            "provider": "openrouter",
            "model": model,
            "prompt_version": prompt_version(),
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "problems": problems,
        "cases": cases,
    }
    parse_batch(batch)
    return batch


def openrouter(client: httpx.Client, api_key: str, model: str, usage: list[int]) -> Complete:
    def complete(system: str, user: str) -> dict[str, Any]:
        # One retry: a model occasionally returns malformed JSON.
        for _ in range(2):
            response = client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            body = response.json()
            usage.append(int(body.get("usage", {}).get("total_tokens", 0)))
            try:
                reply = json.loads(body["choices"][0]["message"]["content"])
            except json.JSONDecodeError:
                continue
            if isinstance(reply, dict):
                return reply
        raise GenerationError("model did not return a JSON object twice in a row")

    return complete


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="OpenRouter model id, not Claude or Jev")
    parser.add_argument("--split", required=True, choices=[split.value for split in Split])
    parser.add_argument("--product", required=True, help="one-line fictional product")
    parser.add_argument("--batch-id")
    parser.add_argument("--problems", type=int, default=20)
    parser.add_argument("--pairs", type=int, default=6)
    parser.add_argument("--unlisted", type=int, default=10)
    arguments = parser.parse_args()
    if EXCLUDED_MODEL.search(arguments.model):
        parser.error("the generator must not be the tuning agent's model or the Jev baseline")
    if arguments.pairs * 2 > arguments.problems:
        parser.error("--pairs needs two problems each")
    batch_id = arguments.batch_id or (
        f"{arguments.split}-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(2)}"
    )
    directory = batch_directory(batch_id)
    if directory.exists():
        parser.error(f"{directory} already exists; regenerate under a new batch id")

    environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
    usage: list[int] = []
    with httpx.Client(timeout=300) as client:
        complete = openrouter(
            client, required_environment("OPENROUTER_API_KEY"), arguments.model, usage
        )
        batch = generate_batch(
            complete,
            model=arguments.model,
            split=Split(arguments.split),
            product=arguments.product,
            batch_id=batch_id,
            listed_count=arguments.problems,
            pair_count=arguments.pairs,
            unlisted_count=arguments.unlisted,
        )
    directory.mkdir(parents=True)
    path = directory / "batch.json"
    path.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {path}: {len(batch['cases'])} cases, {sum(usage)} tokens over {len(usage)} calls")
    print(f"Spot-check it with: task eval:label -- {batch_id}")


if __name__ == "__main__":
    main()
