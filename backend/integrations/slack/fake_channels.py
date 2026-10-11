"""Deterministic channel directory for development and end-to-end runs."""

from typing import Any

from slack_sdk.errors import SlackApiError

CHANNELS = [
    {
        "id": "C0E2EPUBLIC",
        "name": "support-requests",
        "is_private": False,
        "is_archived": False,
        "is_ext_shared": False,
        "is_im": False,
        "is_mpim": False,
    },
    {
        "id": "G0E2EPRIVATE",
        "name": "key-accounts",
        "is_private": True,
        "is_archived": False,
        "is_ext_shared": False,
        "is_im": False,
        "is_mpim": False,
    },
    {
        "id": "C0E2ESHARED",
        "name": "partner-shared",
        "is_private": False,
        "is_archived": False,
        "is_ext_shared": True,
        "is_im": False,
        "is_mpim": False,
    },
]


class FakeDirectoryClient:
    def users_conversations(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "channels": [dict(channel) for channel in CHANNELS],
            "response_metadata": {"next_cursor": ""},
        }

    def conversations_info(self, *, channel: str) -> dict[str, Any]:
        for value in CHANNELS:
            if value["id"] == channel:
                return {"ok": True, "channel": {**value, "is_member": True}}
        response = {"ok": False, "error": "channel_not_found"}
        raise SlackApiError(message="channel_not_found", response=response)


_fake = FakeDirectoryClient()


def fake_directory_client() -> FakeDirectoryClient:
    return _fake
