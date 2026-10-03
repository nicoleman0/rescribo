"""Slack block payloads for follow-up delivery and recorded outcomes.

Blocks are the only Slack-specific surface here; delivery state lives in
connections/slack_delivery.py.
"""

import json
from typing import Any

CONTACTED_BLOCK = "follow_up_contacted"
CONFIRMED_BLOCK = "follow_up_confirmed"
CONTACTED_TEXT = "Customer contacted"
CONFIRMED_TEXT = "Customer confirmed"
OUTCOME_ACTION_IDS: frozenset[str] = frozenset({CONTACTED_BLOCK, CONFIRMED_BLOCK})


def _text(text: str) -> dict[str, Any]:
    return {"type": "plain_text", "text": text[:2000]}


def _content_blocks(message: str) -> list[dict[str, Any]]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": message[i : i + 3000]}}
        for i in range(0, len(message), 3000)
    ] or [{"type": "section", "text": {"type": "mrkdwn", "text": ""}}]


def follow_up_message_blocks(*, message: str, follow_up_id: str) -> list[dict[str, Any]]:
    """The approved message plus the outcome buttons the recipient may press."""
    return [
        *_content_blocks(message),
        {
            "type": "actions",
            "block_id": "follow_up_outcomes",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": _text(CONTACTED_TEXT),
                    "action_id": CONTACTED_BLOCK,
                    "value": follow_up_id,
                },
                {
                    "type": "button",
                    "text": _text(CONFIRMED_TEXT),
                    "action_id": CONFIRMED_BLOCK,
                    "value": follow_up_id,
                },
            ],
        },
    ]


def outcome_message_blocks(
    *, message: str, outcome: str, actor: str, follow_up_id: str
) -> list[dict[str, Any]]:
    """Sent history in the DM, showing what was recorded on the follow-up and by whom."""
    blocks = [
        *_content_blocks(message),
        {
            "type": "section",
            "text": _text(f"Recorded {outcome} by {actor}."),
        },
    ]
    if outcome != "confirmed":
        blocks.append(
            {
                "type": "actions",
                "block_id": "follow_up_outcomes",
                "elements": [
                    {
                        "type": "button",
                        "text": _text(CONFIRMED_TEXT),
                        "action_id": CONFIRMED_BLOCK,
                        "value": follow_up_id,
                    }
                ],
            }
        )
    return blocks


def payload_json(payload: dict[str, Any]) -> str:
    """Serialise interactive payload blocks for Slack calls."""
    return json.dumps(payload)


def outcome_action_pairs(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract the (action_id, value) pairs for known outcome buttons."""
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return []
    pairs: list[tuple[str, str]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = action.get("action_id")
        value = action.get("value")
        if (
            isinstance(action_id, str)
            and action_id in OUTCOME_ACTION_IDS
            and isinstance(value, str)
        ):
            pairs.append((action_id, value))
    return pairs
