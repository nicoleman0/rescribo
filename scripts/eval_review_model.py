#!/usr/bin/env python3
"""Spot-check a batch's sample with a reviewer model through OpenRouter.

Run with `task eval:review-model -- <batch_id> --model <id>`. Verdicts and the model's reasons
go into the batch's review.json beside any human verdicts. Prints counts and case IDs only,
so an agent running it does not see exam text.
"""

import argparse
from collections.abc import Callable
from pathlib import Path
from string import Template

import environ
import httpx

from eval_cases import (
    EVAL_ROOT,
    EXCLUDED_MODEL,
    Batch,
    ReviewStatus,
    Verdict,
    batch_sha256,
    load_batch,
    open_review,
    review_status,
    sample,
    save_review,
    spot_check_sample_size,
)
from eval_generate import Complete, openrouter
from eval_label import render_case
from live_check import required_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROMPT = EVAL_ROOT / "reviewer" / "prompt.md"
SYSTEM = "You are a careful reviewer. Reply with one JSON object and nothing else."


class ReviewerError(Exception):
    pass


def check_reviewer(model: str, batch: Batch) -> None:
    if EXCLUDED_MODEL.search(model):
        raise ReviewerError("the reviewer must not be the tuning agent's model or the Jev baseline")
    if model == batch.generator.model:
        raise ReviewerError("the reviewer must not be the model that generated the batch")


def review_with_model(
    batch_id: str, model: str, complete: Complete, write: Callable[[str], None]
) -> ReviewStatus:
    batch = load_batch(batch_id)
    check_reviewer(model, batch)
    digest = batch_sha256(batch_id)
    size = spot_check_sample_size()
    review, status = open_review(batch, digest, size)
    if status is ReviewStatus.REJECTED:
        write(f"{batch_id} is {status}. Wrong cases: {', '.join(review.wrong_case_ids())}")
        return status
    problems = "\n".join(f"- {problem.title}: {problem.summary}" for problem in batch.problems)
    chosen = sample(batch, review.seed, size)
    pending = [case for case in chosen if case.id not in review.reviewed_case_ids()]
    for position, case in enumerate(pending, start=len(chosen) - len(pending) + 1):
        prompt = Template(PROMPT.read_text(encoding="utf-8")).substitute(
            problems=problems, case=render_case(batch, case, position, len(chosen))
        )
        reply = complete(SYSTEM, prompt)
        right, reason = reply.get("right"), reply.get("reason")
        if not isinstance(right, bool) or not isinstance(reason, str):
            raise ReviewerError(f"reviewer reply for case {case.id} lacks right and reason")
        review.verdicts.append(
            Verdict(case.id, right=right, reviewer=f"model:{model}", note=reason)
        )
        save_review(batch_id, review)
        write(f"{position}/{len(chosen)} {case.id} {'right' if right else 'WRONG'}")
    status = review_status(batch, digest, review, size)
    write(f"{batch_id}: {status}")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_id")
    parser.add_argument(
        "--model", required=True, help="OpenRouter id; not Claude, Jev, or the generator"
    )
    arguments = parser.parse_args()
    environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
    usage: list[int] = []
    with httpx.Client(timeout=300) as client:
        complete = openrouter(
            client, required_environment("OPENROUTER_API_KEY"), arguments.model, usage
        )
        try:
            review_with_model(arguments.batch_id, arguments.model, complete, print)
        except ReviewerError as error:
            parser.exit(1, f"eval:review-model: {error}\n")
        finally:
            print(f"{sum(usage)} tokens over {len(usage)} calls")


if __name__ == "__main__":
    main()
