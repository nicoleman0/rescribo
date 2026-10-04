"""Rejected signatures and OAuth state store nothing. Real PostgreSQL; provider calls are mocked."""

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from builders import (
    make_connection,
    make_membership,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from cryptography.fernet import Fernet
from django.test import Client, override_settings
from django.utils import timezone

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from accounts.tokens import digest
from connections.models import Connection, SetupState, SlackCaptureContext
from feedback.models import Activity, FollowUp, Report
from feedback.problems import confirm_fix
from feedback.reports import link_report
from operations.models import InboundReceipt

pytestmark = pytest.mark.django_db

SECRET = "test-slack-signing-secret"
INTERACTIONS = "/api/integrations/slack/interactions/"
EVENTS = "/api/integrations/slack/events/"
TEAM = "T0VERIFY"


@pytest.fixture(autouse=True)
def provider_settings() -> Iterator[None]:
    with override_settings(
        RESCRIBO_SLACK_SIGNING_SECRET=SECRET,
        RESCRIBO_SLACK_CLIENT_ID="test-id",
        RESCRIBO_SLACK_CLIENT_SECRET="test-secret",
        RESCRIBO_GITHUB_CLIENT_ID="test-id",
        RESCRIBO_GITHUB_CLIENT_SECRET="test-secret",
        RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode(),
    ):
        yield


# Slack signatures

BAD_SIGNATURES = {
    "wrong-secret": {"secret": "not-the-secret"},
    "stale": {"timestamp": int(time.time()) - 600},
    "future": {"timestamp": int(time.time()) + 600},
    "no-headers": {"headers": False},
    "bad-digest": {"digest": "v0=" + "0" * 64},
}


def post_signed(
    client: Client,
    path: str,
    body: bytes,
    content_type: str,
    *,
    secret: str = SECRET,
    timestamp: int | None = None,
    headers: bool = True,
    digest: str | None = None,
) -> Any:
    ts = str(int(time.time()) if timestamp is None else timestamp)
    mac = hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256)
    sent = (
        {"X-Slack-Request-Timestamp": ts, "X-Slack-Signature": digest or f"v0={mac.hexdigest()}"}
        if headers
        else {}
    )
    return client.post(path, data=body, content_type=content_type, headers=sent)


def interactions(client: Client, payload: dict[str, Any], **sign: Any) -> Any:
    body = urlencode({"payload": json.dumps(payload)}).encode()
    return post_signed(client, INTERACTIONS, body, "application/x-www-form-urlencoded", **sign)


def slack_connection() -> Connection:
    return Connection.objects.create(
        workspace=make_workspace(slug="verify", name="Verify"),
        provider="slack",
        external_id=TEAM,
        status="active",
        credential="ciphertext",
    )


@pytest.mark.parametrize("sign", BAD_SIGNATURES.values(), ids=BAD_SIGNATURES.keys())
def test_unverified_event_cannot_disable_a_connection(client: Client, sign: dict[str, Any]) -> None:
    connection = slack_connection()
    payload = {
        "type": "event_callback",
        "team_id": TEAM,
        "event_id": "Ev0FORGED",
        "event": {"type": "app_uninstalled"},
    }
    response = post_signed(client, EVENTS, json.dumps(payload).encode(), "application/json", **sign)
    assert response.status_code == 401
    assert not InboundReceipt.objects.exists()
    after = Connection.objects.get(pk=connection.pk)
    assert (after.status, after.version, after.error_code) == ("active", 1, "")


@pytest.mark.parametrize("sign", BAD_SIGNATURES.values(), ids=BAD_SIGNATURES.keys())
def test_unverified_outcome_click_changes_nothing(client: Client, sign: dict[str, Any]) -> None:
    connection = slack_connection()
    owner = make_membership(workspace=connection.workspace, role="owner")
    problem = make_problem(actor=owner)
    report = make_report(actor=owner)
    link_report(actor=owner, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    confirm_fix(
        actor=owner, problem_id=problem.pk, expected_version=1, fix_note="x", fix_version="1"
    )
    follow_up = FollowUp.objects.get(report=report)
    activity_before = Activity.objects.count()
    payload = {
        "type": "block_actions",
        "team": {"id": TEAM},
        "user": {"id": "U0ACTOR"},
        "container": {"channel_id": "D0DM", "message_ts": "1.1"},
        "actions": [{"action_id": "follow_up_contacted", "value": str(follow_up.pk)}],
    }
    assert interactions(client, payload, **sign).status_code == 401
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING
    assert Activity.objects.count() == activity_before


@pytest.mark.parametrize("sign", BAD_SIGNATURES.values(), ids=BAD_SIGNATURES.keys())
def test_unverified_submission_stores_no_report(client: Client, sign: dict[str, Any]) -> None:
    connection = slack_connection()
    context = SlackCaptureContext.objects.create(
        connection=connection,
        team_id=TEAM,
        channel_id="C0X",
        actor_id="U0ACTOR",
        message_ts="1.1",
        text="customer text",
        expires_at=timezone.now() + timedelta(minutes=15),
    )
    payload = {
        "type": "view_submission",
        "team": {"id": TEAM},
        "user": {"id": "U0ACTOR"},
        "view": {
            "private_metadata": str(context.pk),
            "state": {"values": {"report_title": {"title": {"value": "Forged"}}}},
        },
    }
    assert interactions(client, payload, **sign).status_code == 401
    assert not Report.objects.exists()
    context.refresh_from_db()
    assert context.consumed_at is None and context.text == "customer text"


# OAuth state

CONNECTED = dict(external_id="T0OLD", identity="Old team", status="active", credential="old")
PROVIDER_VALUES: dict[str, dict[str, Any]] = {
    "slack": {"external_id": "T0NEW", "identity": "New", "scopes": [], "credential": "new"},
    "github": {
        "external_id": "777",
        "identity": "org",
        "scopes": [],
        "repository": "org/repo",
        "repository_id": "7",
        "visibility": "private",
        "credential": "",
    },
}


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def owner_client(membership: Membership) -> Client:
    client = Client()
    sign_in(client, membership)
    return client


def begin(client: Client, owner: Membership, provider: str) -> str:
    response = client.post(
        f"/api/workspaces/{owner.workspace_id}/connections/{provider}/setup/",
        {"consent": True, "repository": "org/repo"},
        content_type="application/json",
    )
    assert response.status_code == 200
    return parse_qs(urlparse(response.json()["url"]).query)["state"][0]


def callback(client: Client, owner: Membership, provider: str, state: str) -> Any:
    return client.get(
        f"/api/workspaces/{owner.workspace_id}/connections/{provider}/callback/",
        {"state": state, "code": "code"},
    )


def connection_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in Connection.objects.order_by("pk").values()]


@pytest.fixture(params=["slack", "github"])
def provider(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def owner() -> Membership:
    return make_membership(role="owner")


@pytest.fixture
def rejected_setup(provider: str, owner: Membership) -> Iterator[MagicMock]:
    """Patches the provider call; a rejected callback must never reach it."""
    Connection.objects.create(workspace=owner.workspace, provider=provider, **CONNECTED)
    with patch(f"connections.providers.{provider}_setup") as setup:
        setup.return_value = PROVIDER_VALUES[provider]
        yield setup


def assert_rejected(response: Any, setup: MagicMock, before: list[dict[str, Any]]) -> None:
    assert response.status_code == 400
    assert response.json()["reason"] == "invalid_state"
    setup.assert_not_called()
    assert connection_rows() == before


def test_expired_state_is_rejected(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    client = owner_client(owner)
    state = begin(client, owner, provider)
    SetupState.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    before = connection_rows()
    assert_rejected(callback(client, owner, provider, state), rejected_setup, before)


def test_state_from_another_owner_is_rejected(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    state = begin(owner_client(owner), owner, provider)
    second = make_membership(
        workspace=owner.workspace, user=make_user(email="second@example.test"), role="owner"
    )
    before = connection_rows()
    response = callback(owner_client(second), second, provider, state)
    assert_rejected(response, rejected_setup, before)


def test_state_from_another_workspace_is_rejected(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    state = begin(owner_client(owner), owner, provider)
    foreign = make_membership(
        workspace=make_workspace(slug="foreign", name="Foreign"),
        user=make_user(email="foreign@example.test"),
        role="owner",
    )
    before = connection_rows()
    response = callback(owner_client(foreign), foreign, provider, state)
    assert_rejected(response, rejected_setup, before)
    assert not Connection.objects.filter(workspace=foreign.workspace).exists()


def test_unknown_state_is_rejected(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    before = connection_rows()
    response = callback(owner_client(owner), owner, provider, "forged-state")
    assert_rejected(response, rejected_setup, before)


def test_replayed_state_is_rejected_after_success(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    client = owner_client(owner)
    state = begin(client, owner, provider)
    assert callback(client, owner, provider, state).status_code == 302
    rejected_setup.assert_called_once()
    rejected_setup.reset_mock()
    before = connection_rows()
    assert_rejected(callback(client, owner, provider, state), rejected_setup, before)


def test_forged_installation_is_rejected_over_http(owner: Membership) -> None:
    """The callback names no installation. The user's own access to the repository decides."""
    existing = make_connection(workspace=owner.workspace, external_id="42")
    client = owner_client(owner)
    state = begin(client, owner, "github")
    before = connection_rows()
    sdk = MagicMock()
    sdk.exchange_user_code.return_value = "user-token"
    sdk.get_repository_installation.return_value = {
        "id": 999,
        "permissions": {"issues": "write", "metadata": "read"},
        "account": {"login": "victim"},
    }
    sdk.get_user_installation_repositories.return_value = {"repositories": []}
    with patch("integrations.github_app.settings.github_client") as factory:
        factory.return_value.__enter__.return_value = sdk
        response = callback(client, owner, "github", state)
    assert response.status_code == 400
    assert response.json()["reason"] == "repository_access"
    sdk.create_installation_token.assert_not_called()
    assert connection_rows() == before
    assert Connection.objects.get(pk=existing.pk).external_id == "42"


def test_state_is_bound_to_its_owner_even_when_the_session_matches(
    provider: str, owner: Membership, rejected_setup: MagicMock
) -> None:
    """Owner and session are separate bindings; each must hold on its own."""
    second = make_membership(
        workspace=owner.workspace, user=make_user(email="second@example.test"), role="owner"
    )
    client = owner_client(second)
    SetupState.objects.create(
        token_digest=digest("known-state"),
        actor=owner,
        session_digest=digest(client.session.session_key or ""),
        provider=provider,
        repository="org/repo",
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    before = connection_rows()
    assert_rejected(callback(client, second, provider, "known-state"), rejected_setup, before)
