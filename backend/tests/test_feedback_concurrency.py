"""Competing triage decisions on separate PostgreSQL connections."""

import threading
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from builders import make_membership, make_notification, make_problem, make_report, make_user
from django.db import connection, connections, transaction
from django.utils import timezone

from feedback.errors import VersionConflict
from feedback.follow_ups import correct_outcome, record_outcome
from feedback.models import Activity, FollowUp, Problem, Report, ReportNotificationOperation
from feedback.problems import confirm_fix
from feedback.reports import assign_report, link_report

pytestmark = pytest.mark.django_db(transaction=True)

WAIT_SECONDS = 10


def backend_pid() -> int:
    connection.ensure_connection()
    return int(connection.connection.info.backend_pid)


def waiting_on_lock(pid: int) -> bool:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
        row = cursor.fetchone()
    return row is not None and row[0] == "Lock"


@pytest.mark.parametrize("correct", [False, True])
def test_still_affected_and_fix_confirmation_share_lock_order(correct: bool) -> None:
    from feedback import problems

    actor = make_membership(role="owner")
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed",
        fix_version="1.0",
    )
    follow_up = FollowUp.objects.get(report=report)
    if correct:
        FollowUp.objects.filter(pk=follow_up.pk).update(
            contact_state=FollowUp.ContactState.CONTACTED,
            outcome_at=timezone.now(),
            outcome_by=actor,
        )
    problem.refresh_from_db()
    Problem.objects.filter(pk=problem.pk).update(state=Problem.State.IN_PROGRESS)
    holder_locked = threading.Event()
    release_holder = threading.Event()
    challenger_pid: list[int] = []
    outcomes: dict[str, Any] = {}
    original_lock = problems.locked_problem

    def hold_problem(**kwargs: Any) -> Problem:
        row = original_lock(**kwargs)
        holder_locked.set()
        if not release_holder.wait(WAIT_SECONDS):
            raise TimeoutError("The outcome never queued behind the problem lock.")
        return row

    def run(name: str, work: Callable[[], Any]) -> None:
        try:
            outcomes[name] = work()
        except Exception as error:
            outcomes[name] = error
        finally:
            connection.close()

    def challenger() -> FollowUp:
        challenger_pid.append(backend_pid())
        if not holder_locked.wait(WAIT_SECONDS):
            raise TimeoutError("Fix confirmation never locked the problem.")
        if correct:
            return correct_outcome(
                actor=actor,
                follow_up_id=follow_up.pk,
                state="still_affected",
                note="The customer still sees the failure.",
                expected_version=follow_up.version,
                reason="Customer reported the failure again.",
            )
        return record_outcome(
            actor=actor,
            follow_up_id=follow_up.pk,
            state="still_affected",
            note="The customer still sees the failure.",
            expected_version=follow_up.version,
        )

    with patch.object(problems, "locked_problem", side_effect=hold_problem):
        threads = [
            threading.Thread(
                target=run,
                args=(
                    "confirmation",
                    lambda: confirm_fix(
                        actor=actor,
                        problem_id=problem.pk,
                        expected_version=problem.version,
                        fix_note="Fixed again",
                        fix_version="2.0",
                    ),
                ),
            ),
            threading.Thread(target=run, args=("outcome", challenger)),
        ]
        for thread in threads:
            thread.start()
        holder_locked.wait(WAIT_SECONDS)
        queued = threading.Event()
        try:
            for _ in range(WAIT_SECONDS * 100):
                if challenger_pid and waiting_on_lock(challenger_pid[0]):
                    queued.set()
                    break
                queued.wait(0.01)
        finally:
            release_holder.set()
            for thread in threads:
                thread.join(WAIT_SECONDS)

    assert all(not thread.is_alive() for thread in threads)
    assert queued.is_set(), "The outcome did not wait for fix confirmation."
    assert isinstance(outcomes["confirmation"], Problem), outcomes
    assert isinstance(outcomes["outcome"], FollowUp), outcomes
    follow_up.refresh_from_db()
    problem.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.STILL_AFFECTED
    assert problem.resolution_revision == 2
    assert problem.needs_review is True


def test_one_expected_version_admits_one_decision() -> None:
    actor = make_membership()
    other = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
    first = make_problem(actor=actor, title="First")
    second = make_problem(actor=actor, title="Second")
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=first.pk)
    report.refresh_from_db()
    pending = make_notification(report=report)
    activity_before = Activity.objects.count()

    holder_locked = threading.Event()
    release_holder = threading.Event()
    challenger_pid: list[int] = []
    outcomes: dict[str, Any] = {}

    def run(name: str, work: Callable[[], Any]) -> None:
        try:
            outcomes[name] = work()
        except Exception as error:
            outcomes[name] = error
        finally:
            connection.close()

    def holder() -> Report:
        with transaction.atomic():
            result = assign_report(
                actor=actor, report_id=report.pk, expected_version=2, assignee_id=other.pk
            )
            holder_locked.set()
            if not release_holder.wait(WAIT_SECONDS):
                raise TimeoutError("The challenger never queued behind the report lock.")
            return result

    def challenger() -> Report:
        challenger_pid.append(backend_pid())
        if not holder_locked.wait(WAIT_SECONDS):
            raise TimeoutError("The holder never locked the report.")
        return link_report(
            actor=actor, report_id=report.pk, expected_version=2, problem_id=second.pk
        )

    threads = [
        threading.Thread(target=run, args=("holder", holder)),
        threading.Thread(target=run, args=("challenger", challenger)),
    ]
    for thread in threads:
        thread.start()
    holder_locked.wait(WAIT_SECONDS)
    queued = threading.Event()
    for _ in range(WAIT_SECONDS * 100):
        if challenger_pid and waiting_on_lock(challenger_pid[0]):
            queued.set()
            break
        queued.wait(0.01)
    release_holder.set()
    for thread in threads:
        thread.join(WAIT_SECONDS)

    assert queued.is_set(), "The challenger did not wait on the report row lock."
    assert isinstance(outcomes["holder"], Report)
    assert isinstance(outcomes["challenger"], VersionConflict)
    assert outcomes["challenger"].current.version == 3
    row = Report.objects.get(pk=report.pk)
    assert (row.version, row.problem_id, row.assignee_id) == (3, first.pk, other.pk)
    pending = ReportNotificationOperation.objects.get(pk=pending.pk)
    assert (pending.state, pending.invalidation_reason) == ("cancelled", "reassigned")
    # Report and problem timelines each gain one reassignment entry, plus the
    # follow-up recipient change for the manual report's pending follow-up.
    # The move wrote nothing.
    new_activity = Activity.objects.count() - activity_before
    assert new_activity == 3
    assert not Activity.objects.filter(record_id=second.pk, action="report.linked").exists()


def test_competing_manual_submissions_converge() -> None:
    from uuid import uuid4

    from feedback.models import ReportSource
    from feedback.reports import SubmitResult, submit_report
    from feedback.submissions import ReportSubmission

    actor = make_membership()
    draft = ReportSubmission("Concurrent capture", "", "", "", "", None, uuid4())
    inserted = threading.Event()
    release = threading.Event()
    challenger_pid: list[int] = []
    outcomes: dict[str, Any] = {}

    def run(name: str) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '15s'")
            if name == "holder":
                with transaction.atomic():
                    outcomes[name] = submit_report(actor=actor, submission=draft)
                    inserted.set()
                    if not release.wait(WAIT_SECONDS):
                        raise TimeoutError("Challenger never reached the uniqueness constraint.")
            else:
                challenger_pid.append(backend_pid())
                if not inserted.wait(WAIT_SECONDS):
                    raise TimeoutError("Holder never inserted the source.")
                outcomes[name] = submit_report(actor=actor, submission=draft)
        except Exception as error:
            outcomes[name] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(name,)) for name in ("holder", "challenger")]
    queued = threading.Event()
    try:
        for thread in threads:
            thread.start()
        assert inserted.wait(WAIT_SECONDS)
        for _ in range(WAIT_SECONDS * 100):
            if challenger_pid and waiting_on_lock(challenger_pid[0]):
                queued.set()
                break
            queued.wait(0.01)
    finally:
        release.set()
        for thread in threads:
            thread.join(WAIT_SECONDS * 2)
    assert all(not thread.is_alive() for thread in threads)
    assert queued.is_set(), "Challenger did not compete for the database identity."
    assert isinstance(outcomes["holder"], SubmitResult), outcomes
    assert isinstance(outcomes["challenger"], SubmitResult), outcomes
    assert outcomes["holder"].created and not outcomes["challenger"].created
    assert outcomes["holder"].report.pk == outcomes["challenger"].report.pk
    assert Report.objects.count() == ReportSource.objects.count() == Activity.objects.count() == 1
