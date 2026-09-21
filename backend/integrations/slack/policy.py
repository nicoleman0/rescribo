"""Slack source policy and the short-lived modal validation cache."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic
from typing import Any

REQUIRED_BOT_SCOPES = frozenset(
    {"commands", "channels:read", "groups:read", "chat:write", "im:write"}
)


class ChannelRejected(ValueError):
    """Raised when a Slack conversation cannot be an approved source."""

    def __init__(self, channel_id: str, reason: str) -> None:
        super().__init__(f"{reason}:{channel_id}")
        self.channel_id = channel_id
        self.reason = reason


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
            raise ChannelRejected("unknown", "missing_channel_id")
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
        raise ChannelRejected(channel.channel_id, "direct_message")
    if channel.is_mpim:
        raise ChannelRejected(channel.channel_id, "group_direct_message")
    if channel.is_ext_shared:
        raise ChannelRejected(channel.channel_id, "externally_shared")
    if channel.is_archived:
        raise ChannelRejected(channel.channel_id, "archived")
    if not channel.is_member:
        raise ChannelRejected(channel.channel_id, "bot_not_member")
    return channel


class ChannelEligibilityCache:
    """Cache only the startup check; submissions always fetch fresh state."""

    def __init__(
        self,
        fetch: Callable[[str], Mapping[str, Any]],
        *,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._fetch = fetch
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._startup: dict[str, tuple[SlackChannel, float]] = {}

    def validate_for_modal_start(self, channel_id: str) -> SlackChannel:
        """Use a short-lived cached result while opening the capture modal."""
        now = self._clock()
        cached = self._startup.get(channel_id)
        if cached is not None and cached[1] > now:
            return cached[0]
        channel = validate_channel(self._fetch(channel_id))
        self._startup[channel_id] = (channel, now + self._ttl_seconds)
        return channel

    def validate_for_submission(self, channel_id: str) -> SlackChannel:
        """Revalidate at submit time and fail closed on any provider error."""
        channel = validate_channel(self._fetch(channel_id))
        self._startup.pop(channel_id, None)
        return channel
