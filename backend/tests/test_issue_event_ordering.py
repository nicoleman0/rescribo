"""Close and reopen deliveries that arrive reversed, and reopen after a sent follow-up."""

import pytest
from builders import make_notification, make_report
from issue_world import World, deliver, github_reads

from feedback.engineering_issues import SYSTEM_ACTOR, sync_issue
from feedback.models import Activity, EngineeringIssue, FollowUp, Problem
from feedback.problems import confirm_fix
from feedback.reports import link_report

pytestmark = pytest.mark.django_db


def test_reopen_processed_before_the_earlier_close_leaves_the_issue_open() -> None:
    world = World()
    closed = world.receipt(action="closed", seconds=10)
    reopened = world.receipt(action="reopened", seconds=20)
    pending = make_notification(report=world.report, state="queued")

    with github_reads(world.github_says(state="open", seconds=20)):
        deliver(reopened)
        deliver(closed)

    world.issue.refresh_from_db()
    world.problem.refresh_from_db()
    pending.refresh_from_db()
    assert world.issue.state == EngineeringIssue.State.OPEN
    assert world.issue.provider_updated_at == world.at(20)
    assert world.problem.state == Problem.State.IN_PROGRESS
    assert pending.state == "cancelled" and pending.invalidation_reason == "issue_reopened"
    closed_flags = Activity.objects.filter(
        record_id=world.problem.pk, metadata__reason="issue_closed"
    )
    assert not closed_flags.exists()


def test_close_processed_before_the_earlier_reopen_leaves_the_issue_closed() -> None:
    world = World()
    reopened = world.receipt(action="reopened", seconds=10)
    closed = world.receipt(action="closed", seconds=20)

    with github_reads(world.github_says(state="closed", seconds=20)):
        deliver(closed)
        deliver(reopened)

    world.issue.refresh_from_db()
    assert world.issue.state == EngineeringIssue.State.CLOSED
    assert world.issue.state_reason == "completed"
    assert world.issue.provider_updated_at == world.at(20)


def test_late_delivery_of_an_event_already_reflected_changes_nothing() -> None:
    world = World()
    closed = world.receipt(action="closed", seconds=10)
    reopened = world.receipt(action="reopened", seconds=20)

    with github_reads(world.github_says(state="open", seconds=20)):
        deliver(reopened)
        world.issue.refresh_from_db()
        problem_after_reopen = Problem.objects.get(pk=world.problem.pk)
        activity_after_reopen = Activity.objects.count()
        deliver(closed)

    world.issue.refresh_from_db()
    problem = Problem.objects.get(pk=world.problem.pk)
    assert problem.version == problem_after_reopen.version
    assert Activity.objects.count() == activity_after_reopen
    assert world.issue.state == EngineeringIssue.State.OPEN


def test_scheduled_sync_after_a_stale_read_does_not_regress_state() -> None:
    world = World()
    with github_reads(world.github_says(state="closed", seconds=20)):
        sync_issue(issue_id=world.issue.pk, actor_system=SYSTEM_ACTOR)
    with github_reads(world.github_says(state="open", seconds=10)):
        sync_issue(issue_id=world.issue.pk, actor_system=SYSTEM_ACTOR)
    world.issue.refresh_from_db()
    assert world.issue.state == EngineeringIssue.State.CLOSED
    assert world.issue.provider_updated_at == world.at(20)


def test_reopen_keeps_sent_history_and_a_later_fix_opens_a_new_revision() -> None:
    world = World()
    other_report = make_report(actor=world.actor, title="Second report")
    link_report(
        actor=world.actor,
        report_id=other_report.pk,
        expected_version=other_report.version,
        problem_id=world.problem.pk,
    )
    assert FollowUp.objects.filter(problem=world.problem).count() == 1  # late report: none yet
    sent = make_notification(report=world.report, state="sent")
    sent_before = sent.updated_at
    reopened = world.receipt(action="reopened", seconds=10)

    with github_reads(world.github_says(state="open", seconds=10)):
        deliver(reopened)

    world.problem.refresh_from_db()
    sent.refresh_from_db()
    assert world.problem.state == Problem.State.IN_PROGRESS
    assert world.problem.resolution_revision == 1
    assert sent.state == "sent" and sent.invalidated_at is None
    assert sent.updated_at == sent_before

    second = confirm_fix(
        actor=world.actor,
        problem_id=world.problem.pk,
        expected_version=world.problem.version,
        fix_note="Fixed properly",
        fix_version="1.0.1",
    )

    sent.refresh_from_db()
    assert second.state == Problem.State.FIX_AVAILABLE and second.resolution_revision == 2
    assert sent.state == "sent" and sent.resolution_revision == 1
    assert sorted(
        FollowUp.objects.filter(report=world.report).values_list("resolution_revision", flat=True)
    ) == [1, 2]
    assert FollowUp.objects.filter(
        problem=world.problem, resolution_revision=2, report=other_report
    ).exists()
