#!/usr/bin/env python3
"""Spot-check a random sample of a generated batch.

`task eval:label` lists batches and their status. `task eval:label -- <batch_id>` reviews one.
Keys: y right, n wrong, u undo, q quit. Each key is saved, so a review can resume.
"""

import argparse
import sys
import termios
import textwrap
import tty
from collections.abc import Callable

from eval_cases import (
    EXPECTS_NO_MATCH,
    PERSON,
    Batch,
    BatchFormatError,
    Case,
    CaseKind,
    ReviewStatus,
    Verdict,
    batch_ids,
    batch_sha256,
    load_batch,
    load_review,
    open_review,
    review_status,
    sample,
    save_review,
    spot_check_sample_size,
)

KEYS = "[y] right  [n] wrong  [u] undo  [q] quit"


def _block(text: str, indent: str = "  ") -> str:
    paragraphs = text.strip().splitlines() or [""]
    return "\n".join(
        textwrap.fill(line, width=88, initial_indent=indent, subsequent_indent=indent) or indent
        for line in paragraphs
    )


def render_case(batch: Batch, case: Case, position: int, total: int) -> str:
    lines = [
        f"\n=== Case {position} of {total} · {case.kind} · {batch.batch_id} ===",
        "REPORT",
        _block(case.report.title),
        "",
        _block(case.report.description),
        "",
        "EXPECTED",
    ]
    if case.kind is CaseKind.NO_MATCH:
        assert case.unlisted_problem is not None
        lines += [
            "  No match. Written about a problem missing from the list below:",
            _block(f"{case.unlisted_problem.title}: {case.unlisted_problem.summary}", "    "),
        ]
    elif case.kind in EXPECTS_NO_MATCH:
        assert case.source_problem_id is not None
        source = batch.problem(case.source_problem_id)
        lines.append(f"  No match. Says it does not have: {source.title}")
    else:
        assert case.expected_problem_id is not None
        expected = batch.problem(case.expected_problem_id)
        lines += [_block(expected.title), _block(expected.summary)]
        if case.kind is CaseKind.CONFUSABLE and expected.confusable_with:
            lines.append(
                f"  Not to be confused with: {batch.problem(expected.confusable_with).title}"
            )
    if case.expected_problem_id is None:
        lines += ["", "LISTED PROBLEMS", *(f"  - {problem.title}" for problem in batch.problems)]
    return "\n".join(lines)


def run_review(
    batch_id: str, read_key: Callable[[], str], write: Callable[[str], None]
) -> ReviewStatus:
    batch = load_batch(batch_id)
    digest = batch_sha256(batch_id)
    size = spot_check_sample_size()
    review, status = open_review(batch, digest, size)
    if status is ReviewStatus.REJECTED:
        write(f"{batch_id} is {status}. Wrong cases: {', '.join(review.wrong_case_ids())}")
        return status
    if status is ReviewStatus.STALE:
        write("The batch changed since its review. Starting a new sample.")

    chosen = sample(batch, review.seed, size)
    while True:
        reviewed = review.reviewed_case_ids()
        pending = [case for case in chosen if case.id not in reviewed]
        if pending:
            position = len(chosen) - len(pending) + 1
            write(render_case(batch, pending[0], position, len(chosen)))
            write(f"\nIs the expected answer right?  {KEYS}")
        else:
            status = review_status(batch, digest, review, size)
            write(f"\nSample complete: {status}.  [u] undo  [q] quit")
        key = read_key().lower()
        if key == "q":
            break
        if key == "u":
            if review.verdicts:
                review.verdicts.pop()
                save_review(batch_id, review)
            else:
                write("Nothing to undo.")
        elif key in {"y", "n"} and pending:
            review.verdicts.append(Verdict(pending[0].id, right=key == "y", reviewer=PERSON))
            save_review(batch_id, review)
        else:
            write(KEYS)
    status = review_status(batch, digest, review, size)
    write(f"{batch_id}: {status}")
    return status


def list_batches(write: Callable[[str], None]) -> None:
    size = spot_check_sample_size()
    write(f"Spot-check sample size: {size}")
    write(f"{'batch':<32} {'split':<9} {'cases':>5}  {'status':<28} generator")
    for batch_id in batch_ids():
        batch = load_batch(batch_id)
        status = review_status(batch, batch_sha256(batch_id), load_review(batch_id), size)
        write(
            f"{batch_id:<32} {batch.split:<9} {len(batch.cases):>5}  {status:<28} "
            f"{batch.generator.model}"
        )


def read_terminal_key() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()[:1] or "q"
    descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setcbreak(descriptor)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_id", nargs="?", help="batch to review; omit to list batches")
    arguments = parser.parse_args()
    try:
        if arguments.batch_id is None:
            list_batches(print)
        else:
            run_review(arguments.batch_id, read_terminal_key, print)
    except BatchFormatError as error:
        sys.exit(f"eval:label: {error}")


if __name__ == "__main__":
    main()
