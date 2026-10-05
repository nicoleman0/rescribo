"""Workspace and problem locks must not deadlock against member writes.

A member write holds a report or problem lock, then inserts a row whose foreign key needs a
KEY SHARE lock on the workspace or problem. The challenger locks the parent first and the
member's row second. Each test fixes that interleaving and expects both sides to finish.
"""

from typing import Any
from unittest.mock import patch

import pytest
from builders import make_membership, make_problem, make_user
from concurrency import race
from issue_world import World, github_reads

from accounts.models import Membership
from connections.services import disconnect
from feedback.engineering_issues import apply_issue_webhook, link_issue
from feedback.follow_ups import draft_notification
from feedback.models import Activity, FollowUp, Problem, ReportNotificationOperation
from feedback.services import locked_problem, locked_report, write_activity
from operations.github_issue_create import create_draft

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def no_broker() -> Any:
    with patch("feedback.follow_ups.dispatch_task"), patch("operations.dispatch.dispatch_task"):
        yield


def assert_both_finished(outcomes: dict[str, Any]) -> None:
    errors = {name: out for name, out in outcomes.items() if isinstance(out, Exception)}
    assert not errors, f"A side was aborted: {errors!r}"


def record_activity(world: World) -> None:
    write_activity(
        actor=world.actor,
        action=Activity.Action.REPORT_UPDATED,
        record_type=Activity.RecordType.REPORT,
        record_id=world.report.pk,
    )


def hold_report(world: World) -> None:
    locked_report(actor=world.actor, report_id=world.report.pk)


def draft_follow_up(world: World) -> ReportNotificationOperation:
    follow_up = FollowUp.objects.get(report=world.report)
    return draft_notification(actor=world.actor, follow_up_id=follow_up.pk)


def another_issue(world: World) -> dict[str, Any]:
    return {
        **world.github_says(state="open", seconds=30),
        "id": int(world.issue_id) + 1,
        "number": 8,
        "html_url": "https://github.com/acme/widgets/issues/8",
    }


def relink(world: World) -> Any:
    with github_reads(another_issue(world)):
        return link_issue(
            actor=world.actor,
            problem_id=world.problem.pk,
            expected_version=Problem.objects.get(pk=world.problem.pk).version,
            reference="8",
            replace=True,
        )


def test_relinking_an_issue_does_not_deadlock_with_a_member_activity_write() -> None:
    world = World()

    outcomes = race(
        lambda: hold_report(world), lambda: relink(world), then=lambda: record_activity(world)
    )

    assert_both_finished(outcomes)
    assert outcomes["challenger"].number == 8


def test_relinking_an_issue_does_not_deadlock_with_a_member_drafting_a_follow_up() -> None:
    world = World()

    outcomes = race(
        lambda: hold_report(world), lambda: relink(world), then=lambda: draft_follow_up(world)
    )

    assert_both_finished(outcomes)
    assert outcomes["challenger"].number == 8


def test_issue_sync_does_not_deadlock_with_a_member_drafting_a_follow_up() -> None:
    world = World()

    def reopen() -> None:
        with github_reads(world.github_says(state="open", seconds=30)):
            apply_issue_webhook(
                installation_id=world.connection.external_id,
                event=world.event(action="reopened", seconds=30),
            )

    outcomes = race(lambda: hold_report(world), reopen, then=lambda: draft_follow_up(world))

    assert_both_finished(outcomes)
    assert Problem.objects.get(pk=world.problem.pk).state == Problem.State.IN_PROGRESS


def test_issue_draft_does_not_deadlock_with_a_member_editing_the_problem() -> None:
    world = World()
    problem = make_problem(actor=world.actor, title="No issue yet")

    def hold_problem() -> None:
        locked_problem(actor=world.actor, problem_id=problem.pk)

    def record_problem_activity() -> None:
        write_activity(
            actor=world.actor,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
        )

    outcomes = race(
        hold_problem,
        lambda: create_draft(
            actor=world.actor, problem_id=problem.pk, expected_version=problem.version
        ),
        then=record_problem_activity,
    )

    assert_both_finished(outcomes)
    assert outcomes["challenger"].problem_id == problem.pk


def test_disconnecting_does_not_deadlock_with_a_member_activity_write() -> None:
    world = World()
    owner = make_membership(
        workspace=world.actor.workspace,
        user=make_user(email="owner@example.test"),
        role=Membership.Role.OWNER,
    )

    outcomes = race(
        lambda: hold_report(world),
        lambda: disconnect(owner, "github", world.connection.version),
        then=lambda: record_activity(world),
    )

    assert_both_finished(outcomes)
    world.connection.refresh_from_db()
    assert world.connection.status == "disconnected"
