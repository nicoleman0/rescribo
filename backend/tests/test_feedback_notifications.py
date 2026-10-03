"""Persisted cancellation of prepared report notifications."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import (
    AlreadyLinked,
    InvalidReference,
    InvalidTransition,
    NoChanges,
    VersionConflict,
)
from feedback.models import Problem, Report, ReportNotificationOperation
from feedback.notifications import invalidate_pending_notifications, stale_reason
from feedback.problems import confirm_fix
from feedback.reports import (
    assign_report,
    create_problem_and_link_report,
    link_report,
    unlink_report,
)

pytestmark = pytest.mark.django_db

Operation = ReportNotificationOperation
FIELDS = [f.attname for f in Operation._meta.concrete_fields]


def snapshot(*rows: ReportNotificationOperation) -> list[dict[str, Any]]:
    fresh = (
        Operation.objects.filter(pk__in=[row.pk for row in rows])
        .order_by("resolution_revision", "created_at")
        .all()
    )
    return [{name: getattr(row, name) for name in FIELDS} for row in fresh]


def linked_report(actor: Membership, problem: Problem, title: str = "Report") -> Report:
    report = make_report(actor=actor, title=title)
    return link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)


def one_of_each(report: Report) -> dict[str, ReportNotificationOperation]:
    """One row per state, each on its own follow-up revision: one active row per follow-up."""
    earlier = timezone.now() - timedelta(days=1)
    rows = {}
    for offset, state in enumerate(("draft", "queued", "failed", "uncertain", "sent", "cancelled")):
        kwargs: dict[str, Any] = {"resolution_revision": 10 + offset}
        if state == "cancelled":
            kwargs.update(invalidated_at=earlier, invalidation_reason="moved")
        rows[state] = make_notification(report=report, state=state, **kwargs)
    return rows


@pytest.fixture
def world() -> dict[str, Any]:
    actor = make_membership()
    other = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
    first = make_problem(actor=actor, title="First")
    second = make_problem(actor=actor, title="Second")
    report = linked_report(actor, first)
    confirm_fix(
        actor=actor,
        problem_id=first.pk,
        expected_version=first.version,
        fix_note="Confirmed for delivery tests.",
        fix_version="1.0",
    )
    report = Report.objects.get(pk=report.pk)
    return {"actor": actor, "other": other, "first": first, "second": second, "report": report}


def reassign(w: dict[str, Any]) -> Report:
    return assign_report(
        actor=w["actor"], report_id=w["report"].pk, expected_version=2, assignee_id=w["other"].pk
    )


def move(w: dict[str, Any]) -> Report:
    return link_report(
        actor=w["actor"], report_id=w["report"].pk, expected_version=2, problem_id=w["second"].pk
    )


def move_to_new(w: dict[str, Any]) -> Report:
    return create_problem_and_link_report(
        actor=w["actor"], report_id=w["report"].pk, expected_version=2, title="New"
    )


def unlink(w: dict[str, Any]) -> Report:
    return unlink_report(actor=w["actor"], report_id=w["report"].pk, expected_version=2)


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (reassign, "reassigned"),
        (move, "moved"),
        (move_to_new, "moved"),
        (unlink, "unlinked"),
    ],
)
def test_triage_changes_cancel_pending_and_keep_history(
    world: dict[str, Any], mutate: Callable[[dict[str, Any]], Report], reason: str
) -> None:
    rows = one_of_each(world["report"])
    kept = {state: snapshot(rows[state])[0] for state in ("sent", "cancelled")}
    uncertain_before = snapshot(rows["uncertain"])[0]
    mutate(world)
    report = Report.objects.get(pk=world["report"].pk)
    for state in ("draft", "queued", "failed"):
        row = Operation.objects.get(pk=rows[state].pk)
        assert row.state == "cancelled" and row.invalidation_reason == reason
        assert row.invalidated_at == report.updated_at
        assert row.problem_id == world["first"].pk and row.report_version == 2
    uncertain = Operation.objects.get(pk=rows["uncertain"].pk)
    assert uncertain.state == "uncertain" and uncertain.invalidation_reason == reason
    unchanged = {"invalidated_at", "invalidation_reason", "updated_at"}
    assert {k: v for k, v in snapshot(uncertain)[0].items() if k not in unchanged} == {
        k: v for k, v in uncertain_before.items() if k not in unchanged
    }
    for state, before in kept.items():
        assert snapshot(rows[state])[0] == before


def test_unrelated_reports_and_workspaces_are_untouched(world: dict[str, Any]) -> None:
    sibling = linked_report(world["actor"], world["first"], "Sibling")
    foreign_actor = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    foreign = linked_report(foreign_actor, make_problem(actor=foreign_actor))
    bystanders = [make_notification(report=sibling), make_notification(report=foreign)]
    before = snapshot(*bystanders)
    make_notification(report=world["report"])
    reassign(world)
    assert snapshot(*bystanders) == before


def test_rejected_actions_cancel_nothing(world: dict[str, Any]) -> None:
    actor, report = world["actor"], world["report"]
    rows = one_of_each(report)
    before = snapshot(*rows.values())
    foreign = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    attempts: list[tuple[type[Exception], Callable[[], Any]]] = [
        (
            NoChanges,
            lambda: assign_report(
                actor=actor, report_id=report.pk, expected_version=2, assignee_id=None
            ),
        ),
        (
            AlreadyLinked,
            lambda: link_report(
                actor=actor, report_id=report.pk, expected_version=2, problem_id=world["first"].pk
            ),
        ),
        (
            VersionConflict,
            lambda: assign_report(
                actor=actor, report_id=report.pk, expected_version=1, assignee_id=actor.pk
            ),
        ),
        (
            VersionConflict,
            lambda: unlink_report(actor=actor, report_id=report.pk, expected_version=1),
        ),
        (
            InvalidReference,
            lambda: assign_report(
                actor=actor, report_id=report.pk, expected_version=2, assignee_id=foreign.pk
            ),
        ),
        (
            InvalidReference,
            lambda: create_problem_and_link_report(
                actor=actor,
                report_id=report.pk,
                expected_version=2,
                title="New",
                owner_id=foreign.pk,
            ),
        ),
    ]
    for error, attempt in attempts:
        with pytest.raises(error):
            attempt()
    assert snapshot(*rows.values()) == before


def test_invalid_transition_cancels_nothing() -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    with pytest.raises(InvalidTransition):
        unlink_report(actor=actor, report_id=report.pk, expected_version=1)
    assert not Operation.objects.exists()


def test_failure_after_cancelling_rolls_the_cancellation_back(world: dict[str, Any]) -> None:
    rows = one_of_each(world["report"])
    before = snapshot(*rows.values())
    with (
        patch("feedback.reports.write_activity", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        reassign(world)
    assert snapshot(*rows.values()) == before
    assert Report.objects.get(pk=world["report"].pk).version == 2


def test_repeated_invalidation_is_harmless(world: dict[str, Any]) -> None:
    rows = one_of_each(world["report"])
    reassign(world)
    after_first = snapshot(*rows.values())
    report = Report.objects.get(pk=world["report"].pk)
    with transaction.atomic():
        changed = invalidate_pending_notifications(
            report=report, reason="unlinked", now=timezone.now()
        )
    assert changed == 0
    assert snapshot(*rows.values()) == after_first


# The default test wrapper is itself a transaction, so this needs autocommit.
@pytest.mark.django_db(transaction=True)
def test_invalidation_requires_the_mutation_transaction(world: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError):
        invalidate_pending_notifications(
            report=world["report"], reason="reassigned", now=timezone.now()
        )


def test_invalidation_rejects_unknown_reasons(world: dict[str, Any]) -> None:
    with transaction.atomic(), pytest.raises(ValueError):
        invalidate_pending_notifications(
            report=world["report"], reason="customer text", now=timezone.now()
        )


def test_stale_preparation_needs_current_data(world: dict[str, Any]) -> None:
    prepared = make_notification(report=world["report"])
    report = Report.objects.select_related("problem").get(pk=world["report"].pk)
    assert stale_reason(operation=prepared, report=report) is None
    reassign(world)
    report = Report.objects.select_related("problem").get(pk=world["report"].pk)
    prepared.refresh_from_db()
    assert stale_reason(operation=prepared, report=report) == "invalidated"
    # Even a row that escaped cancellation is stale once the report version moves on.
    escaped = make_notification(report=report, report_version=2)
    assert stale_reason(operation=escaped, report=report) == "report_changed"
    # A stale draft is cancelled, and the follow-up is drafted again against current data.
    Operation.objects.filter(pk=escaped.pk).update(
        state=Operation.State.CANCELLED,
        invalidated_at=timezone.now(),
        invalidation_reason=Operation.InvalidationReason.MEMBER_CANCELLED,
    )
    fresh = make_notification(report=report)
    assert fresh.recipient_id == world["other"].pk
    assert stale_reason(operation=fresh, report=report) is None
    prepared.refresh_from_db()
    assert prepared.state == "cancelled"


def test_stale_reason_checks_problem_revision_and_recipient(world: dict[str, Any]) -> None:
    report = Report.objects.select_related("problem").get(pk=world["report"].pk)
    other_problem = make_notification(report=report, problem=world["second"], resolution_revision=5)
    assert stale_reason(operation=other_problem, report=report) == "problem_changed"
    old_revision = make_notification(report=report, resolution_revision=4)
    assert stale_reason(operation=old_revision, report=report) == "resolution_changed"
    assert report.problem is not None
    current_revision = report.problem.resolution_revision
    inactive = make_notification(
        report=report,
        resolution_revision=current_revision,
        recipient=world["other"],
    )
    Membership.objects.filter(pk=world["other"].pk).update(
        is_active=False, revoked_at=timezone.now()
    )
    inactive = Operation.objects.select_related("recipient").get(pk=inactive.pk)
    assert stale_reason(operation=inactive, report=report) == "recipient_inactive"
    uncertain = make_notification(report=report, state="uncertain", resolution_revision=3)
    assert stale_reason(operation=uncertain, report=report) == "not_sendable"


@pytest.mark.parametrize(
    "values",
    [
        {"state": "sent", "sent_at": None},
        {"state": "sent", "remote_message_id": ""},
        {"state": "draft", "sent_at": timezone.now()},
        {"state": "cancelled"},
        {"state": "cancelled", "invalidated_at": timezone.now()},
        {"state": "draft", "invalidated_at": timezone.now(), "invalidation_reason": "moved"},
        {"state": "failed", "invalidated_at": timezone.now(), "invalidation_reason": "moved"},
        {"state": "queued", "invalidated_at": timezone.now(), "invalidation_reason": "moved"},
    ],
)
def test_database_rejects_inconsistent_rows(world: dict[str, Any], values: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        make_notification(report=world["report"], **values)


def test_a_manual_delivery_confirmation_satisfies_the_sent_constraint(
    world: dict[str, Any],
) -> None:
    row = make_notification(
        report=world["report"],
        state="sent",
        remote_message_id="",
        delivery_confirmed_by=world["other"],
        delivery_confirmed_at=timezone.now(),
    )
    assert row.state == "sent"


def test_reports_with_notification_history_cannot_be_deleted(world: dict[str, Any]) -> None:
    make_notification(report=world["report"], state="sent")
    with pytest.raises(ProtectedError):
        Report.objects.filter(pk=world["report"].pk).delete()
