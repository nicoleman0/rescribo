"""Tests for applying verified GitHub issue and installation webhook events."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from builders import (
    make_connection,
    make_engineering_issue,
    make_membership,
    make_notification,
    make_problem,
    make_report,
)
from django.utils import timezone

from connections.models import Connection
from feedback.engineering_issues import apply_installation_webhook, apply_issue_webhook
from feedback.errors import DeliveryNotReady
from feedback.follow_ups import draft_notification
from feedback.models import Activity, EngineeringIssue, Problem
from feedback.problems import confirm_fix
from feedback.reports import link_report
from integrations.github_app.client import GitHubAPIError
from integrations.github_app.webhooks import InstallationEvent, IssueEvent

pytestmark = pytest.mark.django_db

ISSUE_PAYLOAD: dict[str, Any] = {
    "id": 555,
    "number": 7,
    "title": "Export button does nothing",
    "state": "open",
    "state_reason": None,
    "html_url": "https://github.com/acme/widgets/issues/7",
    "repository_url": "https://api.github.com/repos/acme/widgets",
    "repository": {"id": 999, "full_name": "acme/widgets"},
    "updated_at": "2026-09-20T21:00:00Z",
}

# Older than every fixture fetch's updated_at above, so applying one always looks newer.
STORED_UPDATED_AT = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)


def github_mock(
    *, get_issue: dict[str, Any] | None = None, get_issue_error: Exception | None = None
) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    if get_issue_error is not None:
        client.get_issue.side_effect = get_issue_error
    else:
        client.get_issue.return_value = get_issue if get_issue is not None else dict(ISSUE_PAYLOAD)
    return client


def patched_client(client: MagicMock) -> Any:
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def issue_event(*, action: str, state_reason: str | None = None, updated_at: str) -> IssueEvent:
    return IssueEvent(
        action=action,
        number=7,
        repository="acme/widgets",
        state_reason=state_reason,
        updated_at=updated_at,
        repository_id="999",
        issue_id="555",
    )


def test_closed_event_sets_needs_review_and_keeps_state_reason() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )
    closed = {**ISSUE_PAYLOAD, "state": "closed", "state_reason": "completed"}

    factory = patched_client(github_mock(get_issue=closed))
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="closed", updated_at="2026-09-20T21:05:00Z"),
        )
    finally:
        factory.stop()

    issue.refresh_from_db()
    problem.refresh_from_db()
    assert issue.state == "closed" and issue.state_reason == "completed"
    assert problem.needs_review is True
    assert problem.state == Problem.State.OPEN  # closing never sets fix_available
    activity = Activity.objects.get(record_id=problem.pk, action=Activity.Action.PROBLEM_UPDATED)
    assert activity.actor_system == "github_webhook" and activity.actor_membership is None


def test_closed_as_not_planned_only_sets_needs_review() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )
    closed = {**ISSUE_PAYLOAD, "state": "closed", "state_reason": "not_planned"}

    factory = patched_client(github_mock(get_issue=closed))
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="closed", updated_at="2026-09-20T21:05:00Z"),
        )
    finally:
        factory.stop()

    problem.refresh_from_db()
    assert problem.needs_review is True
    assert problem.state == Problem.State.OPEN


def test_reopened_event_returns_fix_available_problem_to_in_progress() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )
    report = make_report(actor=actor)
    link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=problem.pk
    )
    report.refresh_from_db()
    confirmed = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Shipped",
        fix_version="1.0.0",
    )
    assert confirmed.state == Problem.State.FIX_AVAILABLE
    pending = make_notification(report=report, state="queued")
    sent = make_notification(report=report, state="sent", resolution_revision=9)
    reopen_time = timezone.now() + timedelta(seconds=5)
    reopened = {
        **ISSUE_PAYLOAD,
        "state": "open",
        "state_reason": None,
        "updated_at": reopen_time.isoformat(),
    }

    factory = patched_client(github_mock(get_issue=reopened))
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="reopened", updated_at=reopen_time.isoformat()),
        )
    finally:
        factory.stop()

    problem.refresh_from_db()
    issue.refresh_from_db()
    pending.refresh_from_db()
    sent.refresh_from_db()
    assert issue.state == "open"
    assert problem.state == Problem.State.IN_PROGRESS
    assert problem.needs_review is True
    assert pending.state == "cancelled" and pending.invalidation_reason == "issue_reopened"
    assert sent.state == "sent" and sent.invalidated_at is None
    with pytest.raises(DeliveryNotReady, match="fix_not_confirmed"):
        draft_notification(actor=actor, follow_up_id=pending.follow_up_id)
    activity = Activity.objects.get(
        record_id=problem.pk, action=Activity.Action.PROBLEM_STATE_CHANGED
    )
    assert activity.actor_system == "github_webhook"


def test_stale_delivery_does_not_regress_state_or_timestamp() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    stored_time = timezone.now()
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="closed",
        state_reason="completed",
        provider_updated_at=stored_time,
    )
    problem.fix_confirmed_at = stored_time + timedelta(days=1)
    problem.save(update_fields=["fix_confirmed_at"])
    # GitHub's current answer is now OLDER than what we already stored (a replayed
    # or out-of-order delivery), so the fetch must not roll state backward.
    stale_fetch = {
        **ISSUE_PAYLOAD,
        "state": "open",
        "updated_at": "2020-01-01T00:00:00Z",
    }

    factory = patched_client(github_mock(get_issue=stale_fetch))
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="reopened", updated_at="2020-01-01T00:00:00Z"),
        )
    finally:
        factory.stop()

    issue.refresh_from_db()
    problem.refresh_from_db()
    assert issue.state == "closed" and issue.state_reason == "completed"
    assert issue.provider_updated_at == stored_time
    assert issue.access == EngineeringIssue.Access.OK
    assert issue.last_attempted_sync_at is not None
    assert problem.needs_review is False  # the stale "reopen" was never applied


def test_inaccessible_issue_is_marked_access_lost_not_closed() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="open",
        provider_updated_at=timezone.now(),
    )

    factory = patched_client(github_mock(get_issue_error=GitHubAPIError("issue lookup", 404)))
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="closed", updated_at="2026-09-20T21:05:00Z"),
        )
    finally:
        factory.stop()

    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.INACCESSIBLE
    assert issue.state == "open"  # unchanged: unknown, not closed


def test_unknown_installation_is_a_no_op() -> None:
    apply_issue_webhook(
        installation_id="does-not-exist",
        event=issue_event(action="closed", updated_at="2026-09-20T21:05:00Z"),
    )
    # No connection, no issue, nothing to assert beyond "it did not raise".


def test_untracked_issue_number_is_a_no_op() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)

    factory = patched_client(github_mock())
    try:
        apply_issue_webhook(
            installation_id=connection.external_id,
            event=issue_event(action="closed", updated_at="2026-09-20T21:05:00Z"),
        )
    finally:
        factory.stop()
    # No EngineeringIssue exists for number=7 on this connection; must not crash.


def test_installation_suspended_marks_connection_and_issues() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem, connection=connection, created_by=actor, provider_updated_at=timezone.now()
    )

    apply_installation_webhook(
        installation_id=connection.external_id,
        event=InstallationEvent(
            event="installation", action="suspend", repositories_removed=(), access_lost=True
        ),
    )

    connection.refresh_from_db()
    issue.refresh_from_db()
    assert connection.status == Connection.Status.ERROR
    assert connection.error_code == "installation_suspended"
    assert issue.access == EngineeringIssue.Access.SUSPENDED


def test_installation_deleted_marks_connection_and_issues_access_lost() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem, connection=connection, created_by=actor, provider_updated_at=timezone.now()
    )

    apply_installation_webhook(
        installation_id=connection.external_id,
        event=InstallationEvent(
            event="installation", action="deleted", repositories_removed=(), access_lost=True
        ),
    )

    connection.refresh_from_db()
    issue.refresh_from_db()
    assert connection.status == Connection.Status.ERROR
    assert connection.error_code == "access_lost"
    assert issue.access == EngineeringIssue.Access.ACCESS_LOST


def test_installation_unsuspend_does_not_touch_issues() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace, status=Connection.Status.ERROR)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        access=EngineeringIssue.Access.SUSPENDED,
        provider_updated_at=timezone.now(),
    )

    apply_installation_webhook(
        installation_id=connection.external_id,
        event=InstallationEvent(
            event="installation", action="unsuspend", repositories_removed=(), access_lost=False
        ),
    )

    connection.refresh_from_db()
    issue.refresh_from_db()
    assert connection.status == Connection.Status.ERROR  # untouched; refresh confirms health
    assert issue.access == EngineeringIssue.Access.SUSPENDED
