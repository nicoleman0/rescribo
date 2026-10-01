"""Slack source channel policy."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from integrations.slack.errors import ChannelRejected

REQUIRED_BOT_SCOPES = frozenset(
    {"commands", "channels:read", "groups:read", "chat:write", "im:write"}
)


@dataclass(frozen=True)
class SlackChannel:
    """The channel fields needed for the source policy."""

    channel_id: str
    is_private: bool
    is_archived: bool
    is_member: bool
    is_ext_shared: bool
    is_im: bool
    is_mpim: bool

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> SlackChannel:
        channel_id = data.get("id")
        if not isinstance(channel_id, str) or not channel_id:
            raise ChannelRejected("missing_channel_id", "unknown")
        return cls(
            channel_id=channel_id,
            is_private=data.get("is_private") is True,
            is_archived=data.get("is_archived") is True,
            is_member=data.get("is_member") is True,
            is_ext_shared=data.get("is_ext_shared") is True,
            is_im=data.get("is_im") is True,
            is_mpim=data.get("is_mpim") is True,
        )


def validate_channel(data: Mapping[str, Any]) -> SlackChannel:
    """Validate an internal, active channel containing the bot."""
    channel = SlackChannel.from_api(data)
    if channel.is_im:
        raise ChannelRejected("direct_message", channel.channel_id)
    if channel.is_mpim:
        raise ChannelRejected("group_direct_message", channel.channel_id)
    if channel.is_ext_shared:
        raise ChannelRejected("externally_shared", channel.channel_id)
    if channel.is_archived:
        raise ChannelRejected("archived", channel.channel_id)
    if not channel.is_member:
        raise ChannelRejected("bot_not_member", channel.channel_id)
    return channel
