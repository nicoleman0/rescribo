"""Capture modal building and submission parsing for the message shortcut flow."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from slack_sdk.models.blocks import SectionBlock

from integrations.slack.shortcuts import MessageShortcut

# Slack rejects a section whose plain_text runs past this. Read the limit off
# the SDK rather than restating Slack's number here.
SECTION_TEXT_LIMIT: int = SectionBlock.text_max_length
TITLE_LIMIT = 80
_TRUNCATION_NOTE = "\n[Preview truncated. The whole message is captured.]"
_NO_TEXT_NOTE = "(This message has no text.)"


class SubmissionErrors(ValueError):
    """Maps block ids to visible error messages for `response_action: errors`."""

    def __init__(self, errors: Mapping[str, str], *, context_id: str) -> None:
        super().__init__(f"Submission rejected for context {context_id}: {sorted(errors)}")
        self.errors = dict(errors)
        self.context_id = context_id


@dataclass(frozen=True)
class CaptureSubmission:
    context_id: str
    shortcut: MessageShortcut
    title: str
    customer_reference: str
    affected_version: str
    additional_context: str
    link_code: str

    def as_evidence(self) -> dict[str, Any]:
        return {
            "team_id": self.shortcut.team_id,
            "channel_id": self.shortcut.channel_id,
            "message_ts": self.shortcut.message_ts,
            "title_length": len(self.title),
            "customer_reference_given": bool(self.customer_reference),
            "affected_version_given": bool(self.affected_version),
            "additional_context_given": bool(self.additional_context),
            "link_code_given": bool(self.link_code),
        }


def _prefill_title(text: str) -> str:
    """The leading whole words of the message, within the title limit.

    A first word longer than the limit is cut mid-word: a blank prefill on a
    required field is worse than a clipped one.
    """
    words = text.split()
    if not words:
        return ""
    parts: list[str] = []
    length = 0
    for word in words:
        added = len(word) + (1 if parts else 0)
        if length + added > TITLE_LIMIT:
            break
        parts.append(word)
        length += added
    if not parts:
        return words[0][:TITLE_LIMIT]
    return " ".join(parts)


def _snapshot_text(text: str, captured_on: date) -> str:
    """The snapshot section, clipped to what Slack will accept in one section."""
    header = f"Captured on {captured_on.isoformat()}:\n"
    body = text if text.strip() else _NO_TEXT_NOTE
    budget = SECTION_TEXT_LIMIT - len(header)
    if len(body) > budget:
        body = body[: budget - len(_TRUNCATION_NOTE)] + _TRUNCATION_NOTE
    return header + body


def build_capture_modal(
    shortcut: MessageShortcut,
    *,
    workspace_name: str,
    captured_on: date,
    context_id: str,
    link_required: bool = False,
) -> dict[str, Any]:
    """Build the Block Kit capture modal from the shortcut snapshot.

    The message text is captured verbatim as a snapshot; the only Slack-facing
    identifier carried forward is the opaque `context_id` in `private_metadata`.
    """
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": _snapshot_text(shortcut.text, captured_on),
            },
        }
    ]
    if shortcut.is_thread_reply:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": (
                            "This is a thread reply captured without its parent conversation."
                        ),
                    }
                ],
            }
        )
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": f"This report will be visible to all members of {workspace_name}.",
            },
        },
    )
    if link_required:
        blocks.append(
            {
                "type": "input",
                "block_id": "slack_link_code",
                "label": {"type": "plain_text", "text": "Product linking code"},
                "element": {"type": "plain_text_input", "action_id": "value"},
            }
        )
    title_element: dict[str, Any] = {"type": "plain_text_input", "action_id": "title"}
    prefill = _prefill_title(shortcut.text)
    if prefill:
        title_element["initial_value"] = prefill
    blocks.append(
        {
            "type": "input",
            "block_id": "report_title",
            "label": {"type": "plain_text", "text": "Report title"},
            "element": title_element,
        },
    )
    blocks.append(
        {
            "type": "input",
            "optional": True,
            "block_id": "customer_reference",
            "label": {"type": "plain_text", "text": "Customer organisation / contact"},
            "element": {"type": "plain_text_input", "action_id": "value"},
        },
    )
    blocks.append(
        {
            "type": "input",
            "optional": True,
            "block_id": "affected_version",
            "label": {"type": "plain_text", "text": "Affected version"},
            "element": {"type": "plain_text_input", "action_id": "value"},
        },
    )
    blocks.append(
        {
            "type": "input",
            "optional": True,
            "block_id": "additional_context",
            "label": {"type": "plain_text", "text": "Additional context"},
            "element": {"type": "plain_text_input", "action_id": "value", "multiline": True},
        },
    )
    return {
        "type": "modal",
        "callback_id": shortcut.callback_id,
        "title": {"type": "plain_text", "text": "Submit customer feedback"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": context_id,
        "blocks": blocks,
    }


_BLOCK_ACTION_IDS = {
    "report_title": "title",
    "customer_reference": "value",
    "affected_version": "value",
    "additional_context": "value",
    "slack_link_code": "value",
}


def _input_value(state: Mapping[str, Any], block_id: str) -> str:
    block = state.get(block_id)
    if not isinstance(block, Mapping):
        return ""
    element = block.get(_BLOCK_ACTION_IDS[block_id])
    if isinstance(element, Mapping) and isinstance(element.get("value"), str):
        return element["value"]
    return ""


def parse_capture_submission(
    payload: Mapping[str, Any],
    *,
    resolve_context: Callable[[str], MessageShortcut],
) -> CaptureSubmission:
    """Parse a `view_submission` payload, resolving identity from the context.

    Team, channel and message identity come only from the shortcut returned by
    `resolve_context(private_metadata)`; values inside the submission payload
    are never used for identity. An unknown context raises `ValueError`.
    """
    view = payload.get("view")
    if not isinstance(view, Mapping):
        raise ValueError("Interaction payload has no view.")
    metadata = view.get("private_metadata")
    if not isinstance(metadata, str) or not metadata:
        raise ValueError("Submission carries no private metadata context.")
    shortcut = resolve_context(metadata)
    state = view.get("state")
    if not isinstance(state, Mapping):
        state = {}
    values = state.get("values")
    values = values if isinstance(values, Mapping) else {}
    errors: dict[str, str] = {}
    title = _input_value(values, "report_title")
    if not title.strip():
        errors["report_title"] = "A report title is required."
    if errors:
        raise SubmissionErrors(errors, context_id=metadata)
    return CaptureSubmission(
        context_id=metadata,
        shortcut=shortcut,
        title=title,
        customer_reference=_input_value(values, "customer_reference"),
        affected_version=_input_value(values, "affected_version"),
        additional_context=_input_value(values, "additional_context"),
        link_code=_input_value(values, "slack_link_code"),
    )
