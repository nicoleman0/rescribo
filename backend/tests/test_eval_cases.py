import json
from pathlib import Path
from typing import Any

import pytest
from eval_builders import _id, batch_data, first_case, keys, write_batch

import eval_cases
import eval_label
from eval_cases import BatchFormatError, Review, ReviewStatus, parse_batch


def test_generated_batch_parses() -> None:
    batch = parse_batch(batch_data())

    assert len(batch.cases) == 14
    assert batch.problems[0].confusable_with == batch.problems[1].id


@pytest.mark.parametrize("kind", ["match", "paraphrase", "confusable"])
def test_listed_problem_cases_must_expect_their_source(kind: str) -> None:
    data = batch_data()
    case = first_case(data, kind)
    case["expected_problem_id"] = data["problems"][1]["id"]

    with pytest.raises(BatchFormatError, match="must expect its source problem"):
        parse_batch(data)


@pytest.mark.parametrize("kind", ["negation", "no_match"])
def test_no_match_kinds_must_expect_nothing(kind: str) -> None:
    data = batch_data()
    case = first_case(data, kind)
    case["expected_problem_id"] = data["problems"][0]["id"]
    case.setdefault("source_problem_id", data["problems"][0]["id"])

    with pytest.raises(BatchFormatError, match="must expect no match"):
        parse_batch(data)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data.update(split="holdout"), "split"),
        (lambda data: data.update(data_source="redacted"), "data_source"),
        (lambda data: data["generator"].pop("model"), "model"),
        (lambda data: data["cases"][0].update(kind="typo"), "unknown case kind"),
        (
            lambda data: first_case(data, "negation").update(source_problem_id=_id()),
            "unknown source",
        ),
        (lambda data: data["cases"][1].update(id=data["cases"][0]["id"]), "unique"),
        (lambda data: data["problems"][0].update(id=data["problems"][0]["id"].upper()), "UUID"),
    ],
)
def test_malformed_batches_fail_loudly(change: Any, message: str) -> None:
    data = batch_data()
    change(data)

    with pytest.raises(BatchFormatError, match=message):
        parse_batch(data)


def test_larger_sample_extends_the_same_sample() -> None:
    batch = parse_batch(batch_data())

    small = eval_cases.sample(batch, seed=7, size=4)
    large = eval_cases.sample(batch, seed=7, size=9)

    assert large[:4] == small


def test_review_marks_batch_usable_only_after_a_clean_sample(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())
    output: list[str] = []

    assert eval_cases.is_usable("practice-test") is False
    status = eval_label.run_review(
        "practice-test", keys("y", "y", "y", "q").__next__, output.append
    )
    assert status is ReviewStatus.IN_PROGRESS

    status = eval_label.run_review("practice-test", keys("y", "q").__next__, output.append)

    assert status is ReviewStatus.USABLE
    assert eval_cases.is_usable("practice-test") is True


def test_wrong_answer_rejects_the_batch_until_it_changes(eval_root: Path) -> None:
    data = batch_data()
    write_batch(eval_root, data)
    output: list[str] = []

    eval_label.run_review("practice-test", keys("y", "n", "y", "y", "q").__next__, output.append)
    status = eval_label.run_review("practice-test", keys("y").__next__, output.append)

    assert status is ReviewStatus.REJECTED
    assert eval_cases.is_usable("practice-test") is False

    data["cases"][0]["report"]["description"] = "Fixed wording."
    write_batch(eval_root, data)
    status = eval_label.run_review(
        "practice-test", keys("y", "y", "y", "y", "q").__next__, output.append
    )

    assert "Starting a new sample" in "\n".join(output)
    assert status is ReviewStatus.USABLE


def test_undo_reverts_the_last_verdict(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())
    output: list[str] = []

    status = eval_label.run_review(
        "practice-test", keys("y", "y", "y", "n", "u", "y", "q").__next__, output.append
    )

    assert status is ReviewStatus.USABLE
    review = eval_cases.load_review("practice-test")
    assert isinstance(review, Review)
    assert [verdict.right for verdict in review.verdicts] == [True] * 4
    assert {verdict.reviewer for verdict in review.verdicts} == {"person"}


def test_editing_a_usable_batch_makes_it_stale(eval_root: Path) -> None:
    data = batch_data()
    write_batch(eval_root, data)
    eval_label.run_review("practice-test", keys("y", "y", "y", "y", "q").__next__, print)

    data["problems"][0]["summary"] = "Changed."
    write_batch(eval_root, data)

    assert eval_cases.is_usable("practice-test") is False


def test_review_refuses_to_start_without_a_sample_size(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())
    (eval_root / "gates.json").write_text(json.dumps({"spot_check_sample_size": None}))

    with pytest.raises(BatchFormatError, match="spot_check_sample_size is not set"):
        eval_label.run_review("practice-test", keys("q").__next__, print)


def test_no_match_case_shows_the_listed_problems() -> None:
    batch = parse_batch(batch_data())
    case = next(case for case in batch.cases if case.kind is eval_cases.CaseKind.NO_MATCH)

    rendered = eval_label.render_case(batch, case, 1, 4)

    assert "missing from the list" in rendered
    assert "  - CSV export drops rows" in rendered
