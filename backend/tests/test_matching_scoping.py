"""Retrieval and candidate loading read only the report's workspace, even from a corrupt row."""

from uuid import uuid4

import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace

from accounts.models import Membership
from feedback.models import Report
from matching.retrieval import load_candidates, retrieve_candidate_ids

pytestmark = pytest.mark.django_db

TEXT = "CSV export times out on large files"


def owner(tag: str) -> Membership:
    return make_membership(
        workspace=make_workspace(name=tag, slug=f"{tag}-{uuid4().hex[:6]}"),
        user=make_user(email=f"{tag}-{uuid4().hex[:6]}@example.test"),
    )


def test_retrieval_ranks_only_the_reports_workspace() -> None:
    a, b = owner("a"), owner("b")
    own = make_problem(actor=a, title=TEXT)
    make_problem(actor=b, title=TEXT, summary=TEXT)
    report = make_report(actor=a, title=TEXT)

    assert retrieve_candidate_ids(report=report) == [own.pk]


def test_retrieval_ignores_a_foreign_report_attached_to_the_problem() -> None:
    a, b = owner("a"), owner("b")
    problem = make_problem(actor=a, title="Dark mode colours")
    foreign_report = make_report(actor=b, title=TEXT, description=TEXT)
    # Written past the application, which would refuse this link.
    Report.objects.filter(pk=foreign_report.pk).update(problem=problem, triage_state="linked")
    query = make_report(actor=a, title=TEXT)

    assert retrieve_candidate_ids(report=query) == []


def test_candidate_load_never_includes_foreign_problems_or_linked_reports() -> None:
    a, b = owner("a"), owner("b")
    own = make_problem(actor=a, title=TEXT)
    foreign = make_problem(actor=b, title=TEXT)
    foreign_report = make_report(actor=b, title="Foreign linked report")
    Report.objects.filter(pk=foreign_report.pk).update(problem=own, triage_state="linked")

    assert (
        load_candidates(workspace_id=a.workspace_id, problem_ids=[foreign.pk], max_linked_reports=5)
        is None
    )
    loaded = load_candidates(
        workspace_id=a.workspace_id, problem_ids=[own.pk], max_linked_reports=5
    )
    assert loaded is not None
    assert loaded.candidates[0]["linked_reports"] == []
