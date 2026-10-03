"""Slack outcome-button clicks over the signed interactions endpoint.

The signed team and the signed actor are the source of trust; the rules live
in `feedback.follow_ups`. Slack API calls are mocked, not live evidence.
"""

import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.test import Client, override_settings
from django.utils import timezone

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections.models import Connection, ExternalIdentity
from feedback.follow_ups import change_recipient, record_outcome
from feedback.models import Activity, FollowUp
from feedback.problems import confirm_fix
from feedback.reports import link_report
from integrations.slack.messages import (
    CONFIRMED_BLOCK,
    CONTACTED_BLOCK,
    follow_up_message_blocks,
    outcome_message_blocks,
)

pytestmark = pytest.mark.django_db

SECRET = "slack-signing-secret"
INTERACTIONS = "/api/integrations/slack/interactions/"
TEAM = "T0TEAM"
CHANNEL = "D0DM"
ACTOR = "U0ACTOR"
TS = "171.5"


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


@pytest.fixture(autouse=True)
def slack_settings() -> Iterator[None]:
    with override_settings(
        RESCRIBO_SLACK_SIGNING_SECRET=SECRET, RESCRIBO_PUBLIC_BASE_URL="https://app.test"
    ):
        yield


def fixed_report(actor: Membership, *, recipient: Membership | None = None) -> Any:
    problem = make_problem(actor=actor, title="Broken export")
    report = make_report(actor=actor, title="Export fails")
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed.",
        fix_version="1.0",
    )
    if recipient is not None:
        follow_up = report.follow_ups.get()
        FollowUp.objects.filter(pk=follow_up.pk).update(recipient=recipient)
    report.refresh_from_db()
    return report


def setup_world(*, actor_user_id: str = ACTOR) -> tuple[Membership, FollowUp, Connection]:
    actor = make_membership(role=Membership.Role.OWNER)
    connection = Connection.objects.create(
        workspace=actor.workspace,
        provider=Connection.Provider.SLACK,
        external_id=TEAM,
        identity="Acme Slack",
        status=Connection.Status.ACTIVE,
        credential="encrypted",
    )
    ExternalIdentity.objects.create(
        workspace=actor.workspace,
        membership=actor,
        provider=Connection.Provider.SLACK,
        provider_team_id=TEAM,
        provider_user_id=actor_user_id,
    )
    report = fixed_report(actor)
    make_notification(
        report=report,
        state="sent",
        sent_at=timezone.now(),
        remote_conversation_id=CHANNEL,
        remote_message_id=TS,
        message="The fix is available.",
    )
    follow_up = report.follow_ups.get()
    return actor, follow_up, connection


def action_payload(
    action_id: str, follow_up_id: Any, *, actor_user_id: str = ACTOR
) -> dict[str, Any]:
    return {
        "type": "block_actions",
        "team": {"id": TEAM},
        "user": {"id": actor_user_id},
        "channel": {"id": CHANNEL},
        "container": {"channel_id": CHANNEL, "message_ts": TS},
        "actions": [{"action_id": action_id, "value": str(follow_up_id)}],
    }


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def test_contacted_button_records_outcome_and_updates_dm(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    response = interact(
        client,
        action_payload("follow_up_contacted", follow_up.pk),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "ephemeral"
    assert "contacted" in body["text"].lower()
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.CONTACTED
    activity = Activity.objects.get(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.OUTCOME_RECORDED,
    )
    assert activity.actor_membership_id == actor.pk


def test_confirmed_button_records_outcome_from_contacted(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    record_outcome(
        actor=actor,
        follow_up_id=follow_up.pk,
        state=FollowUp.ContactState.CONTACTED,
        note="",
        expected_version=1,
    )
    response = interact(
        client,
        action_payload("follow_up_confirmed", follow_up.pk),
    )
    assert response.status_code == 200
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.CONFIRMED


@pytest.mark.parametrize(
    "who",
    [
        "unconnected_team",
        "unlinked_actor",
        "unrelated_member",
        "former_recipient",
        "revoked_member",
        "other_workspace",
        "inactive_connection",
    ],
)
def test_rejected_clicks_post_ephemeral_without_changing_state(client: Client, who: str) -> None:
    actor, follow_up, connection = setup_world()

    if who == "unconnected_team":
        payload = action_payload("follow_up_contacted", follow_up.pk)
        payload["team"] = {"id": "T0UNKNOWN"}
    elif who == "unlinked_actor":
        ExternalIdentity.objects.filter(membership=actor).delete()
        payload = action_payload("follow_up_contacted", follow_up.pk, actor_user_id="U0NEW")
    elif who == "unrelated_member":
        other = make_membership(
            workspace=actor.workspace, user=make_user(email="unrelated@example.test")
        )
        ExternalIdentity.objects.create(
            workspace=actor.workspace,
            membership=other,
            provider=Connection.Provider.SLACK,
            provider_team_id=TEAM,
            provider_user_id="U0UNRELATED",
        )
        payload = action_payload("follow_up_contacted", follow_up.pk, actor_user_id="U0UNRELATED")
    elif who == "former_recipient":
        other = make_membership(workspace=actor.workspace, user=make_user(email="o@example.test"))
        FollowUp.objects.filter(pk=follow_up.pk).update(recipient=other)
        ExternalIdentity.objects.create(
            workspace=actor.workspace,
            membership=other,
            provider=Connection.Provider.SLACK,
            provider_team_id=TEAM,
            provider_user_id="U0RECIP",
        )
        payload = action_payload("follow_up_contacted", follow_up.pk)
    elif who == "revoked_member":
        Membership.objects.filter(pk=actor.pk).update(is_active=False, revoked_at=timezone.now())
        payload = action_payload("follow_up_contacted", follow_up.pk)
    elif who == "other_workspace":
        other_workspace = make_workspace(slug="other", name="Other")
        other_actor = make_membership(
            workspace=other_workspace,
            user=make_user(email="other@example.test"),
        )
        ExternalIdentity.objects.filter(membership=actor).update(membership=other_actor)
        payload = action_payload("follow_up_contacted", follow_up.pk)
    elif who == "inactive_connection":
        Connection.objects.filter(pk=connection.pk).update(status=Connection.Status.ERROR)
        payload = action_payload("follow_up_contacted", follow_up.pk)
    else:
        raise AssertionError(who)

    response = interact(client, payload)
    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "ephemeral"
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING
    assert not Activity.objects.filter(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.OUTCOME_RECORDED,
    ).exists()


def test_reassigned_recipient_can_record_outcome_from_slack(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    new_recipient = make_membership(
        workspace=actor.workspace, user=make_user(email="reassigned@example.test")
    )
    ExternalIdentity.objects.create(
        workspace=actor.workspace,
        membership=new_recipient,
        provider=Connection.Provider.SLACK,
        provider_team_id=TEAM,
        provider_user_id="U0REASSIGNED",
    )
    change_recipient(actor=actor, follow_up_id=follow_up.pk, new_recipient_id=new_recipient.pk)
    response = interact(
        client,
        action_payload("follow_up_contacted", follow_up.pk, actor_user_id="U0REASSIGNED"),
    )
    assert response.status_code == 200
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.CONTACTED


def test_contacted_message_retains_confirmation_then_removes_completed_action(
    client: Client,
) -> None:
    actor, follow_up, _ = setup_world()
    with patch("integrations.slack.client.chat_update") as update:
        first = interact(client, action_payload(CONTACTED_BLOCK, follow_up.pk))
        assert first.status_code == 200
        blocks = update.call_args.kwargs["blocks"]
        next_action = next(
            item["action_id"]
            for block in blocks
            if block["type"] == "actions"
            for item in block["elements"]
        )
        assert next_action == CONFIRMED_BLOCK
        second = interact(client, action_payload(next_action, follow_up.pk))
        assert second.status_code == 200
        blocks = update.call_args.kwargs["blocks"]
        assert not [block for block in blocks if block["type"] == "actions"]


@pytest.mark.parametrize("length", [1, 3000, 3001, 10000])
def test_slack_message_content_is_split_without_loss(length: int) -> None:
    message = "x" * length
    blocks = follow_up_message_blocks(message=message, follow_up_id="fu-1")
    sections = [block["text"]["text"] for block in blocks if block["type"] == "section"]
    assert "".join(sections) == message
    assert all(len(value) <= 3000 for value in sections)
    updated = outcome_message_blocks(
        message=message, outcome="contacted", actor="Ada", follow_up_id="fu-1"
    )
    updated_sections = [block["text"]["text"] for block in updated if block["type"] == "section"]
    assert "".join(updated_sections[: len(sections)]) == message
    assert all(len(value) <= 3000 for value in updated_sections[: len(sections)])


def test_unknown_action_id_is_silently_ignored(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    payload = action_payload("some_other_action", follow_up.pk)
    response = interact(client, payload)
    assert response.status_code == 200
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING


def test_invalid_uuid_value_is_rejected(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    payload = action_payload("follow_up_contacted", follow_up.pk)
    payload["actions"] = [{"action_id": "follow_up_contacted", "value": "not-a-uuid"}]
    response = interact(client, payload)
    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "ephemeral"
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING


def test_signature_failure_is_rejected(client: Client) -> None:
    actor, follow_up, _ = setup_world()
    body = urlencode(
        {"payload": json.dumps(action_payload("follow_up_contacted", follow_up.pk))}
    ).encode()
    response = client.post(
        INTERACTIONS,
        data=body,
        content_type="application/x-www-form-urlencoded",
        headers={
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=bad",
        },
    )
    assert response.status_code == 401
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING


def test_chat_update_failure_does_not_block_recording(client: Client) -> None:
    from slack_sdk.errors import SlackApiError
    from slack_sdk.web import SlackResponse

    actor, follow_up, _ = setup_world()
    response_obj = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/chat.update",
        req_args={},
        data={"ok": False, "error": "message_not_found"},
        headers={},
        status_code=200,
    )

    with patch(
        "integrations.slack.client.chat_update",
        side_effect=SlackApiError("message_not_found", response_obj),
    ):
        response = interact(
            client,
            action_payload("follow_up_contacted", follow_up.pk),
        )
    assert response.status_code == 200
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.CONTACTED
