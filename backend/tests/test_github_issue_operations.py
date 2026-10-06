"""Tests for approved and uncertain GitHub issue create operations."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from builders import make_connection, make_membership, make_problem, make_user, make_workspace
from django.utils import timezone

from connections.models import Connection
from feedback.errors import (
    IssueCreateUnresolved,
    IssueOperationError,
    NotFound,
    VersionConflict,
)
from feedback.models import EngineeringIssue
from integrations.github_app.client import GitHubAPIError
from operations.github_issue_create import (
    abandon_creation,
    approve_draft,
    create_draft,
    request_recovery,
)
from operations.models import ExternalOperation
from operations.retries import MAX_ATTEMPTS
from operations.tasks import (
    dispatch_due_operations,
    process_github_issue_create,
    reconcile_github_issue_create,
    revalidate_github_connection,
)

pytestmark = pytest.mark.django_db

CREATED_ISSUE: dict[str, Any] = {
    "id": 555,
    "number": 7,
    "title": "Export failure",
    "state": "open",
    "state_reason": None,
    "html_url": "https://github.com/acme/widgets/issues/7",
    "repository_url": "https://api.github.com/repos/acme/widgets",
    "repository": {"id": 999, "full_name": "acme/widgets"},
    "updated_at": "2026-09-20T21:00:00Z",
}


def approved_operation(actor: Any, problem: Any) -> ExternalOperation:
    draft = create_draft(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        title="Approved title",
        body="Approved body",
    )
    return approve_draft(
        actor=actor,
        problem_id=problem.pk,
        draft_id=draft.pk,
        draft_version=draft.draft_version,
        approved=True,
    )


def fake_provider(*, create_error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("short-lived", "expires")
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    if create_error is not None:
        client.create_issue.side_effect = create_error
    else:
        client.create_issue.return_value = dict(CREATED_ISSUE)
    return client


def test_approved_content_is_the_only_content_written_and_linked() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider()

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    issue = EngineeringIssue.objects.get(problem=problem, active=True)
    assert operation.state == ExternalOperation.State.SUCCEEDED
    assert client.create_issue.call_count == 1
    assert client.create_issue.call_args.kwargs["title"] == "Approved title"
    sent_body = client.create_issue.call_args.kwargs["body"]
    assert sent_body.startswith("Approved body\n\n<!-- rescribo-operation:")
    assert str(operation.pk) in sent_body
    assert issue.issue_id == "555"


def test_ambiguous_create_is_uncertain_and_never_posts_again() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider(create_error=httpx.TimeoutException("timeout"))

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
        process_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.UNCERTAIN
    assert client.create_issue.call_count == 1
    assert not EngineeringIssue.objects.filter(problem=problem, active=True).exists()


def test_marker_recovery_paginates_and_ignores_pull_requests() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    operation.state = ExternalOperation.State.UNCERTAIN
    operation.save(update_fields=["state"])
    marker = f"<!-- rescribo-operation:{operation.pk} -->"
    client = fake_provider()
    client.list_issues.side_effect = [
        ([{"pull_request": {}, "body": marker}], True),
        ([{**CREATED_ISSUE, "body": marker}], False),
    ]

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        reconcile_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.SUCCEEDED
    assert client.list_issues.call_count == 2
    assert EngineeringIssue.objects.get(problem=problem, active=True).issue_id == "555"


@pytest.mark.parametrize("stage", ["create_installation_token", "get_repository_by_id"])
@pytest.mark.parametrize(
    "error",
    [httpx.ConnectTimeout("timeout"), GitHubAPIError("preflight", 502), ValueError("bad identity")],
)
def test_preflight_failure_is_terminal_without_post(stage: str, error: Exception) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider()
    getattr(client, stage).side_effect = error
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.FAILED
    client.create_issue.assert_not_called()
    create_draft(actor=actor, problem_id=problem.pk, expected_version=problem.version)


def test_connect_timeout_during_post_is_known_not_sent() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = fake_provider(
            create_error=httpx.ConnectTimeout("connect")
        )
        process_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.FAILED


@pytest.mark.parametrize("expire_lease", [False, True])
def test_success_preserves_remote_identity_when_linking_cannot_finish(expire_lease: bool) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider()

    def created(**kwargs: Any) -> dict[str, Any]:
        if expire_lease:
            ExternalOperation.objects.filter(pk=operation.pk).update(
                state="uncertain", lease_token=None
            )
        return dict(CREATED_ISSUE)

    client.create_issue.side_effect = created
    with (
        patch("operations.tasks.github_client") as factory,
        patch(
            "operations.tasks.record_created_issue",
            side_effect=RuntimeError("database link failed"),
        ),
    ):
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.UNCERTAIN
    assert operation.remote_issue_id == "555"
    assert operation.remote_number == 7
    assert operation.remote_url == CREATED_ISSUE["html_url"]


def test_missing_marker_stops_dispatch_and_records_feedback() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    operation.state = ExternalOperation.State.UNCERTAIN
    operation.save()
    request_recovery(actor=actor, problem_id=problem.pk, operation_id=operation.pk, reference="7")
    client = fake_provider()
    client.get_issue.return_value = {**CREATED_ISSUE, "body": "Hand-filed issue"}
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        reconcile_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.safe_error == "marker_not_found"
    assert operation.recovery_attempts == 1
    assert operation.recovery_reference == ""
    assert not operation.recovery_requested
    with patch("operations.tasks.reconcile_github_issue_create.delay") as dispatch:
        dispatch_due_operations()
        dispatch_due_operations()
    dispatch.assert_not_called()
    abandon_creation(
        actor=actor,
        problem_id=problem.pk,
        operation_id=operation.pk,
        reason="Checked GitHub; issue was filed by hand.",
    )
    operation.refresh_from_db()
    assert operation.resolved_by == actor
    assert operation.resolution_reason
    create_draft(actor=actor, problem_id=problem.pk, expected_version=problem.version)


def test_abandon_cannot_cross_workspace_or_cancel_running_write() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    with pytest.raises(IssueOperationError):
        abandon_creation(
            actor=actor, problem_id=problem.pk, operation_id=operation.pk, reason="Checked"
        )
    operation.state = ExternalOperation.State.UNCERTAIN
    operation.save()
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@example.test")
    )
    with pytest.raises(NotFound):
        abandon_creation(
            actor=other, problem_id=problem.pk, operation_id=operation.pk, reason="Checked"
        )
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.UNCERTAIN


def test_abandoning_an_uncertain_create_records_the_member_and_unblocks_the_problem() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    operation.state = ExternalOperation.State.UNCERTAIN
    operation.save()
    with pytest.raises(IssueCreateUnresolved):
        create_draft(actor=actor, problem_id=problem.pk, expected_version=problem.version)

    abandon_creation(
        actor=actor,
        problem_id=problem.pk,
        operation_id=operation.pk,
        reason="No issue in acme/widgets",
    )

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.CANCELLED
    assert operation.resolved_by == actor
    assert operation.resolution_reason == "No issue in acme/widgets"
    assert create_draft(actor=actor, problem_id=problem.pk, expected_version=problem.version)


def test_edited_preview_updates_draft_and_invalidates_old_approval() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    first = create_draft(actor=actor, problem_id=problem.pk, expected_version=problem.version)
    edited = create_draft(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        draft_id=first.pk,
        body="Revised",
    )
    assert edited.pk == first.pk
    assert edited.draft_version == first.draft_version + 1
    with pytest.raises(VersionConflict):
        approve_draft(
            actor=actor,
            problem_id=problem.pk,
            draft_id=first.pk,
            draft_version=first.draft_version,
            approved=True,
        )


@pytest.mark.parametrize("stage", ["create_installation_token", "create_issue"])
def test_rate_limited_create_is_queued_again_after_the_delay(stage: str) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider()
    getattr(client, stage).side_effect = GitHubAPIError(
        "limited", 429, retry_after_seconds=600, rate_limited=True
    )
    before = timezone.now()
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
        # Not yet due, so a second run does nothing.
        process_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.QUEUED
    assert operation.safe_error == "rate_limited"
    assert operation.attempts == 1
    assert operation.lease_token is None
    assert (operation.due_at - before).total_seconds() >= 600
    assert client.create_issue.call_count == (1 if stage == "create_issue" else 0)

    operation.due_at = timezone.now()
    operation.save(update_fields=["due_at"])
    getattr(client, stage).side_effect = None
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.SUCCEEDED


def test_rate_limited_create_fails_at_the_retry_cap() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    ExternalOperation.objects.filter(pk=operation.pk).update(attempts=MAX_ATTEMPTS - 1)
    client = fake_provider(
        create_error=GitHubAPIError("limited", 403, retry_after_seconds=60, rate_limited=True)
    )
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.FAILED
    assert operation.safe_error == "rate_limited"
    assert operation.lease_token is None


@pytest.mark.parametrize(
    "stage,status,code",
    [
        ("create_installation_token", 404, "access_lost"),
        ("create_installation_token", 403, "installation_suspended"),
        ("create_installation_token", 401, "github_credentials_invalid"),
        ("create_issue", 401, "github_credentials_invalid"),
    ],
)
def test_refused_installation_disables_its_connections_and_cancels_creation(
    stage: str, status: int, code: str
) -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    shared = make_connection(workspace=make_workspace(slug="other"))
    operation = approved_operation(actor, make_problem(actor=actor))
    waiting = approved_operation(actor, make_problem(actor=actor))
    client = fake_provider()
    getattr(client, stage).side_effect = GitHubAPIError(
        "installation token creation" if stage == "create_installation_token" else "issue create",
        status,
    )

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
        process_github_issue_create(str(waiting.pk))

    operation.refresh_from_db()
    waiting.refresh_from_db()
    assert (operation.state, operation.safe_error) == ("cancelled", "disconnected")
    assert operation.lease_token is None
    assert (waiting.state, waiting.safe_error) == ("cancelled", "approval_stale")
    for row in (connection, shared):
        row.refresh_from_db()
        assert (row.status, row.error_code) == (Connection.Status.ERROR, code)
    assert client.create_issue.call_count == (1 if stage == "create_issue" else 0)

    # Reconnecting restores the connection without releasing the cancelled approvals.
    with (
        patch("operations.tasks.github_client") as factory,
        patch("operations.tasks.dispatch_task"),
    ):
        factory.return_value.__enter__.return_value = fake_provider()
        revalidate_github_connection(str(connection.pk))
        dispatch_due_operations()
    connection.refresh_from_db()
    operation.refresh_from_db()
    waiting.refresh_from_db()
    assert connection.status == Connection.Status.ACTIVE
    assert operation.state == waiting.state == ExternalOperation.State.CANCELLED
