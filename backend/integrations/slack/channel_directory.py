"""Django-free Slack channel directory pagination shared with live checks."""

from typing import Any

PAGE_SIZE = 200
MAX_LISTED_CHANNELS = 1000


def collect_member_channels(client: Any) -> tuple[list[dict[str, Any]], bool]:
    """Return up to 1,000 bot memberships and whether more were available."""
    channels: list[dict[str, Any]] = []
    cursor = ""
    while len(channels) < MAX_LISTED_CHANNELS:
        response = client.users_conversations(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=PAGE_SIZE,
            cursor=cursor,
        )
        channels.extend(response.get("channels", []))
        if len(channels) >= MAX_LISTED_CHANNELS:
            channels = channels[:MAX_LISTED_CHANNELS]
            return channels, bool(response.get("response_metadata", {}).get("next_cursor"))
        cursor = response.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            return channels, False
    return channels, False
