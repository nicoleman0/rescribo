#!/usr/bin/env python3
"""List Slack channel ids and bot membership, to pick channels to approve.

Run with `task slack-channels`. Reads the bot token from `.env.slack-feasibility`.
"""

from pathlib import Path
from typing import Any

import environ
from slack_sdk import WebClient

from live_check import required_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
environ.Env.read_env(REPOSITORY_ROOT / ".env.slack-feasibility", overwrite=False)


def list_channels(client: WebClient) -> list[dict[str, Any]]:
    response = client.conversations_list(
        types="public_channel,private_channel", exclude_archived=True, limit=200
    )
    channels: list[dict[str, Any]] = list(response["channels"])
    return sorted(channels, key=lambda channel: str(channel["name"]))


def main() -> None:
    client = WebClient(token=required_environment("RESCRIBO_SLACK_BOT_TOKEN"))
    channels = list_channels(client)
    print(f"{'id':<14} {'kind':<8} {'bot in?':<8} name")
    for channel in channels:
        kind = "private" if channel["is_private"] else "public"
        member = "yes" if channel["is_member"] else "no"
        print(f"{channel['id']:<14} {kind:<8} {member:<8} #{channel['name']}")


if __name__ == "__main__":
    main()
