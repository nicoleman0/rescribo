import pytest

from integrations.slack import MessageShortcut
from slack_capture_ledger import ACK_PENDING, CaptureLedger, LedgerMismatch

PUBLIC = "C0PUBLIC"
PRIVATE = "C0PRIVATE"


def make_shortcut(
    *, channel_id: str = PUBLIC, message_ts: str = "1758400000.000100", thread: bool = False
) -> MessageShortcut:
    return MessageShortcut(
        callback_id="submit_customer_feedback",
        team_id="T0TEAM",
        channel_id=channel_id,
        channel_name="fixture",
        actor_id="U0ACTOR",
        message_ts=message_ts,
        thread_ts="1758399000.000100" if thread else None,
        text="Invented customer report text for fixture use only.",
        trigger_id="Tr0trigger",
    )


def make_ledger() -> CaptureLedger:
    return CaptureLedger(public_channel=PUBLIC, private_channel=PRIVATE)


def capture_and_commit(
    ledger: CaptureLedger, *, channel_id: str, message_ts: str, thread: bool
) -> MessageShortcut:
    shortcut = make_shortcut(channel_id=channel_id, message_ts=message_ts, thread=thread)
    ledger.record_capture(shortcut, views_open_ms=40.0, skew_s=0.1, duplicate=False)
    ledger.mark_submission(shortcut, committed=True)
    return shortcut


def complete_coverage(ledger: CaptureLedger) -> None:
    for index, (channel_id, thread) in enumerate(
        [(PUBLIC, False), (PUBLIC, True), (PRIVATE, False), (PRIVATE, True)]
    ):
        capture_and_commit(
            ledger, channel_id=channel_id, message_ts=f"175840000{index}.000100", thread=thread
        )
    ledger.record_rejection(reason="direct_message", channel_id="D0DM")
    ledger.record_rejection(reason="unapproved_channel", channel_id="C0OTHER")


def test_channel_kind_labels_only_the_declared_channels() -> None:
    ledger = make_ledger()
    assert ledger.channel_kind(PUBLIC) == "public"
    assert ledger.channel_kind(PRIVATE) == "private"
    assert ledger.channel_kind("C0OTHER") == "unknown"


def test_fresh_ledger_is_not_complete() -> None:
    ledger = make_ledger()
    assert len(ledger.coverage_remaining()) == 4
    assert ledger.rejections_remaining() == {"direct_message", "unapproved_channel"}
    assert ledger.complete(require_forced_error=False) is False


def test_complete_requires_every_combination_and_both_rejections() -> None:
    ledger = make_ledger()
    complete_coverage(ledger)
    assert ledger.coverage_remaining() == set()
    assert ledger.rejections_remaining() == set()
    assert ledger.complete(require_forced_error=False) is True


def test_open_modal_alone_does_not_prove_a_combination() -> None:
    ledger = make_ledger()
    ledger.record_capture(make_shortcut(), views_open_ms=40.0, skew_s=None, duplicate=False)
    assert ("public", "root") in ledger.coverage_remaining()


def test_failed_views_open_does_not_prove_a_combination() -> None:
    ledger = make_ledger()
    shortcut = make_shortcut()
    ledger.record_capture(
        shortcut,
        views_open_ms=None,
        skew_s=None,
        duplicate=False,
        views_open_error="invalid_blocks",
    )
    ledger.mark_submission(shortcut, committed=True)
    assert ("public", "root") in ledger.coverage_remaining()


def test_duplicate_capture_does_not_prove_a_combination() -> None:
    ledger = make_ledger()
    capture_and_commit(ledger, channel_id=PUBLIC, message_ts="1758400000.000100", thread=False)
    shortcut = make_shortcut()
    assert ledger.is_duplicate(shortcut.source_key()) is True
    ledger.record_capture(shortcut, views_open_ms=40.0, skew_s=None, duplicate=True)
    ledger.mark_submission(shortcut, committed=True)
    assert ledger.coverage_remaining() == {
        ("public", "thread"),
        ("private", "root"),
        ("private", "thread"),
    }


def test_one_rejection_is_not_both() -> None:
    ledger = make_ledger()
    complete_coverage(ledger)
    ledger = make_ledger()
    for index, (channel_id, thread) in enumerate(
        [(PUBLIC, False), (PUBLIC, True), (PRIVATE, False), (PRIVATE, True)]
    ):
        capture_and_commit(
            ledger, channel_id=channel_id, message_ts=f"175840000{index}.000100", thread=thread
        )
    ledger.record_rejection(reason="direct_message", channel_id="D0DM")
    assert ledger.rejections_remaining() == {"unapproved_channel"}
    assert ledger.complete(require_forced_error=False) is False


def test_forced_error_gates_completion_only_when_requested() -> None:
    ledger = make_ledger()
    complete_coverage(ledger)
    assert ledger.complete(require_forced_error=False) is True
    assert ledger.complete(require_forced_error=True) is False


def test_forced_error_then_retry_still_completes() -> None:
    ledger = make_ledger()
    shortcut = make_shortcut()
    ledger.record_capture(shortcut, views_open_ms=40.0, skew_s=None, duplicate=False)
    ledger.mark_submission(shortcut, committed=False, forced=True)
    assert ledger.forced_error_recorded() is True
    assert ("public", "root") in ledger.coverage_remaining()
    ledger.mark_submission(shortcut, committed=True)
    assert ("public", "root") not in ledger.coverage_remaining()
    assert ledger.forced_error_recorded() is True


def test_mark_submission_without_an_open_capture_raises() -> None:
    ledger = make_ledger()
    with pytest.raises(LedgerMismatch):
        ledger.mark_submission(make_shortcut(), committed=True)


def test_mark_submission_error_is_not_a_system_exit() -> None:
    """A receiver thread must surface this as a 500, not die silently."""
    ledger = make_ledger()
    with pytest.raises(Exception) as error:
        ledger.mark_submission(make_shortcut(), committed=True)
    assert not isinstance(error.value, SystemExit)


def test_record_ack_fills_the_newest_pending_capture() -> None:
    ledger = make_ledger()
    first = make_shortcut(message_ts="1758400000.000100")
    ledger.record_capture(first, views_open_ms=40.0, skew_s=None, duplicate=False)
    ledger.record_ack(12.5)
    second = make_shortcut(message_ts="1758400000.000200")
    ledger.record_capture(second, views_open_ms=40.0, skew_s=None, duplicate=False)
    ledger.record_ack(34.0)
    assert [capture["ack_ms"] for capture in ledger.sanitised_captures()] == [12.5, 34.0]


def test_record_ack_without_a_pending_capture_is_a_no_op() -> None:
    make_ledger().record_ack(9.0)


def test_expired_submission_keeps_its_reason_in_the_evidence() -> None:
    ledger = make_ledger()
    ledger.record_expired_submission()
    entry = ledger.sanitised_captures()[0]
    assert entry["error"] == "context_expired"
    assert entry["submission_committed"] is False


def test_sanitised_captures_drop_the_source_key() -> None:
    ledger = make_ledger()
    shortcut = make_shortcut()
    ledger.record_capture(shortcut, views_open_ms=40.0, skew_s=None, duplicate=False)
    ledger.mark_submission(shortcut, committed=False, forced=True)
    entry = ledger.sanitised_captures()[0]
    assert "source_key" not in entry
    assert shortcut.message_ts not in str(entry)
    assert entry["forced_submission_error"] is True


def test_sanitised_captures_never_carry_message_text_or_actor() -> None:
    ledger = make_ledger()
    shortcut = make_shortcut()
    ledger.record_capture(shortcut, views_open_ms=40.0, skew_s=None, duplicate=False)
    dumped = str(ledger.sanitised_captures())
    assert shortcut.text not in dumped
    assert shortcut.actor_id not in dumped
    assert shortcut.trigger_id not in dumped
    assert shortcut.team_id not in dumped


def test_rejections_record_that_text_was_not_retained() -> None:
    ledger = make_ledger()
    ledger.record_rejection(reason="direct_message", channel_id="D0DM")
    assert ledger.rejections() == [
        {"reason": "direct_message", "channel_id": "D0DM", "text_retained": False}
    ]


def test_outstanding_lists_what_the_operator_still_has_to_do() -> None:
    ledger = make_ledger()
    outstanding = ledger.outstanding(require_forced_error=True)
    assert "rejection: direct_message" in outstanding
    assert "rejection: unapproved_channel" in outstanding
    assert "one forced submission error" in outstanding
    assert sorted(line for line in outstanding if " channel, " in line) == [
        "private channel, root message",
        "private channel, thread message",
        "public channel, root message",
        "public channel, thread message",
    ]
    complete_coverage(ledger)
    assert ledger.outstanding(require_forced_error=False) == []


def test_ack_pending_sentinel_never_reaches_the_evidence_file() -> None:
    ledger = make_ledger()
    ledger.record_capture(make_shortcut(), views_open_ms=40.0, skew_s=None, duplicate=False)
    ledger.record_ack(11.0)
    assert all(capture["ack_ms"] != ACK_PENDING for capture in ledger.sanitised_captures())
