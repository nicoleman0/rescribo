"""Slack capture over HTTP with real PostgreSQL; Slack API calls are mocked, not live evidence."""

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest
from builders import make_membership, make_user, make_workspace
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from slack_sdk.errors import SlackApiError
from slack_sdk.web import SlackResponse

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections import slack_identity, slack_inbound
from connections.models import (
    AllowedChannel,
    Connection,
    ExternalIdentity,
    SlackCaptureContext,
    SlackLinkCode,
)
from feedback.models import Report, ReportSource
from integrations.slack.errors import ChannelRejected
from operations.models import InboundReceipt

pytestmark = pytest.mark.django_db

SECRET = "slack-signing-secret"
INTERACTIONS = "/api/integrations/slack/interactions/"
EVENTS = "/api/integrations/slack/events/"
TEAM = "T0TEAM"
CHANNEL = "C0FEEDBACK"
ACTOR = "U0ACTOR"


def slack_error(code: str) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/test",
        req_args={},
        data={"ok": False, "error": code},
        headers={},
        status_code=200,
    )
    return SlackApiError(code, response)


def signed(body: bytes, *, timestamp: int | None = None, secret: str = SECRET) -> dict[str, str]:
    ts = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(secret.encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256)
    return {
        "X-Slack-Request-Timestamp": ts,
        "X-Slack-Signature": f"v0={digest.hexdigest()}",
    }


def interact(client: Client, payload: dict[str, Any], **sign_args: Any) -> Any:
    body = urlencode({"payload": json.dumps(payload)}).encode()
    return client.post(
        INTERACTIONS,
        data=body,
        content_type="application/x-www-form-urlencoded",
        headers=signed(body, **sign_args),
    )


def event(client: Client, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload).encode()
    return client.post(EVENTS, data=body, content_type="application/json", headers=signed(body))


def shortcut(
    *, ts: str = "1758400000.000100", thread_ts: str | None = None, **overrides: Any
) -> dict[str, Any]:
    message: dict[str, Any] = {"ts": ts, "text": "Export fails for Acme", "user": "U0AUTHOR"}
    if thread_ts:
        message["thread_ts"] = thread_ts
    payload = {
        "type": "message_action",
        "callback_id": "submit_customer_feedback",
        "trigger_id": "Tr0trigger",
        "team": {"id": TEAM},
        "user": {"id": ACTOR},
        "channel": {"id": CHANNEL, "name": "customer-feedback"},
        "message": message,
    }
    payload.update(overrides)
    return payload


def submission(
    context_id: str, *, title: str = "Export fails", link_code: str | None = None, **who: str
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "report_title": {"title": {"value": title}},
        "customer_reference": {"value": {"value": "Acme"}},
        "affected_version": {"value": {"value": "4.2"}},
        "additional_context": {"value": {"value": "Seen twice"}},
    }
    if link_code is not None:
        values["slack_link_code"] = {"value": {"value": link_code}}
    return {
        "type": "view_submission",
        "team": {"id": who.get("team", TEAM)},
        "user": {"id": who.get("user", ACTOR)},
        "view": {"private_metadata": context_id, "state": {"values": values}},
    }


@pytest.fixture(autouse=True)
def slack_settings() -> Iterator[None]:
    with override_settings(
        RESCRIBO_SLACK_SIGNING_SECRET=SECRET, RESCRIBO_PUBLIC_BASE_URL="https://app.test"
    ):
        yield


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def api() -> Iterator[MagicMock]:
    with (
        patch.object(slack_inbound.client, "eligible_channel") as eligible,
        patch.object(slack_inbound.client, "open_view") as open_view,
        patch.object(slack_inbound.client, "message_permalink") as permalink,
        patch("connections.slack_inbound.dispatch_task") as dispatch,
    ):
        permalink.return_value = "https://slack.test/archives/C0FEEDBACK/p1"
        yield MagicMock(
            eligible=eligible, open_view=open_view, permalink=permalink, dispatch=dispatch
        )


@pytest.fixture
def member() -> Membership:
    return make_membership(role="owner")


@pytest.fixture
def connection(member: Membership) -> Connection:
    row = Connection.objects.create(
        workspace=member.workspace,
        provider="slack",
        external_id=TEAM,
        identity="Acme Slack",
        status="active",
        credential="encrypted",
    )
    AllowedChannel.objects.create(
        connection=row, channel_id=CHANNEL, name="customer-feedback", is_private=False
    )
    return row


def link(member: Membership, user_id: str = ACTOR) -> None:
    ExternalIdentity.objects.create(
        workspace=member.workspace,
        membership=member,
        provider="slack",
        provider_team_id=TEAM,
        provider_user_id=user_id,
    )


def opened_view(api: MagicMock) -> dict[str, Any]:
    return api.open_view.call_args.kwargs["view"]


def open_and_validate(client: Client, api: MagicMock, **shortcut_args: Any) -> str:
    assert interact(client, shortcut(**shortcut_args)).status_code == 200
    context_id = opened_view(api)["private_metadata"]
    slack_inbound.revalidate_capture_channel(context_id)
    return context_id


# Signatures


@pytest.mark.parametrize(
    "sign_args",
    [{"secret": "wrong"}, {"timestamp": int(time.time()) - 600}],
    ids=["wrong-secret", "stale"],
)
def test_unverified_requests_store_nothing(
    client: Client, api: MagicMock, connection: Connection, sign_args: dict[str, Any]
) -> None:
    assert interact(client, shortcut(), **sign_args).status_code == 401
    assert not SlackCaptureContext.objects.exists()
    api.open_view.assert_not_called()


def test_missing_signature_headers_are_rejected(client: Client, connection: Connection) -> None:
    body = urlencode({"payload": json.dumps(shortcut())}).encode()
    response = client.post(
        INTERACTIONS, data=body, content_type="application/x-www-form-urlencoded"
    )
    assert response.status_code == 401


def test_missing_signing_secret_fails_closed(client: Client, connection: Connection) -> None:
    with override_settings(RESCRIBO_SLACK_SIGNING_SECRET=""):
        assert interact(client, shortcut()).status_code == 500


# Capture


def test_root_message_capture_commits_report_and_snapshot(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    context_id = open_and_validate(client, api)
    view = opened_view(api)
    assert not any(b.get("block_id") == "slack_link_code" for b in view["blocks"])
    assert "visible to all members of Example" in json.dumps(view)
    api.dispatch.assert_called_with("connections.tasks.revalidate_capture_channel", context_id)

    with TestCase.captureOnCommitCallbacks(execute=True):
        response = interact(client, submission(context_id))

    body = response.json()
    assert body["response_action"] == "update"
    report = Report.objects.get()
    assert f"https://app.test/inbox/{report.pk}" in json.dumps(body)
    assert report.workspace_id == member.workspace_id
    assert report.submitted_by == member
    assert (report.title, report.customer_label, report.affected_version) == (
        "Export fails",
        "Acme",
        "4.2",
    )
    assert report.description == "Seen twice"
    source = report.source
    assert (source.kind, source.external_workspace_id, source.external_channel_id) == (
        "slack",
        TEAM,
        CHANNEL,
    )
    assert source.external_message_id == "1758400000.000100"
    assert source.snapshot_text == "Export fails for Acme"
    assert source.author_external_id == "U0AUTHOR"
    context = SlackCaptureContext.objects.get()
    assert context.consumed_at is not None and context.text == ""
    api.dispatch.assert_called_with("connections.tasks.resolve_slack_permalink", str(source.pk))


def test_thread_reply_is_captured_alone_with_a_preview_note(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    context_id = open_and_validate(
        client, api, ts="1758400000.000200", thread_ts="1758400000.000100"
    )
    assert "without its parent conversation" in json.dumps(opened_view(api))
    interact(client, submission(context_id))
    assert Report.objects.get().source.external_message_id == "1758400000.000200"


def test_direct_message_is_rejected_without_storing_text(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    payload = shortcut(channel={"id": "D0DIRECT", "name": "directmessage"})
    assert interact(client, payload).status_code == 200
    assert opened_view(api)["title"]["text"] == "Can't capture"
    assert not SlackCaptureContext.objects.exists()
    api.eligible.assert_not_called()


def test_unapproved_channel_is_rejected(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    interact(client, shortcut(channel={"id": "C0OTHER"}))
    assert opened_view(api)["title"]["text"] == "Can't capture"
    assert not SlackCaptureContext.objects.exists()


def test_channel_that_became_ineligible_fails_closed_on_submit(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    interact(client, shortcut())
    context_id = opened_view(api)["private_metadata"]
    api.eligible.side_effect = ChannelRejected("archived", CHANNEL)
    slack_inbound.revalidate_capture_channel(context_id)
    assert SlackCaptureContext.objects.get().text == ""

    response = interact(client, submission(context_id)).json()

    assert response["view"]["title"]["text"] == "Can't capture"
    assert not Report.objects.exists()


def test_channel_removed_from_allowlist_fails_closed_on_submit(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    context_id = open_and_validate(client, api)
    AllowedChannel.objects.all().delete()
    response = interact(client, submission(context_id)).json()
    assert response["view"]["title"]["text"] == "Can't capture"
    assert not Report.objects.exists()


def test_submit_before_validation_returns_a_visible_error(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    interact(client, shortcut())
    context_id = opened_view(api)["private_metadata"]
    response = interact(client, submission(context_id)).json()
    assert response["response_action"] == "errors"
    assert "report_title" in response["errors"]
    assert not Report.objects.exists()


def test_expired_context_requires_a_new_shortcut(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    context_id = open_and_validate(client, api)
    SlackCaptureContext.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    response = interact(client, submission(context_id)).json()
    assert response["view"]["title"]["text"] == "Capture expired"
    assert not Report.objects.exists()


@pytest.mark.parametrize("who", [{"user": "U0SOMEONE"}, {"team": "T0OTHER"}])
def test_context_is_bound_to_the_signed_actor_and_team(
    client: Client, api: MagicMock, member: Membership, connection: Connection, who: dict
) -> None:
    link(member)
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, **who)).json()
    assert response["view"]["title"]["text"] == "Capture expired"
    assert not Report.objects.exists()


def test_duplicate_shortcut_and_submission_produce_one_report(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    first = open_and_validate(client, api)
    second = open_and_validate(client, api)
    interact(client, submission(first))
    response = interact(client, submission(second)).json()
    assert response["view"]["title"]["text"] == "Already captured"
    assert Report.objects.count() == 1

    interact(client, shortcut())
    assert opened_view(api)["title"]["text"] == "Already captured"
    assert SlackCaptureContext.objects.count() == 2


def test_shortcut_from_unconnected_team_does_nothing(
    client: Client, api: MagicMock, connection: Connection
) -> None:
    assert interact(client, shortcut(team={"id": "T0UNKNOWN"})).status_code == 200
    api.open_view.assert_not_called()
    assert not SlackCaptureContext.objects.exists()


def test_revoked_credentials_during_capture_disable_the_connection(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    api.eligible.side_effect = slack_error("token_revoked")
    interact(client, shortcut())
    connection.refresh_from_db()
    assert (connection.status, connection.error_code) == ("error", "credentials_revoked")


# Linking


def test_unlinked_actor_links_with_a_web_code_on_first_capture(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    code = slack_identity.issue_link_code(member).secret
    context_id = open_and_validate(client, api)
    assert any(b.get("block_id") == "slack_link_code" for b in opened_view(api)["blocks"])

    interact(client, submission(context_id, link_code=code))

    identity = ExternalIdentity.objects.get()
    assert (identity.membership, identity.provider_team_id, identity.provider_user_id) == (
        member,
        TEAM,
        ACTOR,
    )
    assert Report.objects.get().submitted_by == member


def test_link_code_cannot_be_reused(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    code = slack_identity.issue_link_code(member).secret
    slack_identity.redeem_link_code(
        code, workspace_id=member.workspace_id, team_id=TEAM, user_id="U0FIRST"
    )
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, link_code=code)).json()
    assert response["errors"]["slack_link_code"] == "This linking code is invalid or expired."
    assert not Report.objects.exists()


def test_expired_link_code_is_rejected(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    code = slack_identity.issue_link_code(member).secret
    SlackLinkCode.objects.filter(membership=member).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, link_code=code)).json()
    assert "slack_link_code" in response["errors"]


def test_unlinked_actor_without_code_sees_a_field_error(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, link_code="")).json()
    assert "slack_link_code" in response["errors"]
    assert not Report.objects.exists()


def test_link_code_from_another_workspace_is_rejected(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    outsider = make_membership(
        user=make_user(email="outsider@example.test"),
        workspace=make_workspace(name="Other", slug="other"),
    )
    code = slack_identity.issue_link_code(outsider).secret
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, link_code=code)).json()
    assert "slack_link_code" in response["errors"]
    assert not ExternalIdentity.objects.exists()
    assert not Report.objects.exists()


def test_slack_account_cannot_link_to_two_members(member: Membership) -> None:
    other = make_membership(user=make_user(email="b@example.test"), workspace=member.workspace)
    link(member)
    code = slack_identity.issue_link_code(other).secret
    with pytest.raises(slack_identity.LinkCodeRejected):
        slack_identity.redeem_link_code(
            code, workspace_id=member.workspace_id, team_id=TEAM, user_id=ACTOR
        )


def test_revoked_membership_cannot_capture(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    link(member)
    Membership.objects.filter(pk=member.pk).update(is_active=False, revoked_at=timezone.now())
    context_id = open_and_validate(client, api)
    assert any(b.get("block_id") == "slack_link_code" for b in opened_view(api)["blocks"])
    response = interact(client, submission(context_id, link_code="")).json()
    assert "slack_link_code" in response["errors"]
    assert not Report.objects.exists()


def test_unlinked_actor_on_captured_message_sees_only_the_link_modal(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    ExternalIdentity.objects.all().delete()
    interact(client, shortcut())
    view = opened_view(api)
    assert view["title"]["text"] != "Already captured"
    assert any(b.get("block_id") == "slack_link_code" for b in view["blocks"])
    assert str(report.pk) not in json.dumps(view)
    assert slack_inbound.report_url(report) not in json.dumps(view)


def test_linking_on_a_captured_message_returns_the_existing_report(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    ExternalIdentity.objects.all().delete()
    code = slack_identity.issue_link_code(member).secret
    context_id = open_and_validate(client, api)
    response = interact(client, submission(context_id, link_code=code)).json()
    assert response["view"]["title"]["text"] == "Already captured"
    assert slack_inbound.report_url(report) in json.dumps(response["view"])
    assert Report.objects.count() == 1


def test_revoked_membership_on_captured_message_is_treated_as_unlinked(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    Membership.objects.filter(pk=member.pk).update(is_active=False, revoked_at=timezone.now())
    interact(client, shortcut())
    view = opened_view(api)
    assert any(b.get("block_id") == "slack_link_code" for b in view["blocks"])
    assert str(report.pk) not in json.dumps(view)


def test_identity_in_one_workspace_grants_nothing_in_another(member: Membership) -> None:
    link(member)
    other = make_workspace(name="Other", slug="other")
    assert (
        slack_identity.linked_membership(workspace_id=other.pk, team_id=TEAM, user_id=ACTOR) is None
    )


# Permalinks


def captured_report(client: Client, api: MagicMock, member: Membership) -> Report:
    link(member)
    interact(client, submission(open_and_validate(client, api)))
    return Report.objects.get()


def test_permalink_failure_keeps_the_report_and_retry_recovers(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    api.permalink.side_effect = slack_error("message_not_found")
    slack_inbound.resolve_permalink(report.source.pk)
    source = ReportSource.objects.get()
    assert (source.permalink, source.permalink_error) == ("", "message_not_found")
    assert Report.objects.filter(pk=report.pk).exists()

    api.permalink.side_effect = None
    sign_in(client, member)
    response = client.post(
        f"/api/workspaces/{member.workspace_id}/reports/{report.pk}/permalink/retry/"
    )
    assert response.json() == {
        "permalink": "https://slack.test/archives/C0FEEDBACK/p1",
        "permalink_error": "",
    }


def test_permalink_retry_is_workspace_scoped(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    outsider = make_membership(
        user=make_user(email="outsider@example.test"),
        workspace=make_workspace(name="Other", slug="other"),
    )
    sign_in(client, outsider)
    response = client.post(
        f"/api/workspaces/{outsider.workspace_id}/reports/{report.pk}/permalink/retry/"
    )
    assert response.status_code == 404
    api.permalink.assert_not_called()


def test_sweep_deletes_expired_contexts_and_redispatches_lost_permalinks(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    report = captured_report(client, api, member)
    ReportSource.objects.update(captured_at=timezone.now() - timedelta(minutes=5))
    SlackCaptureContext.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    api.dispatch.reset_mock()
    slack_inbound.sweep()
    assert not SlackCaptureContext.objects.exists()
    api.dispatch.assert_called_once_with(
        "connections.tasks.resolve_slack_permalink", str(report.source.pk)
    )


# Events


def test_url_verification_echoes_the_challenge(client: Client) -> None:
    response = event(client, {"type": "url_verification", "challenge": "abc"})
    assert response.json() == {"challenge": "abc"}


def uninstall(event_id: str = "Ev1", event_type: str = "app_uninstalled", **extra: Any) -> dict:
    return {
        "type": "event_callback",
        "team_id": TEAM,
        "event_id": event_id,
        "event": {"type": event_type, **extra},
    }


def test_app_uninstalled_disables_the_connection_once(
    client: Client, connection: Connection
) -> None:
    assert event(client, uninstall()).status_code == 200
    connection.refresh_from_db()
    assert (connection.status, connection.error_code, connection.version) == (
        "error",
        "app_uninstalled",
        2,
    )
    event(client, uninstall())
    connection.refresh_from_db()
    assert connection.version == 2
    assert InboundReceipt.objects.filter(provider="slack").count() == 1


def test_bot_token_revocation_disables_but_user_token_revocation_does_not(
    client: Client, connection: Connection
) -> None:
    event(client, uninstall("Ev2", "tokens_revoked", tokens={"oauth": ["U1"]}))
    connection.refresh_from_db()
    assert connection.status == "active"
    event(client, uninstall("Ev3", "tokens_revoked", tokens={"bot": ["B1"]}))
    connection.refresh_from_db()
    assert (connection.status, connection.error_code) == ("error", "credentials_revoked")


def test_disabled_connection_stops_new_captures(
    client: Client, api: MagicMock, member: Membership, connection: Connection
) -> None:
    event(client, uninstall())
    interact(client, shortcut())
    api.open_view.assert_not_called()


# Web linking API


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def test_member_issues_a_code_and_manages_only_their_own_link(
    client: Client, member: Membership
) -> None:
    other = make_membership(user=make_user(email="b@example.test"), workspace=member.workspace)
    link(other, user_id="U0OTHER")
    sign_in(client, member)
    base = f"/api/workspaces/{member.workspace_id}/slack/"

    assert client.get(base + "identity/").json()["linked"] is False
    code = client.post(base + "link-code/").json()["code"]
    slack_identity.redeem_link_code(
        code, workspace_id=member.workspace_id, team_id=TEAM, user_id=ACTOR
    )
    assert client.get(base + "identity/").json()["user_id"] == ACTOR

    assert client.post(base + "identity/unlink/").status_code == 204
    assert list(ExternalIdentity.objects.values_list("membership", flat=True)) == [other.pk]


def test_new_code_retires_the_previous_one(member: Membership) -> None:
    first = slack_identity.issue_link_code(member).secret
    slack_identity.issue_link_code(member)
    with pytest.raises(slack_identity.LinkCodeRejected):
        slack_identity.redeem_link_code(
            first, workspace_id=member.workspace_id, team_id=TEAM, user_id=ACTOR
        )
