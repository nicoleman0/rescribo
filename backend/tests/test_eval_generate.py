from typing import Any

import pytest

from eval_cases import EXCLUDED_MODEL, CaseKind, Split, parse_batch
from eval_generate import GenerationError, generate_batch


def _report(name: str) -> dict[str, str]:
    return {"title": name, "description": f"{name} details."}


def fake_model(prompts: list[str]) -> Any:
    def complete(_system: str, user: str) -> dict[str, Any]:
        prompts.append(user)
        if user.startswith("Invent a name"):
            return {
                "product_name": "Tally",
                "problems": [
                    {
                        "key": "P1",
                        "title": "Export times out",
                        "summary": "Large exports.",
                        "confusable_with": "P2",
                        "linked_reports": [_report("Hangs")],
                    },
                    {
                        "key": "P2",
                        "title": "Export drops rows",
                        "summary": "Emoji rows.",
                        "confusable_with": "P1",
                        "linked_reports": [],
                    },
                    {
                        "key": "P3",
                        "title": "Invoices show wrong tax",
                        "summary": "",
                        "confusable_with": None,
                    },
                ],
                "unlisted": [{"title": "SSO loop", "summary": "Login repeats."}],
            }
        if user.startswith("Product: Tally, Billing\n\nWrite one new customer report"):
            return {"reports": [_report("Cannot sign in")]}
        return {kind.value: _report(kind.value) for kind in CaseKind}

    return complete


def test_labels_follow_from_how_each_case_was_generated() -> None:
    prompts: list[str] = []

    data = generate_batch(
        fake_model(prompts),
        model="example/model",
        split=Split.EXAM,
        product="Billing",
        batch_id="exam-test",
        listed_count=3,
        pair_count=1,
        unlisted_count=1,
    )

    batch = parse_batch(data)
    kinds = [case.kind for case in batch.cases]
    assert kinds.count(CaseKind.CONFUSABLE) == 2
    assert kinds.count(CaseKind.NO_MATCH) == 1
    assert len(batch.cases) == 3 * 5 + 2 + 1
    assert batch.split is Split.EXAM
    assert batch.generator.model == "example/model"
    assert "Confusable problem: Export drops rows" in prompts[1]
    assert "Confusable problem" not in prompts[3]
    assert all("$" not in prompt for prompt in prompts)


def test_malformed_reply_fails_loudly() -> None:
    def complete(_system: str, _user: str) -> dict[str, Any]:
        return {"product_name": "Tally", "problems": [{"key": "P1"}], "unlisted": []}

    with pytest.raises(GenerationError, match="problems item lacks"):
        generate_batch(
            complete,
            model="m",
            split=Split.PRACTICE,
            product="p",
            batch_id="practice-x",
            listed_count=1,
            pair_count=0,
            unlisted_count=0,
        )


@pytest.mark.parametrize(
    "model", ["anthropic/claude-sonnet-5.5", "typesafe/jev-1.13", "~typesafe/jev-latest"]
)
def test_tuning_and_baseline_models_are_refused(model: str) -> None:
    assert EXCLUDED_MODEL.search(model)


def test_other_models_are_allowed() -> None:
    assert not EXCLUDED_MODEL.search("openai/gpt-5")
