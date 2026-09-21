"""Evidence bookkeeping for the opt-in Slack shortcut capture check.

Kept out of the HTTP receiver so the coverage rules are testable without Slack.
Every accessor takes the lock: interaction requests are handled on server
threads while the run loop reads progress from the main thread.
"""

import threading
from typing import Any

from integrations.slack import MessageShortcut

REQUIRED_COVERAGE = frozenset(
    {("public", "root"), ("public", "thread"), ("private", "root"), ("private", "thread")}
)
REQUIRED_REJECTIONS = frozenset({"direct_message", "unapproved_channel"})

# Written when a capture is recorded, replaced once the HTTP 200 body is out.
ACK_PENDING = -1.0

_SANITISED_KEYS = frozenset(
    {
        "channel_id",
        "channel_kind",
        "source",
        "ack_ms",
        "views_open_ms",
        "skew_s",
        "snapshot_matches_selected_message",
        "thread_warning_shown",
        "submission_committed",
        "duplicate",
        "views_open_error",
        "error",
    }
)


class LedgerMismatch(RuntimeError):
    """A submission arrived that no open capture accounts for."""


class CaptureLedger:
    """Records what one check run has proved, and what is still outstanding."""

    def __init__(self, *, public_channel: str, private_channel: str) -> None:
        self.public_channel = public_channel
        self.private_channel = private_channel
        self._lock = threading.Lock()
        self._captures: list[dict[str, Any]] = []
        self._rejections: list[dict[str, Any]] = []
        self._retries: list[dict[str, Any]] = []

    def channel_kind(self, channel_id: str) -> str:
        if channel_id == self.public_channel:
            return "public"
        if channel_id == self.private_channel:
            return "private"
        return "unknown"

    def is_duplicate(self, source_key: str) -> bool:
        with self._lock:
            return any(capture["source_key"] == source_key for capture in self._captures)

    def record_capture(
        self,
        shortcut: MessageShortcut,
        *,
        views_open_ms: float | None,
        skew_s: float | None,
        duplicate: bool,
        views_open_error: str | None = None,
    ) -> None:
        capture: dict[str, Any] = {
            "source_key": shortcut.source_key(),
            "channel_id": shortcut.channel_id,
            "channel_kind": self.channel_kind(shortcut.channel_id),
            "source": "thread" if shortcut.is_thread_reply else "root",
            "ack_ms": ACK_PENDING,
            "views_open_ms": views_open_ms,
            "skew_s": skew_s,
            "snapshot_matches_selected_message": views_open_ms is not None,
            "thread_warning_shown": shortcut.is_thread_reply,
            "submission_committed": False,
            "duplicate": duplicate,
        }
        if views_open_error is not None:
            capture["views_open_error"] = views_open_error
        with self._lock:
            self._captures.append(capture)

    def record_expired_submission(self) -> None:
        with self._lock:
            self._captures.append(
                {
                    "source_key": "unknown",
                    "channel_id": "unknown",
                    "channel_kind": "unknown",
                    "source": "unknown",
                    "ack_ms": ACK_PENDING,
                    "views_open_ms": None,
                    "skew_s": None,
                    "snapshot_matches_selected_message": False,
                    "thread_warning_shown": False,
                    "submission_committed": False,
                    "error": "context_expired",
                    "duplicate": False,
                }
            )

    def record_ack(self, ack_ms: float) -> None:
        """Fill in the ack time on the newest capture still awaiting one."""
        with self._lock:
            for capture in reversed(self._captures):
                if capture["ack_ms"] == ACK_PENDING:
                    capture["ack_ms"] = ack_ms
                    return

    def record_rejection(
        self, *, reason: str, channel_id: str, channel_name: str | None = None
    ) -> None:
        entry: dict[str, Any] = {
            "reason": reason,
            "channel_id": channel_id,
            "text_retained": False,
        }
        if channel_name is not None:
            entry["channel_name"] = channel_name
        with self._lock:
            self._rejections.append(entry)

    def record_retry(
        self, interaction_kind: str, *, retry_num: str, retry_reason: str | None
    ) -> None:
        """Record one verified interaction Slack flagged as a retry."""
        with self._lock:
            self._retries.append(
                {
                    "interaction": interaction_kind,
                    "retry_num": retry_num,
                    "retry_reason": retry_reason,
                }
            )

    def retries(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(retry) for retry in self._retries]

    def mark_submission(
        self, shortcut: MessageShortcut, *, committed: bool, forced: bool = False
    ) -> None:
        """Attach a submission result to the newest open capture for that message."""
        source_key = shortcut.source_key()
        with self._lock:
            for capture in reversed(self._captures):
                if capture["source_key"] == source_key and not capture["submission_committed"]:
                    capture["submission_committed"] = committed
                    if forced:
                        capture["forced"] = True
                    return
        raise LedgerMismatch(
            f"No open capture for source {source_key}; the modal state and this "
            "submission do not line up."
        )

    def coverage_remaining(self) -> set[tuple[str, str]]:
        """Combinations still unproved.

        A combination counts only once the modal opened *and* its submission
        committed. A failed `views.open` or an abandoned modal proves nothing.
        """
        with self._lock:
            proved = {
                (capture["channel_kind"], capture["source"])
                for capture in self._captures
                if capture["channel_kind"] in {"public", "private"}
                and not capture["duplicate"]
                and capture["views_open_ms"] is not None
                and capture["submission_committed"]
            }
        return set(REQUIRED_COVERAGE) - proved

    def rejections_remaining(self) -> set[str]:
        with self._lock:
            seen = {rejection["reason"] for rejection in self._rejections}
        return set(REQUIRED_REJECTIONS) - seen

    def forced_error_recorded(self) -> bool:
        with self._lock:
            return any(capture.get("forced") for capture in self._captures)

    def complete(self, *, require_forced_error: bool) -> bool:
        if self.coverage_remaining() or self.rejections_remaining():
            return False
        return self.forced_error_recorded() if require_forced_error else True

    def outstanding(self, *, require_forced_error: bool) -> list[str]:
        """One line per thing the operator still has to do."""
        remaining = sorted(self.coverage_remaining())
        pending = [f"{kind} channel, {source} message" for kind, source in remaining]
        pending += [f"rejection: {reason}" for reason in sorted(self.rejections_remaining())]
        if require_forced_error and not self.forced_error_recorded():
            pending.append("one forced submission error")
        return pending

    def rejections(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(rejection) for rejection in self._rejections]

    def sanitised_captures(self) -> list[dict[str, Any]]:
        """Drop `source_key` and surface only keys cleared for the evidence file."""
        with self._lock:
            captures = [dict(capture) for capture in self._captures]
        clean: list[dict[str, Any]] = []
        for capture in captures:
            entry = {key: value for key, value in capture.items() if key in _SANITISED_KEYS}
            if capture.get("forced"):
                entry["forced_submission_error"] = True
            clean.append(entry)
        return clean
