from eval_builders import batch_data

from eval_baseline import metrics
from eval_cases import parse_batch


def test_retrieval_and_ordering_are_scored_separately() -> None:
    batch = parse_batch(batch_data(cases_per_kind=1))
    first, second = (problem.id for problem in batch.problems)
    pools = {
        case.id: ([second, first] if case.kind == "paraphrase" else [first])
        if case.expected_problem_id
        else ([] if case.kind == "no_match" else [first])
        for case in batch.cases
    }

    result = metrics(batch.cases, pools)

    assert result["expected_match"]["recall_at_10"] == {"hits": 5, "total": 5, "rate": 1.0}
    assert result["expected_match"]["top1"]["hits"] == 4
    assert result["by_kind"]["paraphrase"]["top1"]["hits"] == 0
    assert result["no_match"]["false_suggestion"] == {"hits": 1, "total": 2, "rate": 0.5}
