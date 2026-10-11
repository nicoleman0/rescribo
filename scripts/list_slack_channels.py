#!/usr/bin/env python3
"""List the Slack channels the bot is in, to pick channels to approve.

Run with `task slack-channels`. Reads the bot token from `.env.slack-feasibility`.
"""

import sys
from pathlib import Path
from typing import Any

import environ
from slack_sdk import WebClient

from live_check import required_environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

from integrations.slack.client import collect_member_channels  # noqa: E402

environ.Env.read_env(REPOSITORY_ROOT / ".env.slack-feasibility", overwrite=False)


def list_channels(client: WebClient) -> tuple[list[dict[str, Any]], bool]:
    channels, truncated = collect_member_channels(client)
    return sorted(channels, key=lambda channel: str(channel["name"])), truncated


def main() -> None:
    client = WebClient(token=required_environment("RESCRIBO_SLACK_BOT_TOKEN"))
    channels, truncated = list_channels(client)
    print(f"{'id':<14} {'kind':<8} name")
    for channel in channels:
        kind = "private" if channel["is_private"] else "public"
        print(f"{channel['id']:<14} {kind:<8} #{channel['name']}")
    if truncated:
        print("Channel list was cut short at 1,000 channels.")


if __name__ == "__main__":
    main()
