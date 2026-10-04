from pathlib import Path
from typing import Any

import pytest
from eval_builders import batch_data, write_batch

import eval_cases
import eval_label
from eval_cases import ReviewStatus
from eval_review_model import ReviewerError, review_with_model


def replies(*answers: bool) -> Any:
    remaining = list(answers)
    prompts: list[str] = []

    def complete(_system: str, user: str) -> dict[str, Any]:
        prompts.append(user)
        return {"right": remaining.pop(0), "reason": "Fits the expected problem."}

    complete.prompts = prompts  # type: ignore[attr-defined]
    return complete


def test_model_verdicts_are_recorded_with_the_reviewer(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())
    complete = replies(True, True, True, True)
    output: list[str] = []

    status = review_with_model("practice-test", "google/gemini-3.8-flash", complete, output.append)

    assert status is ReviewStatus.USABLE
    review = eval_cases.load_review("practice-test")
    assert review is not None
    assert {verdict.reviewer for verdict in review.verdicts} == {"model:google/gemini-3.8-flash"}
    assert all(verdict.note for verdict in review.verdicts)
    assert "Listed problems:\n- CSV export times out: Exports over" in complete.prompts[0]
    # Output names cases only, never their text.
    assert not any("Details." in line or "CSV" in line for line in output)


def test_a_wrong_verdict_rejects_the_batch(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())

    status = review_with_model(
        "practice-test", "x-ai/grok-4.7", replies(True, False, True, True), print
    )

    assert status is ReviewStatus.REJECTED


def test_model_review_resumes_a_human_review(eval_root: Path) -> None:
    write_batch(eval_root, batch_data())
    eval_label.run_review("practice-test", iter(["y", "q"]).__next__, print)
    complete = replies(True, True, True)

    assert (
        review_with_model("practice-test", "x-ai/grok-4.7", complete, print) is ReviewStatus.USABLE
    )
    review = eval_cases.load_review("practice-test")
    assert review is not None
    assert [verdict.reviewer for verdict in review.verdicts][0] == "person"


@pytest.mark.parametrize(
    "model", ["anthropic/claude-opus-5.5", "typesafe/jev-1.13", "example/model"]
)
def test_reviewer_must_be_independent(eval_root: Path, model: str) -> None:
    write_batch(eval_root, batch_data())

    with pytest.raises(ReviewerError):
        review_with_model("practice-test", model, replies(), print)
    assert not (eval_root / "batches" / "practice-test" / "review.json").exists()
