"""Matching evaluation batches: format, loading, and spot-check status.

Format and workflow: eval/matching/README.md. Standard library only.
"""

import hashlib
import json
import random
import re
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

EVAL_ROOT = Path(__file__).resolve().parents[1] / "eval" / "matching"
BATCHES_ROOT = EVAL_ROOT / "batches"
GATES_PATH = EVAL_ROOT / "gates.json"

# The tuning agent is Claude and the evaluation baseline is Jev. Generators and reviewer
# models must be neither.
EXCLUDED_MODEL = re.compile(r"anthropic|claude|typesafe|jev", re.IGNORECASE)
UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
BATCH_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class Split(StrEnum):
    PRACTICE = "practice"
    EXAM = "exam"


class CaseKind(StrEnum):
    MATCH = "match"
    PARAPHRASE = "paraphrase"
    CONFUSABLE = "confusable"
    MISSING_CONTEXT = "missing_context"
    MISLEADING_VERSION = "misleading_version"
    NEGATION = "negation"
    NO_MATCH = "no_match"


# Kinds written about a listed problem but expected to match nothing.
EXPECTS_NO_MATCH = {CaseKind.NEGATION, CaseKind.NO_MATCH}


class BatchFormatError(Exception):
    pass


@dataclass(frozen=True)
class Text:
    title: str
    description: str


@dataclass(frozen=True)
class UnlistedProblem:
    title: str
    summary: str


@dataclass(frozen=True)
class LinkedReport:
    id: str
    title: str
    description: str


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    summary: str
    linked_reports: tuple[LinkedReport, ...]
    confusable_with: str | None


@dataclass(frozen=True)
class Case:
    id: str
    kind: CaseKind
    report: Text
    expected_problem_id: str | None
    # The listed problem the case was written from; None for no_match.
    source_problem_id: str | None
    # The unlisted problem a no_match case was written about.
    unlisted_problem: UnlistedProblem | None


@dataclass(frozen=True)
class Generator:
    provider: str
    model: str
    prompt_version: str
    created_at: str


@dataclass(frozen=True)
class Batch:
    batch_id: str
    split: Split
    data_source: str
    generator: Generator
    problems: tuple[Problem, ...]
    cases: tuple[Case, ...]

    def problem(self, problem_id: str) -> Problem:
        return next(problem for problem in self.problems if problem.id == problem_id)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BatchFormatError(message)


def _string(data: dict[str, Any], key: str, *, empty: bool = False) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise BatchFormatError(f"{key} must be a string")
    _require(empty or bool(value.strip()), f"{key} must not be empty")
    return value


def _uuid(data: dict[str, Any], key: str) -> str:
    value = _string(data, key)
    _require(bool(UUID_PATTERN.match(value)), f"{key} must be a lowercase UUID")
    return value


def _text(data: Any) -> Text:
    _require(isinstance(data, dict), "text must be an object")
    return Text(title=_string(data, "title"), description=_string(data, "description"))


def _unlisted(data: Any) -> UnlistedProblem:
    _require(isinstance(data, dict), "unlisted_problem must be an object")
    return UnlistedProblem(title=_string(data, "title"), summary=_string(data, "summary"))


def _problem(data: Any) -> Problem:
    _require(isinstance(data, dict), "problem must be an object")
    linked = data.get("linked_reports")
    _require(isinstance(linked, list), "linked_reports must be a list")
    return Problem(
        id=_uuid(data, "id"),
        title=_string(data, "title"),
        summary=_string(data, "summary", empty=True),
        linked_reports=tuple(
            LinkedReport(id=_uuid(item, "id"), **vars(_text(item))) for item in linked
        ),
        confusable_with=_uuid(data, "confusable_with") if data.get("confusable_with") else None,
    )


def _case(data: Any) -> Case:
    _require(isinstance(data, dict), "case must be an object")
    _require(data.get("kind") in set(CaseKind), f"unknown case kind {data.get('kind')!r}")
    kind = CaseKind(data["kind"])
    no_match = kind is CaseKind.NO_MATCH
    case = Case(
        id=_uuid(data, "id"),
        kind=kind,
        report=_text(data.get("report")),
        expected_problem_id=(
            None if data.get("expected_problem_id") is None else _uuid(data, "expected_problem_id")
        ),
        source_problem_id=None if no_match else _uuid(data, "source_problem_id"),
        unlisted_problem=_unlisted(data.get("unlisted_problem")) if no_match else None,
    )
    if kind in EXPECTS_NO_MATCH:
        _require(case.expected_problem_id is None, f"{kind} case {case.id} must expect no match")
    else:
        _require(
            case.expected_problem_id == case.source_problem_id,
            f"{kind} case {case.id} must expect its source problem",
        )
    return case


def parse_batch(data: Any) -> Batch:
    _require(isinstance(data, dict), "batch must be an object")
    batch_id = _string(data, "batch_id")
    _require(bool(BATCH_ID_PATTERN.match(batch_id)), "batch_id must be lowercase kebab-case")
    _require(data.get("split") in set(Split), "split must be practice or exam")
    _require(data.get("data_source") == "synthetic", "data_source must be synthetic")
    generator = data.get("generator")
    _require(isinstance(generator, dict), "generator must be an object")
    problems = data.get("problems")
    cases = data.get("cases")
    _require(isinstance(problems, list) and bool(problems), "problems must be a non-empty list")
    _require(isinstance(cases, list) and bool(cases), "cases must be a non-empty list")
    batch = Batch(
        batch_id=batch_id,
        split=Split(data["split"]),
        data_source="synthetic",
        generator=Generator(
            provider=_string(generator, "provider"),
            model=_string(generator, "model"),
            prompt_version=_string(generator, "prompt_version"),
            created_at=_string(generator, "created_at"),
        ),
        problems=tuple(_problem(item) for item in problems),
        cases=tuple(_case(item) for item in cases),
    )
    _check_references(batch)
    return batch


def _check_references(batch: Batch) -> None:
    problem_ids = [problem.id for problem in batch.problems]
    record_ids = [
        *problem_ids,
        *(linked.id for problem in batch.problems for linked in problem.linked_reports),
        *(case.id for case in batch.cases),
    ]
    _require(len(record_ids) == len(set(record_ids)), "ids must be unique within a batch")
    known = set(problem_ids)
    for problem in batch.problems:
        _require(
            problem.confusable_with is None or problem.confusable_with in known,
            f"problem {problem.id} is confusable with an unknown problem",
        )
    for case in batch.cases:
        _require(
            case.source_problem_id is None or case.source_problem_id in known,
            f"case {case.id} names an unknown source problem",
        )


def batch_directory(batch_id: str) -> Path:
    return BATCHES_ROOT / batch_id


def load_batch(batch_id: str) -> Batch:
    path = batch_directory(batch_id) / "batch.json"
    batch = parse_batch(json.loads(path.read_text(encoding="utf-8")))
    _require(batch.batch_id == batch_id, f"{path} declares batch_id {batch.batch_id}")
    return batch


def batch_ids() -> list[str]:
    if not BATCHES_ROOT.exists():
        return []
    return sorted(path.parent.name for path in BATCHES_ROOT.glob("*/batch.json"))


# Spot-check review


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    IN_PROGRESS = "in progress"
    USABLE = "usable"
    REJECTED = "rejected: fix or regenerate"
    # The batch changed after review, so the sample no longer vouches for it.
    STALE = "stale: resample"


PERSON = "person"


@dataclass(frozen=True)
class Verdict:
    case_id: str
    right: bool
    # "person", or "model:<openrouter id>" for a reviewer model.
    reviewer: str
    note: str = ""


@dataclass
class Review:
    seed: int
    batch_sha256: str
    # Ordered so the last verdict can be undone.
    verdicts: list[Verdict]

    def wrong_case_ids(self) -> list[str]:
        return [verdict.case_id for verdict in self.verdicts if not verdict.right]

    def reviewed_case_ids(self) -> set[str]:
        return {verdict.case_id for verdict in self.verdicts}

    def to_json(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "batch_sha256": self.batch_sha256,
            "verdicts": [
                {key: value for key, value in vars(verdict).items() if value != ""}
                for verdict in self.verdicts
            ],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Review:
        return cls(
            seed=int(data["seed"]),
            batch_sha256=str(data["batch_sha256"]),
            verdicts=[
                Verdict(
                    case_id=item["case_id"],
                    right=bool(item["right"]),
                    reviewer=str(item["reviewer"]),
                    note=str(item.get("note", "")),
                )
                for item in data["verdicts"]
            ],
        )


def batch_sha256(batch_id: str) -> str:
    return hashlib.sha256((batch_directory(batch_id) / "batch.json").read_bytes()).hexdigest()


def spot_check_sample_size() -> int:
    """The gate's sample size. The maintainer sets it in gates.json before any review."""
    gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    size = gates.get("spot_check_sample_size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 1:
        raise BatchFormatError(f"spot_check_sample_size is not set in {GATES_PATH}")
    return size


def sample(batch: Batch, seed: int, size: int) -> list[Case]:
    """A prefix of one seeded shuffle, so raising the sample size extends the same sample."""
    cases = sorted(batch.cases, key=lambda case: case.id)
    random.Random(seed).shuffle(cases)
    return cases[:size]


def review_status(batch: Batch, digest: str, review: Review | None, size: int) -> ReviewStatus:
    if review is None or not review.verdicts:
        return ReviewStatus.UNREVIEWED
    if review.batch_sha256 != digest:
        return ReviewStatus.STALE
    if review.wrong_case_ids():
        return ReviewStatus.REJECTED
    reviewed = review.reviewed_case_ids()
    if all(case.id in reviewed for case in sample(batch, review.seed, size)):
        return ReviewStatus.USABLE
    return ReviewStatus.IN_PROGRESS


def open_review(batch: Batch, digest: str, size: int) -> tuple[Review, ReviewStatus]:
    """Resume the batch's review, or start a new sample if there is none or the batch changed.

    A rejected review is returned as is: the batch must change before it is sampled again.
    """
    review = load_review(batch.batch_id)
    status = review_status(batch, digest, review, size)
    if review is None or status in {ReviewStatus.STALE, ReviewStatus.UNREVIEWED}:
        review = Review(seed=secrets.randbits(32), batch_sha256=digest, verdicts=[])
    return review, status


def review_path(batch_id: str) -> Path:
    return batch_directory(batch_id) / "review.json"


def load_review(batch_id: str) -> Review | None:
    path = review_path(batch_id)
    if not path.exists():
        return None
    return Review.from_json(json.loads(path.read_text(encoding="utf-8")))


def save_review(batch_id: str, review: Review) -> None:
    path = review_path(batch_id)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(review.to_json(), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def is_usable(batch_id: str) -> bool:
    """Evaluation scripts call this before reading a batch's cases."""
    status = review_status(
        load_batch(batch_id),
        batch_sha256(batch_id),
        load_review(batch_id),
        spot_check_sample_size(),
    )
    return status is ReviewStatus.USABLE
