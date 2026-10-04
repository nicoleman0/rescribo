import pytest
from eval_builders import batch_data

from eval_cases import Batch, parse_batch
from eval_matcher import Outcome, build_request, metrics, postgres_order, triage, wilson


def _batch() -> Batch:
    return parse_batch(batch_data(cases_per_kind=1))


def test_triage_tags_each_failure_kind() -> None:
    batch = _batch()
    first, second = (problem.id for problem in batch.problems)
    case = {case.kind.value: case for case in batch.cases}

    assert triage(case["match"], [second], Outcome((second,))) == "retrieval_miss"
    assert triage(case["match"], [second, first], Outcome((second, first))) == "ranking_miss"
    assert triage(case["match"], [first], Outcome((), "below_threshold")) == "wrong_abstention"
    assert triage(case["match"], [first], Outcome((first,))) is None
    assert triage(case["negation"], [first], Outcome((first,))) == "false_suggestion"
    assert triage(case["no_match"], [first], Outcome((), "below_threshold")) is None


def test_metrics_count_no_match_suggestions_against_precision() -> None:
    batch = _batch()
    first, _ = (problem.id for problem in batch.problems)
    cases = list(batch.cases)
    pools = {case.id: [first] for case in cases}
    # Suggest the first problem everywhere: 5 expected cases right, 2 no-match cases wrong.
    outcomes = {case.id: Outcome((first,)) for case in cases}

    result = metrics(cases, pools, outcomes)

    assert result["top1_precision"]["hits"] == 5
    assert result["top1_precision"]["total"] == 7
    assert result["coverage"]["rate"] == 1.0
    assert result["false_suggestion_on_no_match"]["hits"] == 2
    assert result["failures"] == {"false_suggestion": 2}


def test_postgres_order_suggests_the_top_three_and_abstains_only_when_empty() -> None:
    pools = {"a": ["1", "2", "3", "4"], "b": []}

    assert postgres_order(pools) == {
        "a": Outcome(("1", "2", "3")),
        "b": Outcome((), "no_candidates"),
    }


def test_wilson_interval_brackets_the_rate() -> None:
    result = wilson(8, 10)

    assert result["rate"] == 0.8
    low, high = result["ci95"]
    assert low < 0.8 < high
    assert wilson(0, 0)["rate"] is None


def test_request_follows_the_pool_order_and_contract() -> None:
    batch = _batch()
    first, second = (problem.id for problem in batch.problems)
    case = batch.cases[0]

    request = build_request(batch, case, [second, first], "lexical-1.0")

    assert [candidate["id"] for candidate in request["candidates"]] == [second, first]
    assert request["algorithm_version"] == "lexical-1"
    assert request["report"]["id"] == case.id


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_wilson_handles_extremes(value: float) -> None:
    hits = int(value * 20)
    low, high = wilson(hits, 20)["ci95"]
    assert 0.0 <= low <= value <= high <= 1.0
