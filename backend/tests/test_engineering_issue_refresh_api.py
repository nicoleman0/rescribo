"""API tests for manually refreshing a problem's linked GitHub issue."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from builders import make_connection, make_engineering_issue, make_membership, make_problem
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY

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


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def refresh_url(membership: Membership, problem_id: Any) -> str:
    return f"/api/workspaces/{membership.workspace_id}/problems/{problem_id}/issue/refresh/"


def patched_client(*, get_issue: dict[str, Any] | None = None) -> Any:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    client.get_issue.return_value = get_issue if get_issue is not None else dict(ISSUE_PAYLOAD)
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def test_refresh_queues_a_coalesced_sync_request(client: Client) -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    issue = make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        state="open",
        provider_updated_at=datetime(2026, 9, 20, 20, 0, tzinfo=UTC),
    )
    sign_in(client, actor)

    factory = patched_client()
    try:
        response = client.post(
            refresh_url(actor, problem.pk),
            {"issue_id": str(issue.pk)},
            content_type="application/json",
        )
    finally:
        factory.stop()

    assert response.status_code == 202
    issue.refresh_from_db()
    assert response.json()["issue_id"] == str(issue.pk)
    assert response.json()["status"] == "pending"
    assert issue.sync_requested_generation == 1


def test_refresh_without_a_linked_issue_is_not_found(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    response = client.post(
        refresh_url(actor, problem.pk),
        {"issue_id": str(problem.pk)},
        content_type="application/json",
    )

    assert response.status_code == 404


def test_refresh_rejects_old_issue_id(client: Client) -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        provider_updated_at=datetime.now(UTC),
    )
    sign_in(client, actor)

    response = client.post(
        refresh_url(actor, problem.pk),
        {"issue_id": str(problem.pk)},
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.status_code == 409
