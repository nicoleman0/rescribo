#!/usr/bin/env python3
"""Run the terminal-driven live checks for Slack issue #26.

The default checks are read-only. Delayed DM delivery is an explicit live
write selected with ``--send-delayed-dm``. Output contains no token or message
content and is suitable for a sanitised evidence file.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import environ
from slack_sdk import WebClient

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
environ.Env.read_env(REPOSITORY_ROOT / ".env.slack-feasibility", overwrite=False)

from integrations.slack import (  # noqa: E402
    ChannelRejected,
    SlackConnectionGuard,
    send_delayed_dm,
    validate_channel,
)
from live_check import required_environment  # noqa: E402
from slack_live import check_granted_scopes  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-channel", required=True)
    parser.add_argument("--private-channel", required=True)
    parser.add_argument("--message-channel", help="Channel containing the message for getPermalink")
    parser.add_argument("--message-ts", help="Message timestamp for getPermalink")
    parser.add_argument("--actor-id", help="Linked Slack actor for the optional delayed DM")
    parser.add_argument(
        "--captured-at",
        help="UTC ISO timestamp of the capture; delayed-DM evidence requires at least 30 minutes",
    )
    parser.add_argument(
        "--send-delayed-dm",
        action="store_true",
        help="Perform the live conversations.open and chat.postMessage check",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / ".cache" / "slack-issue26-result.json",
    )
    args = parser.parse_args()
    # Settle the argument contract before the first live call, so a missing
    # flag costs nothing.
    if bool(args.message_channel) != bool(args.message_ts):
        parser.error("--message-channel and --message-ts must be supplied together")
    if args.send_delayed_dm:
        if not args.actor_id or not args.captured_at:
            parser.error("--send-delayed-dm requires --actor-id and --captured-at")
        args.captured_at = parse_capture_time(parser, args.captured_at)
    return args


def parse_capture_time(parser: argparse.ArgumentParser, value: str) -> datetime:
    try:
        captured = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parser.error(f"--captured-at is not an ISO timestamp: {value}")
    if captured.tzinfo is None:
        parser.error("--captured-at needs a UTC offset, for example 2026-09-21T10:00:00Z")
    if (datetime.now(UTC) - captured.astimezone(UTC)).total_seconds() <= 30 * 60:
        parser.error("--captured-at must be more than 30 minutes ago for live evidence")
    return captured


def check_channel(client: WebClient, channel_id: str) -> dict[str, Any]:
    response = client.conversations_info(channel=channel_id)
    data = response.get("channel")
    if not isinstance(data, dict):
        raise RuntimeError("Slack conversations.info returned no channel")
    try:
        channel = validate_channel(data)
    except ChannelRejected as error:
        return {"channel_id": channel_id, "eligible": False, "reason": error.reason}
    return {
        "channel_id": channel.channel_id,
        "eligible": True,
        "kind": "private" if channel.is_private else "public",
    }


def check_permalink(client: WebClient, channel_id: str, message_ts: str) -> dict[str, Any]:
    response = client.chat_getPermalink(channel=channel_id, message_ts=message_ts)
    return {
        "channel_id": channel_id,
        "message_ts_supplied": True,
        "resolved": bool(response.get("permalink")),
    }


def check_delayed_dm(
    client: WebClient, *, actor_id: str, captured_at: datetime, team_id: str
) -> dict[str, Any]:
    age_seconds = (datetime.now(UTC) - captured_at.astimezone(UTC)).total_seconds()
    guard = SlackConnectionGuard(team_id=team_id)
    result = send_delayed_dm(
        client,
        guard,
        send_id="issue-26-delayed-dm",
        actor_id=actor_id,
        text="Rescribo Slack feasibility check: delayed follow-up delivery.",
        member_is_active=lambda: True,
    )
    return {
        "sent": True,
        "age_seconds": round(age_seconds),
        "conversation_id": result.conversation_id,
        "message_ts_returned": result.message_ts is not None,
        "used_temporary_response_url": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    client = WebClient(token=required_environment("RESCRIBO_SLACK_BOT_TOKEN"))
    evidence: dict[str, Any] = {
        "check": "slack-issue-26",
        "evidence_mode": "live_api",
        "scope_check": check_granted_scopes(client),
        "channels": [
            check_channel(client, args.public_channel),
            check_channel(client, args.private_channel),
        ],
        "permalink": None,
        "delayed_dm": None,
    }
    if args.message_channel and args.message_ts:
        evidence["permalink"] = check_permalink(client, args.message_channel, args.message_ts)
    if args.send_delayed_dm:
        team_id = str(evidence["scope_check"]["team_id"])
        evidence["delayed_dm"] = check_delayed_dm(
            client, actor_id=args.actor_id, captured_at=args.captured_at, team_id=team_id
        )
    return evidence


def display_path(path: Path) -> str:
    """Name a repository path relatively; leave any other path as given."""
    return str(path.relative_to(REPOSITORY_ROOT) if path.is_relative_to(REPOSITORY_ROOT) else path)


def main() -> None:
    args = parse_args()
    evidence = run(args)
    output = json.dumps(evidence, indent=2, sort_keys=True)
    print(output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{output}\n", encoding="utf-8")
    print(f"Sanitised result written to {display_path(args.output)}")


if __name__ == "__main__":
    main()
