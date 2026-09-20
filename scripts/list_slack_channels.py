#!/usr/bin/env python3
"""List the feasibility workspace's channel ids for the opt-in Slack checks.

Run with `task slack-channels`. Reads the bot token from `.env.slack-feasibility`
and prints the ids the shortcut capture check needs, with the command to run.
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


def print_suggested_command(channels: list[dict[str, Any]]) -> None:
    """Print a shortcut check command, using the first joined channel of each kind."""
    joined = [channel for channel in channels if channel["is_member"]]
    public = next((channel for channel in joined if not channel["is_private"]), None)
    private = next((channel for channel in joined if channel["is_private"]), None)
    if public is None or private is None:
        print("\nInvite the bot to one public and one private channel, then run this again.")
        return
    print("\nSuggested command. Confirm the channel names above are the approved pair:\n")
    print(
        "task slack-shortcut-check -- \\\n"
        "  --workspace feasibility-a \\\n"
        '  --workspace-name "Feasibility A" \\\n'
        f"  --public-channel {public['id']} \\\n"
        f"  --private-channel {private['id']} \\\n"
        "  --fail-first-submission"
    )


def main() -> None:
    client = WebClient(token=required_environment("RESCRIBO_SLACK_BOT_TOKEN"))
    channels = list_channels(client)
    print(f"{'id':<14} {'kind':<8} {'bot in?':<8} name")
    for channel in channels:
        kind = "private" if channel["is_private"] else "public"
        member = "yes" if channel["is_member"] else "no"
        print(f"{channel['id']:<14} {kind:<8} {member:<8} #{channel['name']}")
    print_suggested_command(channels)


if __name__ == "__main__":
    main()
