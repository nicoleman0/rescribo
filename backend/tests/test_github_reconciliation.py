"""Tests for the 15-minute reconciliation pass over active GitHub issues."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from builders import make_connection, make_engineering_issue, make_membership, make_problem

from connections.models import Connection
from feedback.models import EngineeringIssue
from feedback.tasks import reconcile_github_issues
from integrations.github_app.client import GitHubAPIError

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


def patched_client(
    *, get_issue: dict[str, Any] | None = None, error: Exception | None = None
) -> Any:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    if error is not None:
        client.get_issue.side_effect = error
    else:
        client.get_issue.return_value = get_issue if get_issue is not None else dict(ISSUE_PAYLOAD)
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def test_reconcile_syncs_active_issues_and_stamps_the_connection() -> None:
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
    assert connection.last_reconciled_at is None

    factory = patched_client()
    try:
        reconcile_github_issues()
    finally:
        factory.stop()

    issue.refresh_from_db()
    connection.refresh_from_db()
    assert issue.state == "closed"
    assert issue.last_synced_at is not None
    assert connection.last_reconciled_at is not None


def test_reconcile_updates_connection_even_with_no_active_issues() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)

    reconcile_github_issues()

    connection.refresh_from_db()
    assert connection.last_reconciled_at is not None


def test_reconcile_skips_connections_that_are_not_active() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace, status=Connection.Status.ERROR)
    problem = make_problem(actor=actor)
    make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=STORED_UPDATED_AT,
    )

    reconcile_github_issues()

    connection.refresh_from_db()
    assert connection.last_reconciled_at is None


def test_reconcile_marks_an_inaccessible_issue_access_lost_not_closed() -> None:
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
        reconcile_github_issues()
    finally:
        factory.stop()

    issue.refresh_from_db()
    connection.refresh_from_db()
    assert issue.access == EngineeringIssue.Access.ACCESS_LOST
    assert issue.state == "open"
    assert connection.last_reconciled_at is not None


def test_reconcile_ignores_superseded_issues() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    superseded = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="open",
        active=False,
        provider_updated_at=STORED_UPDATED_AT,
    )

    factory = patched_client()
    try:
        reconcile_github_issues()
    finally:
        factory.stop()

    superseded.refresh_from_db()
    assert superseded.last_synced_at is None  # untouched: it is not active
