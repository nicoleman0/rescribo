"""Settings use real PostgreSQL; provider responses are mocked, never live evidence."""

from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from cryptography.fernet import Fernet
from django.test import Client, override_settings

from accounts.models import Membership, Workspace
from accounts.services import create_invitation
from accounts.session import SESSION_GENERATION_KEY
from connections.credentials import cipher, decrypt
from connections.models import AllowedChannel, Connection
from connections.providers import SetupError
from feedback.models import Activity, FollowUp, Report, ReportNotificationOperation, ReportSource
from feedback.problems import confirm_fix
from feedback.reports import link_report

pytestmark = pytest.mark.django_db


def login(client: Client, actor: Membership) -> None:
    client.force_login(actor.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = actor.user.session_generation
    session.save()


@pytest.fixture
def actor(client: Client) -> Membership:
    actor = make_membership(role="owner")
    login(client, actor)
    return actor


def url(actor: Membership, path: str) -> str:
    return f"/api/workspaces/{actor.workspace_id}/{path}"


def post(client: Client, actor: Membership, path: str, body: dict[str, Any]) -> Any:
    return client.post(url(actor, path), body, content_type="application/json")


def connect(actor: Membership, provider: str = "slack") -> Connection:
    return Connection.objects.create(
        workspace=actor.workspace,
        provider=provider,
        external_id="T123" if provider == "slack" else "123",
        identity="Example team",
        status="active",
        credential="encrypted-secret",
        scopes=["commands"],
        repository="owner/repo" if provider == "github" else "",
    )


def test_read_omits_secrets_and_is_scoped(client: Client, actor: Membership) -> None:
    connect(actor)
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@test.dev")
    )
    connect(other, "github")
    response = client.get(url(actor, "connections/"))
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert b"encrypted-secret" not in response.content
    assert "credential" not in response.json()[0]
    assert client.get(url(other, "connections/")).status_code == 404


@pytest.mark.parametrize(
    "path,body",
    [
        ("connections/slack/setup/", {"consent": True}),
        ("connections/slack/disconnect/", {"version": 1, "confirmation": "DISCONNECT"}),
        ("connections/slack/refresh/", {"version": 1}),
        ("channels/", {"version": 1, "channel_id": "C123", "consent": True}),
        ("delete/", {"confirmation": "example"}),
    ],
)
def test_owner_only(client: Client, actor: Membership, path: str, body: dict[str, Any]) -> None:
    member = make_membership(workspace=actor.workspace, user=make_user(email="another@test.dev"))
    login(client, member)
    assert post(client, actor, path, body).status_code == 403


@pytest.mark.parametrize("provider", ["slack", "github"])
def test_disconnect_cancels_only_unsent_and_keeps_reports(
    client: Client, actor: Membership, provider: str
) -> None:
    row = connect(actor, provider)
    report = make_report(actor=actor)
    problem = make_problem(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, problem_id=problem.pk, expected_version=1
    )
    operations = [
        make_notification(report=report, state=state, resolution_revision=10 + offset)
        for offset, state in enumerate(["draft", "queued", "failed", "uncertain", "sent"])
    ]
    assert (
        post(
            client, actor, f"connections/{provider}/disconnect/", {"version": 1, "confirmation": ""}
        ).status_code
        == 400
    )
    assert (
        post(
            client,
            actor,
            f"connections/{provider}/disconnect/",
            {"version": 1, "confirmation": "DISCONNECT"},
        ).status_code
        == 204
    )
    row.refresh_from_db()
    assert row.credential == row.external_id == ""
    assert row.status == "disconnected"
    assert Report.objects.filter(pk=report.pk).exists()
    for operation, expected in zip(
        operations, ["cancelled", "cancelled", "cancelled", "uncertain", "sent"], strict=True
    ):
        operation.refresh_from_db()
        assert operation.state == expected
        assert bool(operation.invalidated_at) == (expected != "sent")
    assert (
        post(
            client,
            actor,
            f"connections/{provider}/disconnect/",
            {"version": 1, "confirmation": "DISCONNECT"},
        ).status_code
        == 409
    )


def test_channels_validate_consent_and_preserve_on_failure(
    client: Client, actor: Membership
) -> None:
    row = connect(actor)
    body = {"version": 1, "channel_id": "C123", "consent": True}
    assert post(client, actor, "channels/", body | {"consent": False}).status_code == 400
    with patch(
        "connections.providers.channel_details",
        return_value={"channel_id": "C123", "name": "support", "is_private": True},
    ) as provider:
        assert post(client, actor, "channels/", body).status_code == 204
        provider.assert_called_once_with("encrypted-secret", "C123")
    assert AllowedChannel.objects.get(connection=row).is_private
    with patch(
        "connections.providers.channel_details",
        side_effect=SetupError("provider_unavailable", "Retry."),
    ):
        assert post(client, actor, "channels/", body | {"version": 2}).status_code == 400
    assert AllowedChannel.objects.filter(connection=row).count() == 1
    assert (
        post(client, actor, "channels/", body | {"version": 2, "remove": True}).status_code == 204
    )
    assert not AllowedChannel.objects.filter(connection=row).exists()


def test_refresh_records_failure_and_recovery(client: Client, actor: Membership) -> None:
    row = connect(actor)
    with patch(
        "connections.providers.check_connection",
        side_effect=SetupError("missing_scopes", "Reconnect."),
    ):
        assert post(client, actor, "connections/slack/refresh/", {"version": 1}).status_code == 400
    row.refresh_from_db()
    assert row.status == "error" and row.error_code == "missing_scopes"
    with patch("connections.providers.check_connection"):
        assert post(client, actor, "connections/slack/refresh/", {"version": 2}).status_code == 204
    row.refresh_from_db()
    assert row.status == "active" and row.last_success_at


def test_report_deletion_confirmation_version_and_scope(client: Client, actor: Membership) -> None:
    report = make_report(actor=actor, description="private customer content")
    problem = make_problem(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, problem_id=problem.pk, expected_version=1
    )
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Fixed",
        fix_version="1",
    )
    assert FollowUp.objects.filter(report=report).exists()
    make_notification(report=report)
    path = f"reports/{report.pk}/delete/"
    assert (
        post(client, actor, path, {"version": report.version, "confirmation": ""}).status_code
        == 400
    )
    assert post(client, actor, path, {"version": 1, "confirmation": "DELETE"}).status_code == 409
    assert (
        post(client, actor, path, {"version": report.version, "confirmation": "DELETE"}).status_code
        == 204
    )
    assert not Report.objects.filter(pk=report.pk).exists()
    assert not ReportSource.objects.filter(report_id=report.pk).exists()
    assert not ReportNotificationOperation.objects.exists()
    assert not FollowUp.objects.exists()
    deletion = Activity.objects.get(record_id=report.pk)
    assert deletion.action == "report.deleted" and deletion.metadata == {}
    assert problem.reports.count() == 0


def test_workspace_delete_removes_tenant_and_preserves_other_membership(
    client: Client, actor: Membership
) -> None:
    other = make_workspace(slug="other")
    make_membership(user=actor.user, workspace=other)
    connect(actor)
    report = make_report(actor=actor)
    problem = make_problem(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, problem_id=problem.pk, expected_version=1
    )
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Fixed",
        fix_version="1",
    )
    assert FollowUp.objects.filter(report=report).exists()
    make_notification(report=report)
    create_invitation(actor=actor, email="invite@test.dev", role="member")
    assert post(client, actor, "delete/", {"confirmation": "wrong"}).status_code == 400
    assert post(client, actor, "delete/", {"confirmation": actor.workspace.slug}).status_code == 204
    assert not Workspace.objects.filter(pk=actor.workspace_id).exists()
    assert Workspace.objects.filter(pk=other.pk).exists()
    assert actor.user.memberships.count() == 1
    assert not Connection.objects.exists()
    assert not FollowUp.objects.exists()
    assert not Activity.objects.exists()
    assert client.get(url(actor, "connections/")).status_code == 404


@override_settings(
    RESCRIBO_SLACK_CLIENT_ID="id",
    RESCRIBO_SLACK_CLIENT_SECRET="secret",
    RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode(),
)
def test_oauth_state_bound_to_session_and_single_use(client: Client, actor: Membership) -> None:
    response = post(client, actor, "connections/slack/setup/", {"consent": True})
    assert response.status_code == 200
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    callback = url(actor, "connections/slack/callback/") + f"?state={state}&code=code"
    second = Client()
    login(second, actor)
    assert second.get(callback).status_code == 400
    with patch(
        "connections.providers.slack_setup",
        return_value={
            "external_id": "T1",
            "identity": "Team",
            "scopes": ["commands"],
            "credential": "ciphertext",
        },
    ):
        assert client.get(callback).status_code == 302
        assert client.get(callback).status_code == 400
    assert Connection.objects.get().external_id == "T1"


@override_settings(RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode())
def test_credential_encryption() -> None:
    encrypted = cipher().encrypt(b"test-token").decode()
    assert "test-token" not in encrypted
    assert decrypt(encrypted) == "test-token"
    with pytest.raises(SetupError):
        decrypt("bad ciphertext")


@pytest.mark.parametrize(
    "path,body",
    [
        ("connections/slack/disconnect/", {"version": 1, "confirmation": "DISCONNECT"}),
        ("connections/slack/refresh/", {"version": 1}),
        ("channels/", {"version": 1, "channel_id": "C123", "consent": True}),
        ("delete/", {"confirmation": "other"}),
    ],
)
def test_foreign_workspace_mutations_are_hidden(
    client: Client, actor: Membership, path: str, body: dict[str, Any]
) -> None:
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@test.dev"), role="owner"
    )
    connect(other)
    assert post(client, other, path, body).status_code == 404
    assert Connection.objects.get().status == "active"


def test_report_deletion_denies_members_and_foreign_records(
    client: Client, actor: Membership
) -> None:
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@test.dev")
    )
    report = make_report(actor=other)
    assert (
        post(
            client, actor, f"reports/{report.pk}/delete/", {"version": 1, "confirmation": "DELETE"}
        ).status_code
        == 404
    )
    login(client, other)
    assert (
        post(
            client, other, f"reports/{report.pk}/delete/", {"version": 1, "confirmation": "DELETE"}
        ).status_code
        == 403
    )
    assert Report.objects.filter(pk=report.pk).exists()


def test_settings_mutations_require_csrf(actor: Membership) -> None:
    client = Client(enforce_csrf_checks=True)
    login(client, actor)
    assert post(client, actor, "delete/", {"confirmation": actor.workspace.slug}).status_code == 403


@override_settings(
    RESCRIBO_SLACK_CLIENT_ID="id",
    RESCRIBO_SLACK_CLIENT_SECRET="secret",
    RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode(),
)
def test_disconnect_invalidates_setup_and_provider_failure_consumes_state(
    client: Client, actor: Membership
) -> None:
    connect(actor)

    def begin() -> str:
        response = post(client, actor, "connections/slack/setup/", {"consent": True})
        state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
        return url(actor, "connections/slack/callback/") + f"?state={state}&code=code"

    first = begin()
    assert (
        post(
            client,
            actor,
            "connections/slack/disconnect/",
            {"version": 1, "confirmation": "DISCONNECT"},
        ).status_code
        == 204
    )
    with patch("connections.providers.slack_setup") as provider:
        assert client.get(first).status_code == 400
        provider.assert_not_called()
    second = begin()
    with patch(
        "connections.providers.slack_setup",
        side_effect=SetupError("provider_unavailable", "Retry setup."),
    ) as provider:
        assert client.get(second).status_code == 400
        assert client.get(second).status_code == 400
        provider.assert_called_once()
    assert Connection.objects.get().status == "disconnected"


@override_settings(
    RESCRIBO_SLACK_CLIENT_ID="id",
    RESCRIBO_SLACK_CLIENT_SECRET="secret",
    RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode(),
)
def test_cannot_bind_same_slack_team_twice(client: Client, actor: Membership) -> None:
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@test.dev")
    )
    connect(other)
    response = post(client, actor, "connections/slack/setup/", {"consent": True})
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    with patch(
        "connections.providers.slack_setup",
        return_value={
            "external_id": "T123",
            "credential": "secret",
            "identity": "Team",
            "scopes": [],
        },
    ):
        response = client.get(
            url(actor, "connections/slack/callback/") + f"?state={state}&code=code"
        )
    assert response.status_code == 400 and response.json()["reason"] == "team_in_use"
    assert Connection.objects.count() == 1


@override_settings(RESCRIBO_GITHUB_CLIENT_ID="id", RESCRIBO_GITHUB_CLIENT_SECRET="secret")
def test_second_workspace_binds_a_shared_github_repository(
    client: Client, actor: Membership
) -> None:
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@test.dev")
    )
    connect(other, "github")
    response = post(
        client, actor, "connections/github/setup/", {"consent": True, "repository": "owner/repo"}
    )
    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    with patch(
        "connections.providers.github_setup",
        return_value={
            "external_id": "123",
            "identity": "owner",
            "scopes": ["issues:write", "metadata:read"],
            "repository": "owner/repo",
            "repository_id": "",
            "visibility": "private",
            "credential": "",
        },
    ):
        response = client.get(
            url(actor, "connections/github/callback/") + f"?state={state}&code=code"
        )
    assert response.status_code == 302

    response = client.get(url(actor, "connections/"))
    assert [row["provider"] for row in response.json()] == ["github"]
    assert response.json()[0]["status"] == "active"
    assert str(other.workspace_id).encode() not in response.content
    assert Connection.objects.filter(provider="github", external_id="123").count() == 2
