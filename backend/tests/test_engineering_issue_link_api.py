"""API tests for linking an existing GitHub issue to a problem."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from builders import make_connection, make_membership, make_problem, make_user, make_workspace
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import EngineeringIssue

pytestmark = pytest.mark.django_db

ISSUE_PAYLOAD: dict[str, Any] = {
    "id": 555,
    "number": 7,
    "title": "Export button does nothing",
    "state": "open",
    "state_reason": None,
    "html_url": "https://github.com/acme/widgets/issues/7",
    "repository_url": "https://api.github.com/repos/acme/widgets",
    "updated_at": "2026-09-20T21:00:00Z",
}


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def link_url(membership: Membership, problem_id: Any) -> str:
    return f"/api/workspaces/{membership.workspace_id}/problems/{problem_id}/issue/link/"


def github_mock(*, issue: dict[str, Any] | None = None) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    client.get_issue.return_value = issue if issue is not None else dict(ISSUE_PAYLOAD)
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    return client


def patched_client(client: MagicMock) -> Any:
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def link(
    client: Client,
    actor: Membership,
    problem: Any,
    *,
    reference: str = "7",
    version: int = 1,
    replace: bool = False,
) -> Any:
    return client.post(
        link_url(actor, problem.pk),
        {"reference": reference, "expected_version": version, "replace": replace},
        content_type="application/json",
    )


def test_link_succeeds_and_records_activity(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        response = link(client, actor, problem)
    finally:
        factory.stop()

    assert response.status_code == 200
    body = response.json()
    assert body["engineering_issue"]["number"] == 7
    assert body["engineering_issue"]["state"] == "open"
    issue = EngineeringIssue.objects.get(problem=problem, active=True)
    assert issue.issue_id == "555"
    assert issue.created_by_id == actor.pk


def test_link_rejects_pull_requests(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    issue = {**ISSUE_PAYLOAD, "pull_request": {"url": "https://api.github.com/x"}}
    factory = patched_client(github_mock(issue=issue))
    try:
        response = link(client, actor, problem)
    finally:
        factory.stop()

    assert response.status_code == 400
    assert response.json()["reason"] == "issue_reference_rejected"
    assert not EngineeringIssue.objects.filter(problem=problem).exists()


def test_link_rejects_a_reply_from_another_repository(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    foreign = {
        **ISSUE_PAYLOAD,
        "repository_url": "https://api.github.com/repos/other/widgets",
        "html_url": "https://github.com/other/widgets/issues/7",
    }
    factory = patched_client(github_mock(issue=foreign))
    try:
        response = link(client, actor, problem)
    finally:
        factory.stop()
    assert response.status_code == 400
    assert response.json()["reason"] == "issue_reference_rejected"
    assert not EngineeringIssue.objects.filter(problem=problem).exists()


def test_link_rejects_issue_from_other_repository(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        response = link(
            client, actor, problem, reference="https://github.com/other/repository/issues/7"
        )
    finally:
        factory.stop()

    assert response.status_code == 400
    assert response.json()["reason"] == "issue_reference_rejected"


def test_linking_the_same_current_issue_is_a_noop_success(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        first = link(client, actor, problem)
        assert first.status_code == 200
        second = link(client, actor, problem, version=first.json()["version"])
    finally:
        factory.stop()

    assert second.status_code == 200
    assert EngineeringIssue.objects.filter(problem=problem, active=True).count() == 1


def test_link_rejects_issue_already_linked_to_another_problem(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    first_problem = make_problem(actor=actor, title="First problem")
    second_problem = make_problem(actor=actor, title="Second problem")
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        first = link(client, actor, first_problem)
        assert first.status_code == 200
        second = link(client, actor, second_problem)
    finally:
        factory.stop()

    assert second.status_code == 409
    body = second.json()
    assert body["reason"] == "issue_linked_elsewhere"
    assert body["problem_id"] == str(first_problem.pk)


def test_link_supersedes_the_problems_existing_active_issue(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        first = link(client, actor, problem)
        assert first.status_code == 200
        other_issue = {
            **ISSUE_PAYLOAD,
            "id": 999,
            "number": 9,
            "html_url": "https://github.com/acme/widgets/issues/9",
        }
        factory.stop()
        factory = patched_client(github_mock(issue=other_issue))
        second = link(
            client, actor, problem, reference="9", version=first.json()["version"], replace=True
        )
    finally:
        factory.stop()

    assert second.status_code == 200
    assert second.json()["engineering_issue"]["number"] == 9
    active = EngineeringIssue.objects.get(problem=problem, active=True)
    assert active.number == 9
    superseded = EngineeringIssue.objects.get(problem=problem, active=False)
    assert superseded.number == 7 and superseded.unlinked_at is not None


def test_link_requires_an_active_github_connection(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    response = link(client, actor, problem)

    assert response.status_code == 400
    assert response.json()["reason"] == "connection_not_ready"


def test_link_rejects_stale_problem_version(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        response = link(client, actor, problem, version=999)
    finally:
        factory.stop()

    assert response.status_code == 409
    assert response.json()["reason"] == "version_conflict"


@pytest.mark.parametrize("access", ["foreign", "anonymous"])
def test_link_checks_access(client: Client, access: str) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    if access == "foreign":
        stranger = make_membership(
            user=make_user(email="stranger@example.test"),
            workspace=make_workspace(slug="other", name="Other"),
        )
        sign_in(client, stranger)
    else:
        client.logout()

    factory = patched_client(github_mock())
    try:
        response = link(client, actor, problem)
    finally:
        factory.stop()

    assert response.status_code == (401 if access == "anonymous" else 404)
    assert not EngineeringIssue.objects.filter(problem=problem).exists()
