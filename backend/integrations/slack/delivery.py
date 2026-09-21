"""Slack follow-up delivery and fail-closed connection state."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class SlackDeliveryClient(Protocol):
    def conversations_open(self, *, users: str) -> Any: ...

    def chat_postMessage(self, *, channel: str, text: str) -> Any: ...


class DeliveryRejected(PermissionError):
    """Raised before a Slack write when the connection or member is invalid."""


@dataclass
class SlackConnectionGuard:
    team_id: str
    active: bool = True
    disabled_reason: str | None = None
    pending_send_ids: set[str] = field(default_factory=set)

    def require_active(self) -> None:
        if not self.active:
            raise DeliveryRejected(self.disabled_reason or "Slack connection is disabled")

    def begin_send(self, send_id: str) -> None:
        self.require_active()
        self.pending_send_ids.add(send_id)

    def finish_send(self, send_id: str) -> None:
        self.pending_send_ids.discard(send_id)

    def disable(self, reason: str) -> None:
        self.active = False
        self.disabled_reason = reason
        self.pending_send_ids.clear()

    def disable_for_uninstall(self, team_id: str) -> bool:
        """Disable only when the verified event belongs to this connection."""
        if team_id != self.team_id:
            return False
        self.disable("app_uninstalled")
        return True


def slack_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    data = getattr(response, "data", None)
    code = data.get("error") if isinstance(data, dict) else None
    return code if isinstance(code, str) else None


REVOCATION_ERRORS = frozenset({"account_inactive", "invalid_auth", "not_authed", "token_revoked"})


def handle_provider_error(guard: SlackConnectionGuard, error: Exception) -> None:
    """Record revoked credentials so later actions fail before external writes."""
    code = slack_error_code(error)
    if code in REVOCATION_ERRORS:
        guard.disable(f"Slack credentials revoked: {code}")


@dataclass(frozen=True)
class DeliveredMessage:
    conversation_id: str
    message_ts: str | None


def send_delayed_dm(
    client: SlackDeliveryClient,
    guard: SlackConnectionGuard,
    *,
    send_id: str,
    actor_id: str,
    text: str,
    member_is_active: Callable[[], bool],
) -> DeliveredMessage:
    """Open the employee DM and post directly, even after capture is old."""
    guard.begin_send(send_id)
    try:
        if not member_is_active():
            raise DeliveryRejected("Slack member is no longer active")
        try:
            guard.require_active()
            opened = client.conversations_open(users=actor_id)
            conversation = opened.get("channel")
            conversation_id = conversation.get("id") if isinstance(conversation, dict) else None
            if not isinstance(conversation_id, str) or not conversation_id:
                raise ValueError("Slack did not return a DM conversation id")
            if not member_is_active():
                raise DeliveryRejected("Slack member was revoked before message send")
            guard.require_active()
            posted = client.chat_postMessage(channel=conversation_id, text=text)
        except Exception as error:
            handle_provider_error(guard, error)
            raise
        message_ts = posted.get("ts")
        return DeliveredMessage(
            conversation_id=conversation_id,
            message_ts=message_ts if isinstance(message_ts, str) else None,
        )
    finally:
        guard.finish_send(send_id)
