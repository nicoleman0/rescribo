from typing import Any

import httpx
import pytest
from eval_builders import batch_data

import eval_jev
from eval_cases import Batch, parse_batch
from eval_matcher import Outcome


def _batch() -> Batch:
    return parse_batch(batch_data(cases_per_kind=1))


def test_question_hides_problem_ids_and_offers_none() -> None:
    batch = _batch()
    first, second = (problem.id for problem in batch.problems)

    question = eval_jev.question(batch, [second, first])

    assert list(question["criteria"]) == ["p1", "p2", "none"]
    assert question["criteria"]["p1"].startswith("CSV export drops rows")
    assert first not in str(question) and second not in str(question)


def test_outcome_puts_the_choice_first_then_orders_by_probability() -> None:
    pool = ["a", "b", "c", "d"]
    answer = {
        "type": "choice",
        "choice": "p3",
        "probabilities": {"p1": 0.1, "p2": 0.3, "p3": 0.3, "p4": 0.2, "none": 0.1},
    }

    assert eval_jev.outcome(answer, pool) == Outcome(("c", "b", "d"))


def test_none_abstains_and_unknown_answers_fail() -> None:
    pool = ["a"]
    none = {"type": "choice", "choice": "none", "probabilities": {"p1": 0.2, "none": 0.8}}

    assert eval_jev.outcome(none, pool) == Outcome((), "none")
    with pytest.raises(ValueError):
        eval_jev.outcome({"type": "choice", "choice": "p9", "probabilities": {}}, pool)


def test_run_records_served_model_cost_and_metrics() -> None:
    batch = _batch()
    first, _ = (problem.id for problem in batch.problems)
    pools = {case.id: [first] for case in batch.cases}
    sent = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(
            200,
            json={
                "model": "typesafe/jev-1.13-20260917",
                "answers": {
                    "problem": {
                        "type": "choice",
                        "choice": "p1",
                        "confidence": 0.9,
                        "probabilities": {"p1": 0.95, "none": 0.05},
                    }
                },
                "usage": {"input_tokens": 100, "output_tokens": 5, "cost": 0.0000042},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = eval_jev.run([batch], pools, 1, client, "key")

    assert len(sent) == len(batch.cases)
    assert sent[0].url == eval_jev.DECISIONS_URL
    assert result["served_models"] == ["typesafe/jev-1.13-20260917"]
    assert result["input_tokens"] == 100 * len(batch.cases)
    assert result["ranking"]["jev"]["false_suggestion_on_no_match"]["hits"] == 2


def test_agreement_compares_top_answers() -> None:
    def records(*tops: list[str]) -> dict[str, Any]:
        return {
            "case_records": [
                {"case_id": str(index), "jev": {"suggestions": top}}
                for index, top in enumerate(tops)
            ]
        }

    result = eval_jev.agreement(records(["a"], [], ["b"]), records(["a"], [], ["c"]))

    assert result == {"same_top1_or_abstain": 2, "cases": 3, "rate": 0.667}


def test_ask_retries_a_dropped_connection_then_gives_up() -> None:
    attempts = []

    def drop(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ConnectError("dropped")
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(drop)) as client:
        assert eval_jev.ask(client, "key", {}) == {"ok": True}

    def always_drop(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dropped")

    with httpx.Client(transport=httpx.MockTransport(always_drop)) as client:
        with pytest.raises(httpx.ConnectError):
            eval_jev.ask(client, "key", {})
