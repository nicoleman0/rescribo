"""Slack outcome-action orchestration.

The signed team, the signed actor, and the follow-up ID are all the inputs we
trust. Slack only tells us they were clicked; the rules in `feedback.follow_ups`
decide whether anything changes. A rejected click posts an ephemeral reply and
leaves every row alone.
"""

import logging
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from connections import slack_identity
from connections.models import Connection
from feedback.errors import FeedbackError
from feedback.follow_ups import record_outcome
from feedback.models import FollowUp, ReportNotificationOperation
from integrations.slack import client
from integrations.slack.errors import slack_error_code
from integrations.slack.messages import (
    CONFIRMED_BLOCK,
    CONTACTED_BLOCK,
    outcome_message_blocks,
)

logger = logging.getLogger(__name__)

OUTCOME_ACTIONS = {CONTACTED_BLOCK: "contacted", CONFIRMED_BLOCK: "confirmed"}


class OutcomeRejected(Exception):
    """The button click is from the wrong actor or workspace; tell them why."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _channel_and_ts(payload: dict[str, Any]) -> tuple[str, str, str] | None:
    """Resolve (channel_id, message_ts, actor_user_id) from the payload."""
    channel = payload.get("channel") or {}
    container = payload.get("container") or {}
    channel_id = channel.get("id") if isinstance(channel, dict) else None
    if not channel_id and isinstance(container, dict):
        channel_id = container.get("channel_id")
    message_ts = container.get("message_ts") if isinstance(container, dict) else None
    user = payload.get("user") or {}
    user_id = user.get("id") if isinstance(user, dict) else None
    if not (
        isinstance(channel_id, str) and channel_id and isinstance(message_ts, str) and message_ts
    ):
        return None
    return channel_id, message_ts, user_id or ""


def _team_id(payload: dict[str, Any]) -> str:
    team = payload.get("team") or {}
    if isinstance(team, dict):
        identifier = team.get("id")
        if isinstance(identifier, str):
            return identifier
    if isinstance(payload.get("enterprise"), dict):
        identifier = payload["enterprise"].get("id")
        if isinstance(identifier, str):
            return identifier
    return ""


def handle_outcome_action(*, payload: dict[str, Any], action_id: str, value: str) -> dict[str, Any]:
    """Apply one outcome button click or return the ephemeral reply Slack should show.

    Slack expects an HTTP 200 with a JSON body that contains `response_type` and
    the text to show the actor. The `text` field becomes the ephemeral message.
    """
    try:
        follow_up_id = UUID(value)
    except ValueError as error:
        raise OutcomeRejected("This outcome button is no longer valid.") from error
    team_id = _team_id(payload)
    connection = _team_connection(team_id=team_id)
    channel_info = _channel_and_ts(payload)
    actor_user_id = channel_info[2] if channel_info else ""
    actor = slack_identity.linked_membership(
        workspace_id=connection.workspace_id,
        team_id=connection.external_id,
        user_id=actor_user_id,
    )
    if actor is None:
        raise OutcomeRejected(
            "Only the Rescribo member who owns this follow-up can record an outcome."
        )
    follow_up, message, operation = _resolve_target(
        actor=actor,
        follow_up_id=follow_up_id,
    )
    next_state = OUTCOME_ACTIONS[action_id]
    _record(
        actor=actor,
        follow_up=follow_up,
        state=next_state,
        team_id=team_id,
        provider_user_id=actor_user_id,
    )
    if channel_info and operation is not None:
        _update_dm(
            connection=connection,
            channel_id=channel_info[0],
            message_ts=channel_info[1],
            follow_up=follow_up,
            outcome=next_state,
            actor=actor,
            message=message,
        )
    return {
        "response_type": "ephemeral",
        "text": f"Recorded {next_state}.",
    }


def _team_connection(*, team_id: str) -> Connection:
    if not team_id:
        raise OutcomeRejected("This Slack workspace is not connected to Rescribo.")
    connection = (
        Connection.objects.select_related("workspace")
        .filter(
            provider=Connection.Provider.SLACK,
            external_id=team_id,
            status=Connection.Status.ACTIVE,
        )
        .first()
    )
    if connection is None:
        raise OutcomeRejected("This Slack workspace is not connected to Rescribo.")
    return connection


def _resolve_target(
    *, actor: Membership, follow_up_id: UUID
) -> tuple[FollowUp, str, ReportNotificationOperation | None]:
    """Confirm the follow-up exists in the connection's workspace and the actor owns it."""
    with transaction.atomic():
        follow_up = (
            FollowUp.objects.select_for_update()
            .filter(pk=follow_up_id, workspace_id=actor.workspace_id)
            .first()
        )
    if follow_up is None:
        raise OutcomeRejected("This follow-up is no longer available.")
    if follow_up.recipient_id != actor.pk:
        raise OutcomeRejected("Only the Rescribo member who owns this follow-up can record.")
    operation = (
        ReportNotificationOperation.objects.filter(
            workspace_id=actor.workspace_id, follow_up=follow_up
        )
        .exclude(state=ReportNotificationOperation.State.CANCELLED)
        .first()
    )
    return follow_up, operation.message if operation else "", operation


def _record(
    *, actor: Membership, follow_up: FollowUp, state: str, team_id: str, provider_user_id: str
) -> None:
    try:
        record_outcome(
            actor=actor,
            follow_up_id=follow_up.pk,
            state=state,
            note="",
            expected_version=follow_up.version,
            now=timezone.now(),
            slack_team_id=team_id,
            slack_user_id=provider_user_id,
        )
    except FeedbackError as error:
        raise OutcomeRejected(str(error) or "This outcome could not be recorded.") from error


def _update_dm(
    *,
    connection: Connection,
    channel_id: str,
    message_ts: str,
    follow_up: FollowUp,
    outcome: str,
    actor: Membership,
    message: str,
) -> None:
    blocks = outcome_message_blocks(
        message=message,
        outcome=outcome,
        actor=actor.user.full_name or "a member",
        follow_up_id=str(follow_up.pk),
    )
    try:
        client.chat_update(
            connection.credential,
            channel=channel_id,
            ts=message_ts,
            text=message,
            blocks=blocks,
        )
    except Exception as error:  # noqa: BLE001 - chat.update failure must not change state
        logger.warning(
            "Slack chat.update failed for follow-up %s: %s",
            follow_up.pk,
            slack_error_code(error) or type(error).__name__,
        )
