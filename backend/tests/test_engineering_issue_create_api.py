"""API tests for previewing and creating a GitHub issue for a problem."""

import re
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from builders import (
    make_connection,
    make_membership,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import EngineeringIssue
from feedback.reports import link_report
from feedback.submissions import SourceSnapshot

pytestmark = pytest.mark.django_db

CREATED_ISSUE: dict[str, Any] = {
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


def preview_url(membership: Membership, problem_id: Any) -> str:
    return f"/api/workspaces/{membership.workspace_id}/problems/{problem_id}/issue/preview/"


def create_url(membership: Membership, problem_id: Any) -> str:
    return f"/api/workspaces/{membership.workspace_id}/problems/{problem_id}/issue/create/"


def github_mock(*, create_effect: Any = None) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    if create_effect is not None:
        client.create_issue.side_effect = create_effect
    else:
        client.create_issue.return_value = dict(CREATED_ISSUE)
    return client


def patched_client(client: MagicMock) -> Any:
    factory = patch("feedback.engineering_issues.github_client")
    mock_factory = factory.start()
    mock_factory.return_value.__enter__.return_value = client
    return factory


def create(
    client: Client,
    actor: Membership,
    problem: Any,
    *,
    title: str = "Title",
    body: str = "Body",
    version: int = 1,
) -> Any:
    return client.post(
        create_url(actor, problem.pk),
        {"title": title, "body": body, "expected_version": version},
        content_type="application/json",
    )


def test_preview_returns_title_and_summary_with_product_link(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor, title="Exports fail", summary="CSV export stops at 50%.")
    sign_in(client, actor)

    response = client.get(preview_url(actor, problem.pk))

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Exports fail"
    assert "CSV export stops at 50%." in body["body"]
    assert f"/problems/{problem.pk}" in body["body"]


def test_preview_excludes_customer_and_slack_fields(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor, summary="Export stops partway through.")
    source = SourceSnapshot(
        "slack",
        "T1",
        "C1",
        "171234.1",
        "https://example.test/msg",
        "U1",
        "Slack Author",
        "Secret raw Slack excerpt",
    )
    report = make_report(
        actor=actor,
        source=source,
        customer_label="Acme Corp",
        customer_contact_reference="ops@acme.test",
    )
    link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=problem.pk
    )
    sign_in(client, actor)

    response = client.get(preview_url(actor, problem.pk))

    body = response.json()["body"]
    for forbidden in ("Acme Corp", "ops@acme.test", "Secret raw Slack excerpt", "Slack Author"):
        assert forbidden not in body


def test_create_publishes_edited_title_and_body_with_operation_marker(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    mock = github_mock()

    factory = patched_client(mock)
    try:
        response = create(client, actor, problem, title="Edited title", body="Edited body")
    finally:
        factory.stop()

    assert response.status_code == 201
    body = response.json()
    assert body["engineering_issue"]["number"] == 7
    sent_body = mock.create_issue.call_args.kwargs["body"]
    assert sent_body.startswith("Edited body\n\n")
    assert re.search(r"<!-- rescribo-operation:[0-9a-f-]{36} -->", sent_body), (
        f"no operation marker in {sent_body!r}"
    )
    assert mock.create_issue.call_args.kwargs["title"] == "Edited title"
    issue = EngineeringIssue.objects.get(problem=problem, active=True)
    assert issue.number == 7


def test_create_requires_a_title(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock())
    try:
        response = create(client, actor, problem, title="   ")
    finally:
        factory.stop()

    assert response.status_code == 400
    assert not EngineeringIssue.objects.filter(problem=problem).exists()


def test_create_marks_a_timeout_as_uncertain_without_creating_a_row(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    factory = patched_client(github_mock(create_effect=httpx.TimeoutException("timed out")))
    try:
        response = create(client, actor, problem)
    finally:
        factory.stop()

    assert response.status_code == 409
    body = response.json()
    assert body["reason"] == "issue_creation_uncertain"
    assert "operation_id" in body
    assert not EngineeringIssue.objects.filter(problem=problem).exists()


def test_create_requires_an_active_github_connection(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    response = create(client, actor, problem)

    assert response.status_code == 400
    assert response.json()["reason"] == "connection_not_ready"


def test_preview_from_another_workspace_is_not_found(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    intruder = make_membership(
        user=make_user(email="intruder@example.test"),
        workspace=make_workspace(slug="intruder", name="Intruder"),
    )
    sign_in(client, intruder)

    response = client.get(preview_url(intruder, problem.pk))

    assert response.status_code == 404
