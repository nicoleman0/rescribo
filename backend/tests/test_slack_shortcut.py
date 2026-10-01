import hashlib
import hmac
import json
import time
from datetime import date

import pytest
from slack_sdk.models.blocks import SectionBlock

from integrations.slack import (
    InvalidSlackSignature,
    MessageShortcut,
    ShortcutPayloadError,
    SubmissionErrors,
    build_capture_modal,
    parse_capture_submission,
    parse_message_shortcut,
    verify_slack_signature,
)
from integrations.slack.modals import SECTION_TEXT_LIMIT, TITLE_LIMIT

SECRET = "feasibility-signing-secret"
CONTEXT_ID = "ctx-0123456789abcdef"


def modal_for(shortcut: MessageShortcut) -> dict:
    return build_capture_modal(
        shortcut,
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
    )


def block_by_id(view: dict, block_id: str) -> dict:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def signed_headers(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode(), b"v0:" + str(timestamp).encode() + b":" + body, hashlib.sha256
    ).hexdigest()
    return {"timestamp": str(timestamp), "signature": f"v0={digest}"}


def make_shortcut(**overrides: object) -> MessageShortcut:
    values: dict = {
        "callback_id": "submit_customer_feedback",
        "team_id": "T0TEAM",
        "channel_id": "C0PUBLIC",
        "channel_name": "customer-feedback",
        "actor_id": "U0ACTOR",
        "author_id": "U0AUTHOR",
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
    verify_slack_signature(signing_secret=SECRET, body=body, **signed_headers(SECRET, body))


def test_wrong_secret_rejected() -> None:
    body = b"payload=1"
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(signing_secret=SECRET, body=body, **signed_headers("other", body))


def test_tampered_body_rejected() -> None:
    body = b"payload=1"
    headers = signed_headers(SECRET, body)
    with pytest.raises(InvalidSlackSignature):
        verify_slack_signature(signing_secret=SECRET, body=b"payload=2", **headers)


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


def test_first_link_modal_requests_the_product_code() -> None:
    view = build_capture_modal(
        make_shortcut(),
        workspace_name="Feasibility A",
        captured_on=date(2026, 9, 20),
        context_id=CONTEXT_ID,
        link_required=True,
    )
    code_input = block_by_id(view, "slack_link_code")
    assert code_input["label"]["text"] == "Product linking code"


def test_submission_reads_only_fields_and_the_opaque_context() -> None:
    submission = parse_capture_submission(submission_payload(CONTEXT_ID, team="T0OTHER"))
    assert submission.context_id == CONTEXT_ID
    assert submission.title == "Report title from fixture"
    assert not hasattr(submission, "team_id")


def test_submission_carries_link_code_separately_from_report_fields() -> None:
    payload = submission_payload(CONTEXT_ID)
    payload["view"]["state"]["values"]["slack_link_code"] = {
        "value": {"value": "link-code-fixture"}
    }
    submission = parse_capture_submission(payload)
    assert submission.link_code == "link-code-fixture"


def test_submission_rejects_blank_title() -> None:
    payload = submission_payload(CONTEXT_ID)
    payload["view"]["state"]["values"]["report_title"] = {"title": {"value": "   "}}
    with pytest.raises(SubmissionErrors) as error:
        parse_capture_submission(payload)
    assert "report_title" in error.value.errors


def test_parse_message_shortcut_accepts_a_message_without_text() -> None:
    payload = shortcut_payload()
    payload["message"] = {"ts": "1758400000.000100", "text": ""}
    assert parse_message_shortcut(payload).text == ""


def test_parse_message_shortcut_rejects_non_string_text() -> None:
    payload = shortcut_payload()
    payload["message"] = {"ts": "1758400000.000100", "text": ["not", "a", "string"]}
    with pytest.raises(ShortcutPayloadError):
        parse_message_shortcut(payload)


def test_modal_says_so_when_the_message_has_no_text() -> None:
    view = modal_for(make_shortcut(text=""))
    assert "no text" in view["blocks"][0]["text"]["text"]
    assert "initial_value" not in block_by_id(view, "report_title")["element"]


def test_modal_snapshot_stays_within_slack_section_limit() -> None:
    view = modal_for(make_shortcut(text="w" * 10_000))
    snapshot = view["blocks"][0]["text"]["text"]
    assert len(snapshot) <= SECTION_TEXT_LIMIT
    assert snapshot.endswith("The whole message is captured.]")


def test_modal_snapshot_is_verbatim_when_it_fits() -> None:
    text = "y" * (SECTION_TEXT_LIMIT - 100)
    snapshot = modal_for(make_shortcut(text=text))["blocks"][0]["text"]["text"]
    assert snapshot.split("\n", 1)[1] == text


def test_prefilled_title_keeps_whole_words_up_to_the_limit() -> None:
    text = f"{'a' * 40} {'b' * 39}"
    assert len(text) == TITLE_LIMIT
    view = modal_for(make_shortcut(text=text))
    assert block_by_id(view, "report_title")["element"]["initial_value"] == text


def test_prefilled_title_drops_the_word_that_would_overflow() -> None:
    text = f"{'a' * 40} {'b' * 40}"
    assert len(text) == TITLE_LIMIT + 1
    view = modal_for(make_shortcut(text=text))
    assert block_by_id(view, "report_title")["element"]["initial_value"] == "a" * 40


def test_prefilled_title_cuts_a_single_oversized_word() -> None:
    view = modal_for(make_shortcut(text="z" * 200))
    prefill = block_by_id(view, "report_title")["element"]["initial_value"]
    assert prefill == "z" * TITLE_LIMIT


def test_prefilled_title_never_exceeds_the_limit() -> None:
    for text in ["short", "a" * 79, "a" * 80, "a" * 81, "word " * 40, "  spaced   out  "]:
        view = modal_for(make_shortcut(text=text))
        prefill = block_by_id(view, "report_title")["element"].get("initial_value", "")
        assert len(prefill) <= TITLE_LIMIT


@pytest.mark.parametrize(
    "text",
    ["", "A short customer report.", "w" * 40_000, "z" * 5_000, "word " * 2_000],
)
def test_modal_sections_pass_the_slack_sdk_block_validator(text: str) -> None:
    """`SectionBlock` enforces Slack's own limits, so let it police the snapshot."""
    for shortcut in (make_shortcut(text=text), make_shortcut(text=text, thread_ts="1.0")):
        view = modal_for(shortcut)
        for block in view["blocks"]:
            if block["type"] == "section":
                SectionBlock(text=block["text"]["text"]).validate_json()
