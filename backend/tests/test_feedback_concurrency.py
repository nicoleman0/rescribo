"""Competing triage decisions on separate PostgreSQL connections."""

import threading
from collections.abc import Callable
from typing import Any

import pytest
from builders import make_membership, make_notification, make_problem, make_report, make_user
from django.db import connection, connections, transaction

from feedback.errors import VersionConflict
from feedback.models import Activity, Report, ReportNotificationOperation
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
    # Report and problem timelines each gain one reassignment entry; the move wrote nothing.
    new_activity = Activity.objects.count() - activity_before
    assert new_activity == 2
    assert not Activity.objects.filter(record_id=second.pk, action="report.linked").exists()
