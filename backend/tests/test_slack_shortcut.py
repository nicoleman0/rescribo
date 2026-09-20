import hashlib
import hmac
import json
import time
from datetime import date

import pytest

from integrations.slack import (
    InvalidSlackSignature,
    MessageShortcut,
    ShortcutPayloadError,
    SourceRejected,
    SubmissionErrors,
    build_capture_modal,
    check_source_allowed,
    parse_capture_submission,
    parse_message_shortcut,
    verify_slack_signature,
)

SECRET = "feasibility-signing-secret"
CONTEXT_ID = "ctx-0123456789abcdef"


def signed_headers(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode(), b"v0:" + str(timestamp).encode() + b":" + body, hashlib.sha256
    ).hexdigest()
    return {
        "X-Slack-Request-Timestamp": str(timestamp),
        "X-Slack-Signature": f"v0={digest}",
    }


def make_shortcut(**overrides: object) -> MessageShortcut:
    values: dict = {
        "callback_id": "submit_customer_feedback",
        "team_id": "T0TEAM",
        "channel_id": "C0PUBLIC",
        "channel_name": "customer-feedback",
        "actor_id": "U0ACTOR",
        "message_ts": "1758400000.000100",
        "thread_ts": None,
        "text": "Invented customer report text for fixture use only.",
        "trigger_id": "Tr0trigger",
    }
    values.update(overrides)
    return MessageShortcut(**values)


def shortcut_payload(**overrides: object) -> dict:
    payload = {
        "type": "message_action",
        "callback_id": "submit_customer_feedback",
        "trigger_id": "Tr0trigger",
        "team": {"id": "T0TEAM"},
        "user": {"id": "U0ACTOR"},
        "channel": {"id": "C0PUBLIC", "name": "customer-feedback"},
        "message": {
            "ts": "1758400000.000100",
            "text": "Invented customer report text for fixture use only.",
        },
    }
    for key, value in overrides.items():
        if value is None:
            payload.pop(key, None)
        else:
            payload[key] = value  # type: ignore[assignment]
    return payload


def submission_payload(context_id: str, team: str = "T0OTHER") -> dict:
    return {
        "type": "view_submission",
        "trigger_id": "Tr0new",
        "team": {"id": team},
        "user": {"id": "U0OTHER"},
        "view": {
            "private_metadata": context_id,
            "state": {
                "values": {
                    "report_title": {"title": {"value": "Report title from fixture"}},
                    "customer_reference": {"value": {"value": "Fixture customer"}},
                    "affected_version": {"value": {"value": "2.0.0"}},
                    "additional_context": {"value": {"value": "Fixture notes"}},
                }
            },
        },
    }


def test_valid_signature_accepted() -> None:
    body = b"payload=%7B%22x%22%3A1%7D"
    verify_slack_signature(signing_secret=SECRET, body=body, headers=signed_headers(SECRET, body))


def test_wrong_secret_rejected() -> None:
    body = b"payload=1"
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(
            signing_secret=SECRET, body=body, headers=signed_headers("other", body)
        )


def test_missing_signature_header_rejected() -> None:
    body = b"payload=1"
    headers = signed_headers(SECRET, body)
    del headers["X-Slack-Signature"]
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(signing_secret=SECRET, body=body, headers=headers)


def test_malformed_timestamp_rejected() -> None:
    body = b"payload=1"
    headers = signed_headers(SECRET, body)
    headers["X-Slack-Request-Timestamp"] = "not-a-number"
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(signing_secret=SECRET, body=body, headers=headers)


def test_stale_timestamp_rejected() -> None:
    body = b"payload=1"
    stale = int(time.time()) - 301
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(
            signing_secret=SECRET, body=body, headers=signed_headers(SECRET, body, stale)
        )


def test_parse_message_shortcut_extracts_identity() -> None:
    shortcut = parse_message_shortcut(shortcut_payload())
    assert shortcut.team_id == "T0TEAM"
    assert shortcut.channel_id == "C0PUBLIC"
    assert shortcut.actor_id == "U0ACTOR"
    assert shortcut.message_ts == "1758400000.000100"
    assert shortcut.trigger_id == "Tr0trigger"
    assert shortcut.callback_id == "submit_customer_feedback"
    assert shortcut.text == "Invented customer report text for fixture use only."


def test_parse_message_shortcut_rejects_wrong_type() -> None:
    payload = shortcut_payload()
    payload["type"] = "block_action"
    with pytest.raises(ShortcutPayloadError):
        parse_message_shortcut(payload)


@pytest.mark.parametrize("missing", ["trigger_id", "callback_id", "team", "channel", "message"])
def test_parse_message_shortcut_rejects_missing_fields(missing: str) -> None:
    payload = shortcut_payload()
    if missing == "message":
        payload["message"] = {"text": "Invented text without ts."}
    payload.pop(missing)
    with pytest.raises(ShortcutPayloadError):
        parse_message_shortcut(payload)


def test_parse_message_shortcut_rejects_message_without_ts() -> None:
    payload = shortcut_payload()
    payload["message"] = {"text": "Invented text without ts."}
    with pytest.raises(ShortcutPayloadError):
        parse_message_shortcut(payload)


def test_is_thread_reply() -> None:
    assert make_shortcut().is_thread_reply is False
    assert make_shortcut(thread_ts="1758400000.000100").is_thread_reply is False
    assert make_shortcut(thread_ts="1758400000.000050").is_thread_reply is True


def test_check_source_allowed_accepts_approved_channels() -> None:
    approved = frozenset({"C0PUBLIC", "C0PRIVATE"})
    check_source_allowed(make_shortcut(), approved_channel_ids=approved)
    reply = make_shortcut(
        channel_id="C0PRIVATE",
        channel_name="quiet",
        thread_ts="1758400000.000050",
    )
    check_source_allowed(reply, approved_channel_ids=approved)


def test_check_source_allowed_rejects_dm_channel() -> None:
    with pytest.raises(SourceRejected) as error:
        check_source_allowed(
            make_shortcut(channel_id="D0DM", channel_name=None),
            approved_channel_ids=frozenset({"C0PUBLIC"}),
        )
    assert "D0DM" in str(error.value)
    assert "direct_message" in str(error.value)
    assert "text" not in str(error.value)


def test_check_source_allowed_rejects_unapproved_channel() -> None:
    with pytest.raises(SourceRejected) as error:
        check_source_allowed(
            make_shortcut(channel_id="C0OTHER", channel_name="random"),
            approved_channel_ids=frozenset({"C0PUBLIC"}),
        )
    assert "C0OTHER" in str(error.value)
    assert "unapproved_channel" in str(error.value)
    assert "text" not in str(error.value)


def test_modal_snapshot_matches_text_exactly() -> None:
    shortcut = make_shortcut()
    view = build_capture_modal(
        shortcut,
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
    )
    snapshot_block = view["blocks"][0]
    assert (
        snapshot_block["text"]["text"].split("\n", 1)[1]
        == "Invented customer report text for fixture use only."
    )
    assert snapshot_block["text"]["type"] == "plain_text"


def test_modal_thread_warning_shown_only_for_replies() -> None:
    root = build_capture_modal(
        make_shortcut(),
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
    )
    assert "thread reply" not in json.dumps(root["blocks"])
    reply = build_capture_modal(
        make_shortcut(thread_ts="1758400000.000050"),
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
    )
    dumped = json.dumps(reply["blocks"])
    assert "thread reply" in dumped
    assert "parent conversation" in dumped


def test_modal_names_workspace_and_carries_opaque_context() -> None:
    view = build_capture_modal(
        make_shortcut(),
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
    )
    assert "Feasibility A" in json.dumps(view["blocks"])
    assert view["private_metadata"] == CONTEXT_ID


def test_submission_resolves_identity_from_context_not_payload() -> None:
    seen: list[str] = []

    def resolve_context(context_id: str) -> MessageShortcut:
        seen.append(context_id)
        return make_shortcut(team_id="T0TEAM", channel_id="C0PUBLIC")

    submission = parse_capture_submission(
        submission_payload(CONTEXT_ID, team="T0OTHER"), resolve_context=resolve_context
    )
    assert seen == [CONTEXT_ID]
    assert submission.title == "Report title from fixture"


def test_submission_records_context_identity() -> None:
    def resolve_context(context_id: str) -> MessageShortcut:
        return make_shortcut(team_id="T0TEAM", channel_id="C0PUBLIC")

    submission = parse_capture_submission(
        submission_payload(CONTEXT_ID, team="T0OTHER"), resolve_context=resolve_context
    )
    assert submission.shortcut.team_id == "T0TEAM"
    assert submission.title == "Report title from fixture"


def test_submission_rejects_unknown_context() -> None:
    def resolve_context(context_id: str) -> MessageShortcut:
        raise ValueError(f"Unknown context {context_id}")

    with pytest.raises(ValueError):
        parse_capture_submission(submission_payload("ctx-unknown"), resolve_context=resolve_context)


def test_submission_rejects_blank_title() -> None:
    def resolve_context(context_id: str) -> MessageShortcut:
        return make_shortcut()

    payload = submission_payload(CONTEXT_ID)
    payload["view"]["state"]["values"]["report_title"] = {"title": {"value": "   "}}
    with pytest.raises(SubmissionErrors) as error:
        parse_capture_submission(payload, resolve_context=resolve_context)
    assert "report_title" in error.value.errors
