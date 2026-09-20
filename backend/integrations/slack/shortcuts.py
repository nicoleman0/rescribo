"""Message shortcut payload parsing and source eligibility rules."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class ShortcutPayloadError(ValueError):
    """Raised when an interaction payload is not a well-formed message shortcut."""


class SourceRejected(ValueError):
    """Raised when a shortcut source channel is not eligible.

    The message names the reason code and the channel id only; never the
    message text or actor identity.
    """

    def __init__(self, reason: str, channel_id: str) -> None:
        super().__init__(f"{reason}:{channel_id}")
        self.reason = reason
        self.channel_id = channel_id


@dataclass(frozen=True)
class MessageShortcut:
    callback_id: str
    team_id: str
    channel_id: str
    channel_name: str | None
    actor_id: str
    message_ts: str
    thread_ts: str | None
    text: str
    trigger_id: str

    @property
    def is_thread_reply(self) -> bool:
        return self.thread_ts is not None and self.thread_ts != self.message_ts

    def source_key(self) -> str:
        return f"{self.team_id}:{self.channel_id}:{self.message_ts}"


def _require_string(payload: Mapping[str, Any], *path: str | int) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise ShortcutPayloadError(f"Missing field: {'.'.join(str(k) for k in path)}")
        value = value[key]
    if not isinstance(value, str) or not value:
        raise ShortcutPayloadError(f"Unexpected type at {'.'.join(str(k) for k in path)}")
    return value


def parse_message_shortcut(payload: Mapping[str, Any]) -> MessageShortcut:
    """Parse an interactivity `message_action` payload into a `MessageShortcut`.

    Validates shape and types; never trusts the reported structure.
    """
    if payload.get("type") != "message_action":
        raise ShortcutPayloadError("Interaction is not a message_action shortcut.")
    message = payload.get("message")
    if not isinstance(message, Mapping):
        raise ShortcutPayloadError("Missing field: message")
    thread_ts = message.get("thread_ts")
    if thread_ts is not None and not isinstance(thread_ts, str):
        raise ShortcutPayloadError("Unexpected type at message.thread_ts")
    channel_name = payload.get("channel")
    if isinstance(channel_name, Mapping) and isinstance(channel_name.get("name"), str):
        channel_name = channel_name["name"]
    else:
        channel_name = None
    return MessageShortcut(
        callback_id=_require_string(payload, "callback_id"),
        team_id=_require_string(payload, "team", "id"),
        channel_id=_require_string(payload, "channel", "id"),
        channel_name=channel_name,
        actor_id=_require_string(payload, "user", "id"),
        message_ts=_require_string(message, "ts"),
        thread_ts=thread_ts if isinstance(thread_ts, str) and thread_ts else None,
        text=_require_string(message, "text"),
        trigger_id=_require_string(payload, "trigger_id"),
    )


def check_source_allowed(
    shortcut: MessageShortcut, *, approved_channel_ids: frozenset[str]
) -> None:
    """Reject DMs and unapproved channels, raising `SourceRejected`."""
    if shortcut.channel_id.startswith("D") or shortcut.channel_name == "directmessage":
        raise SourceRejected("direct_message", shortcut.channel_id)
    if shortcut.channel_id not in approved_channel_ids:
        raise SourceRejected("unapproved_channel", shortcut.channel_id)
