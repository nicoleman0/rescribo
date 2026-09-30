"""Report grouping, ungrouping, dismissal, and reassignment rules."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import (
    AlreadyLinked,
    FeedbackError,
    InvalidReference,
    InvalidTransition,
    NoChanges,
    TitleRequired,
    VersionConflict,
)
from feedback.models import Activity, Problem, Report, ReportSource
from feedback.problems import confirm_fix
from feedback.reports import (
    assign_report,
    create_problem_and_link_report,
    dismiss_report,
    link_report,
    restore_report,
    unlink_report,
)
from feedback.submissions import SourceSnapshot

pytestmark = pytest.mark.django_db


def slack_source() -> SourceSnapshot:
    return SourceSnapshot(
        "slack", "T1", "C1", "171.1", "https://example.test/msg", "U1", "Author", "snapshot"
    )


def reload(report: Report) -> Report:
    return Report.objects.select_related("source").get(pk=report.pk)


def durable_state(report: Report) -> dict[str, Any]:
    """Every persisted fact a failed or triage action must not disturb."""
    row = reload(report)
    return {
        "report": {f.attname: getattr(row, f.attname) for f in Report._meta.concrete_fields},
        "source": {
            f.attname: getattr(row.source, f.attname) for f in ReportSource._meta.concrete_fields
        },
        "activity": list(Activity.objects.order_by("id").values_list("id", flat=True)),
        "problems": list(Problem.objects.order_by("id").values_list("id", "version")),
    }


def in_state(actor: Membership, state: str, problem: Problem) -> Report:
    report = make_report(actor=actor, source=slack_source())
    if state == "linked":
        link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    elif state == "dismissed":
        dismiss_report(actor=actor, report_id=report.pk, expected_version=1)
    return reload(report)


def problem_timeline(problem_id: UUID) -> list[tuple[str, dict[str, Any]]]:
    rows = Activity.objects.filter(record_type="problem", record_id=problem_id).order_by(
        "created_at", "id"
    )
    return [(row.action, row.metadata) for row in rows]


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        ("new", "link", "linked"),
        ("new", "dismiss", "dismissed"),
        ("new", "restore", InvalidTransition),
        ("new", "unlink", InvalidTransition),
        ("linked", "link_other", "linked"),
        ("linked", "link_same", AlreadyLinked),
        ("linked", "unlink", "new"),
        ("linked", "dismiss", InvalidTransition),
        ("linked", "restore", InvalidTransition),
        ("dismissed", "restore", "new"),
        ("dismissed", "link", InvalidTransition),
        ("dismissed", "dismiss", InvalidTransition),
        ("dismissed", "unlink", InvalidTransition),
    ],
)
def test_report_transition_matrix(state: str, action: str, expected: Any) -> None:
    actor = make_membership()
    first = make_problem(actor=actor, title="First")
    other = make_problem(actor=actor, title="Other")
    report = in_state(actor, state, first)
    version = report.version
    operations: dict[str, Callable[[], Report]] = {
        "link": lambda: link_report(
            actor=actor, report_id=report.pk, expected_version=version, problem_id=first.pk
        ),
        "link_same": lambda: link_report(
            actor=actor, report_id=report.pk, expected_version=version, problem_id=first.pk
        ),
        "link_other": lambda: link_report(
            actor=actor, report_id=report.pk, expected_version=version, problem_id=other.pk
        ),
        "unlink": lambda: unlink_report(actor=actor, report_id=report.pk, expected_version=version),
        "dismiss": lambda: dismiss_report(
            actor=actor, report_id=report.pk, expected_version=version
        ),
        "restore": lambda: restore_report(
            actor=actor, report_id=report.pk, expected_version=version
        ),
    }
    before = durable_state(report)
    if isinstance(expected, str):
        result = operations[action]()
        assert reload(result).triage_state == expected
        assert reload(result).version == version + 1
        assert (reload(result).problem_id is None) == (expected != "linked")
    else:
        with pytest.raises(expected):
            operations[action]()
        assert durable_state(report) == before


def test_two_reports_share_one_problem_created_atomically() -> None:
    actor = make_membership()
    owner = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
    first = make_report(actor=actor, title="First", source=slack_source())
    second = make_report(actor=actor, title="Second")
    linked = create_problem_and_link_report(
        actor=actor,
        report_id=first.pk,
        expected_version=1,
        title="  Exports fail  ",
        summary="Shared cause",
        owner_id=owner.pk,
    )
    problem = Problem.objects.get()
    assert (problem.title, problem.summary, problem.owner_id) == (
        "Exports fail",
        "Shared cause",
        owner.pk,
    )
    assert linked.problem_id == problem.pk and linked.version == 2
    link_report(actor=actor, report_id=second.pk, expected_version=1, problem_id=problem.pk)
    assert set(problem.reports.values_list("title", flat=True)) == {"First", "Second"}
    # Creation and the first link share one timestamp, so compare them as a set.
    timeline = problem_timeline(problem.pk)
    assert sorted(action for action, _ in timeline) == [
        "problem.created",
        "report.linked",
        "report.linked",
    ]
    assert [meta for action, meta in timeline if action == "report.linked"] == [
        {"report_id": str(first.pk), "from_problem_id": None},
        {"report_id": str(second.pk), "from_problem_id": None},
    ]


@pytest.mark.parametrize("failure", ["blank_title", "foreign_owner", "revoked_owner", "stale"])
def test_create_and_link_rolls_back_every_write(failure: str) -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    foreign = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    revoked = make_membership(workspace=actor.workspace, user=make_user(email="r@example.test"))
    Membership.objects.filter(pk=revoked.pk).update(is_active=False, revoked_at=timezone.now())
    arguments: dict[str, Any] = {"title": "Problem", "expected_version": 1}
    expected: type[FeedbackError] = InvalidReference
    if failure == "blank_title":
        arguments["title"], expected = "   ", TitleRequired
    elif failure == "foreign_owner":
        arguments["owner_id"] = foreign.pk
    elif failure == "revoked_owner":
        arguments["owner_id"] = revoked.pk
    else:
        arguments["expected_version"], expected = 2, VersionConflict
    before = durable_state(report)
    with pytest.raises(expected):
        create_problem_and_link_report(actor=actor, report_id=report.pk, **arguments)
    assert durable_state(report) == before
    assert not Problem.objects.exists()


def test_create_and_link_rejects_dismissed_report_before_creating_problem() -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    dismiss_report(actor=actor, report_id=report.pk, expected_version=1)
    before = durable_state(report)
    with pytest.raises(InvalidTransition):
        create_problem_and_link_report(
            actor=actor, report_id=report.pk, expected_version=2, title="Problem"
        )
    assert durable_state(report) == before


def test_create_and_link_moves_a_linked_report_to_the_new_problem() -> None:
    actor = make_membership()
    old = make_problem(actor=actor, title="Old")
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=old.pk)
    moved = create_problem_and_link_report(
        actor=actor, report_id=report.pk, expected_version=2, title="New"
    )
    new = Problem.objects.get(title="New")
    assert moved.problem_id == new.pk and moved.version == 3
    assert problem_timeline(old.pk)[-1] == (
        "report.unlinked",
        {"report_id": str(report.pk), "to_problem_id": str(new.pk)},
    )


def test_triage_preserves_provenance_submitter_and_content() -> None:
    actor = make_membership()
    other = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
    first = make_problem(actor=actor, title="First")
    second = make_problem(actor=actor, title="Second")
    report = make_report(actor=actor, title="Captured", description="Body", source=slack_source())
    kept = {
        "source": {
            f.attname: getattr(report.source, f.attname) for f in ReportSource._meta.concrete_fields
        },
        "report": {
            name: getattr(report, name)
            for name in (
                "title",
                "description",
                "customer_label",
                "customer_contact_reference",
                "affected_version",
                "submitted_by_id",
                "created_at",
            )
        },
    }
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=first.pk)
    assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=other.pk)
    link_report(actor=actor, report_id=report.pk, expected_version=3, problem_id=second.pk)
    unlink_report(actor=actor, report_id=report.pk, expected_version=4)
    dismiss_report(actor=actor, report_id=report.pk, expected_version=5)
    restore_report(actor=actor, report_id=report.pk, expected_version=6)
    row = reload(report)
    assert row.version == 7 and row.triage_state == "new" and row.problem_id is None
    assert {
        f.attname: getattr(row.source, f.attname) for f in ReportSource._meta.concrete_fields
    } == kept["source"]
    assert {name: getattr(row, name) for name in kept["report"]} == kept["report"]


def test_moves_and_ungrouping_stay_on_both_problem_timelines() -> None:
    actor = make_membership()
    first = make_problem(actor=actor, title="First")
    second = make_problem(actor=actor, title="Second")
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=first.pk)
    link_report(actor=actor, report_id=report.pk, expected_version=2, problem_id=second.pk)
    unlink_report(actor=actor, report_id=report.pk, expected_version=3)
    rid = str(report.pk)
    assert problem_timeline(first.pk)[1:] == [
        ("report.linked", {"report_id": rid, "from_problem_id": None}),
        ("report.unlinked", {"report_id": rid, "to_problem_id": str(second.pk)}),
    ]
    assert problem_timeline(second.pk)[1:] == [
        ("report.linked", {"report_id": rid, "from_problem_id": str(first.pk)}),
        ("report.unlinked", {"report_id": rid, "to_problem_id": None}),
    ]
    report_timeline = Activity.objects.filter(record_type="report", record_id=report.pk)
    assert report_timeline.get(action="report.unlinked").metadata == {
        "from_problem_id": str(second.pk)
    }
    assert first.reports.count() == second.reports.count() == 0


def test_reassignment_is_recorded_on_the_current_problem_only_once() -> None:
    actor = make_membership()
    other = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
    problem = make_problem(actor=actor)
    unlinked = make_report(actor=actor, title="Unlinked")
    assign_report(actor=actor, report_id=unlinked.pk, expected_version=1, assignee_id=other.pk)
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=other.pk)
    assign_report(actor=actor, report_id=report.pk, expected_version=3, assignee_id=None)
    assigned = [meta for action, meta in problem_timeline(problem.pk) if "assigned" in action]
    assert assigned == [
        {"report_id": str(report.pk), "from_assignee_id": None, "to_assignee_id": str(other.pk)},
        {"report_id": str(report.pk), "from_assignee_id": str(other.pk), "to_assignee_id": None},
    ]
    assert reload(report).triage_state == "linked"


def test_unchanged_assignment_writes_nothing() -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    assign_report(actor=actor, report_id=report.pk, expected_version=1, assignee_id=actor.pk)
    before = durable_state(report)
    with pytest.raises(NoChanges):
        assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=actor.pk)
    assert durable_state(report) == before


def test_assignment_does_not_need_a_slack_identity_and_null_clears() -> None:
    actor = make_membership()
    member = make_membership(workspace=actor.workspace, user=make_user(email="m@example.test"))
    report = make_report(actor=actor)
    report = assign_report(
        actor=actor, report_id=report.pk, expected_version=1, assignee_id=member.pk
    )
    report = assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=None)
    assert reload(report).assignee_id is None


def test_linking_to_a_fixed_problem_does_not_touch_its_resolution() -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Done",
        fix_version="1.0.0",
    )
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    fixed = Problem.objects.get(pk=problem.pk)
    assert (fixed.state, fixed.resolution_revision, fixed.version, fixed.needs_review) == (
        "fix_available",
        1,
        2,
        False,
    )
    assert not report.notification_operations.exists()


def test_problem_activity_never_contains_report_content() -> None:
    actor = make_membership()
    marker = "sensitive-marker@example.test"
    report = make_report(
        actor=actor,
        title=marker,
        description=marker,
        customer_label=marker,
        customer_contact_reference=marker,
    )
    create_problem_and_link_report(
        actor=actor, report_id=report.pk, expected_version=1, title="Problem"
    )
    unlink_report(actor=actor, report_id=report.pk, expected_version=2)
    assert all(marker not in str(row.metadata) for row in Activity.objects.all())
