"""Tests for durable 15-minute issue sync requests and worker application."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from builders import make_connection, make_engineering_issue, make_membership, make_problem

from connections.models import Connection
from feedback.models import EngineeringIssue
from feedback.tasks import reconcile_github_issues, sync_github_issue
from integrations.github_app.client import GitHubAPIError
from operations.tasks import dispatch_due_operations, revalidate_github_connection

pytestmark = pytest.mark.django_db

ISSUE_PAYLOAD: dict[str, Any] = {
    "id": 555,
    "number": 7,
    "title": "Export button does nothing",
    "state": "closed",
    "state_reason": "completed",
    "html_url": "https://github.com/acme/widgets/issues/7",
    "repository_url": "https://api.github.com/repos/acme/widgets",
    "updated_at": "2026-09-20T21:05:00Z",
}

STORED_UPDATED_AT = datetime(2026, 9, 20, 20, 0, tzinfo=UTC)


def patched_client(*, error: Exception | None = None, stage: str = "get_issue") -> Any:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    client.get_issue.return_value = dict(ISSUE_PAYLOAD)
    if error is not None:
        getattr(client, stage).side_effect = error
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def test_reconcile_persists_and_dispatches_sync_for_active_closed_link() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="closed",
        provider_updated_at=STORED_UPDATED_AT,
    )

    with patch("feedback.tasks.sync_github_issue.delay") as dispatch:
        reconcile_github_issues()

    issue.refresh_from_db()
    assert issue.sync_requested_generation == 1
    dispatch.assert_called_once_with(str(issue.pk))


def test_reconcile_republishes_pending_generation_and_skips_inactive_links() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    active = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )
    old = make_engineering_issue(
        problem=make_problem(actor=actor),
        connection=connection,
        created_by=actor,
        active=False,
        issue_id="556",
        number=8,
        provider_updated_at=STORED_UPDATED_AT,
    )
    active.sync_requested_generation = 1
    active.save(update_fields=["sync_requested_generation"])

    with patch("feedback.tasks.sync_github_issue.delay") as dispatch:
        reconcile_github_issues()

    active.refresh_from_db()
    old.refresh_from_db()
    assert active.sync_requested_generation == 1
    assert old.sync_requested_generation == 0
    dispatch.assert_called_once_with(str(active.pk))


def test_reconcile_skips_connections_that_are_not_active() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace, status=Connection.Status.ERROR)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )

    with patch("feedback.tasks.sync_github_issue.delay") as dispatch:
        reconcile_github_issues()

    issue.refresh_from_db()
    assert issue.sync_requested_generation == 0
    dispatch.assert_not_called()


def test_sync_worker_fetches_and_keeps_last_known_state_on_ambiguous_404() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="open",
        provider_updated_at=STORED_UPDATED_AT,
    )

    factory = patched_client(error=GitHubAPIError("issue lookup", 404))
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()

    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.INACCESSIBLE
    assert issue.state == "open"
    assert issue.last_successful_sync_at is None


def test_sync_worker_applies_closed_state_from_provider() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="open",
        provider_updated_at=STORED_UPDATED_AT,
    )

    factory = patched_client()
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()

    issue.refresh_from_db()
    problem.refresh_from_db()
    assert issue.state == "closed"
    assert issue.last_successful_sync_at is not None
    assert problem.needs_review is True


def test_empty_connection_completes_reconciliation() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    reconcile_github_issues()
    connection.refresh_from_db()
    assert connection.last_reconciled_at is not None


def test_retry_after_is_respected_by_webhook_and_scheduled_sync() -> None:
    from datetime import timedelta

    from django.utils import timezone

    from feedback.engineering_issues import apply_issue_webhook
    from integrations.github_app.webhooks import IssueEvent

    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(problem=problem, connection=connection, created_by=actor)
    issue.sync_retry_at = timezone.now() + timedelta(minutes=10)
    issue.save()
    event = IssueEvent(
        action="closed",
        number=issue.number,
        repository=connection.repository,
        repository_id=issue.repository_id,
        issue_id=issue.issue_id,
        state_reason=None,
        updated_at=timezone.now().isoformat(),
    )
    with patch("feedback.engineering_issues.github_client") as factory:
        sync_github_issue(str(issue.pk))
        apply_issue_webhook(installation_id=connection.external_id, event=event)
    factory.assert_not_called()
    issue.refresh_from_db()
    assert issue.sync_requested_generation > issue.sync_completed_generation


def test_transient_outage_does_not_change_access() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(problem=problem, connection=connection, created_by=actor)
    factory = patched_client(error=GitHubAPIError("lookup", 502))
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()
    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.OK
    assert issue.sync_error == "provider_unavailable"
    assert issue.sync_retry_at is not None


def test_read_timeout_keeps_access_and_schedules_a_retry() -> None:
    import httpx

    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(problem=problem, connection=connection, created_by=actor)
    factory = patched_client(error=httpx.ReadTimeout("read timed out"))
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()
    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.OK
    assert issue.sync_error == "provider_unavailable"
    assert issue.sync_retry_at is not None
    assert issue.sync_lease_token is None


def test_gone_issue_is_inaccessible_and_keeps_last_known_state() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem, connection=connection, created_by=actor, state="open"
    )
    factory = patched_client(error=GitHubAPIError("issue lookup", 410))
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()
    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.INACCESSIBLE
    assert issue.sync_error == "inaccessible"
    assert issue.state == "open"
    assert issue.sync_completed_generation == issue.sync_requested_generation


def test_deleted_issue_webhook_marks_the_link_deleted_without_a_retry() -> None:
    from django.utils import timezone

    from feedback.engineering_issues import apply_issue_webhook
    from integrations.github_app.webhooks import IssueEvent

    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem, connection=connection, created_by=actor, state="open"
    )
    event = IssueEvent(
        action="deleted",
        number=issue.number,
        repository=connection.repository,
        repository_id=issue.repository_id,
        issue_id=issue.issue_id,
        state_reason=None,
        updated_at=timezone.now().isoformat(),
    )
    factory = patched_client(error=GitHubAPIError("issue lookup", 404))
    try:
        apply_issue_webhook(installation_id=connection.external_id, event=event)
    finally:
        factory.stop()
    issue.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.DELETED
    assert issue.state == "open"
    assert issue.sync_retry_at is None
    assert issue.sync_completed_generation == issue.sync_requested_generation


@pytest.mark.parametrize(
    "stage,status,code,access",
    [
        ("create_installation_token", 404, "access_lost", EngineeringIssue.Access.ACCESS_LOST),
        (
            "create_installation_token",
            403,
            "installation_suspended",
            EngineeringIssue.Access.SUSPENDED,
        ),
        ("get_issue", 401, "github_credentials_invalid", EngineeringIssue.Access.ACCESS_LOST),
    ],
)
def test_refused_installation_stops_sync_until_reconnect(
    stage: str, status: int, code: str, access: str
) -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(problem=problem, connection=connection, created_by=actor)
    issue.sync_requested_generation = 1
    issue.save(update_fields=["sync_requested_generation"])
    operation = (
        "installation token creation" if stage == "create_installation_token" else "issue lookup"
    )
    factory = patched_client(error=GitHubAPIError(operation, status), stage=stage)
    try:
        sync_github_issue(str(issue.pk))
    finally:
        factory.stop()

    connection.refresh_from_db()
    issue.refresh_from_db()
    assert (connection.status, connection.error_code) == (Connection.Status.ERROR, code)
    assert (issue.access, issue.sync_error) == (access, code)
    assert issue.sync_retry_at is None
    assert issue.sync_lease_token is None
    with patch("operations.tasks.dispatch_task") as dispatch:
        dispatch_due_operations()
    assert ("feedback.tasks.sync_github_issue", str(issue.pk)) not in [
        call.args for call in dispatch.call_args_list
    ]

    with (
        patch("operations.tasks.github_client") as revalidate_factory,
        patch("operations.tasks.dispatch_task") as dispatch,
    ):
        revalidate_client = revalidate_factory.return_value.__enter__.return_value
        revalidate_client.create_installation_token.return_value = ("token", "expires")
        revalidate_client.get_repository_by_id.return_value = {
            "id": 999,
            "full_name": "acme/widgets",
        }
        revalidate_github_connection(str(connection.pk))
    connection.refresh_from_db()
    assert connection.status == Connection.Status.ACTIVE
    dispatch.assert_called_once_with("feedback.tasks.sync_github_issue", str(issue.pk))
