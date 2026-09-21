#!/usr/bin/env python3
"""Opt-in live Slack message shortcut capture feasibility check.

Run manually with `task slack-shortcut-check`. Requires a disposable Slack
workspace, a test app with interactivity pointed at a public HTTPS tunnel to
this loopback receiver, and secrets in `.env.slack-feasibility`. Writes a
sanitised evidence file to `.cache/` that never contains message text, actor
ids, tokens, trigger ids or raw payloads.
"""

import argparse
import json
import secrets
import sys
import threading
import time
from datetime import UTC, date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import environ

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
environ.Env.read_env(REPOSITORY_ROOT / ".env.slack-feasibility", overwrite=False)

from slack_sdk import WebClient  # noqa: E402
from slack_sdk.errors import SlackApiError  # noqa: E402

from integrations.slack import (  # noqa: E402
    ChannelRejected,
    InvalidSlackSignature,
    MessageShortcut,
    ShortcutPayloadError,
    SubmissionErrors,
    build_capture_modal,
    check_source_allowed,
    parse_capture_submission,
    parse_message_shortcut,
    slack_error_code,
    verify_slack_signature,
)
from live_check import receiver_of, required_environment  # noqa: E402
from slack_capture_ledger import CaptureLedger  # noqa: E402
from slack_live import check_granted_scopes  # noqa: E402

INTERACTIONS_PATH = "/slack/interactions"
CONTEXT_TTL_S = 15 * 60


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the opt-in Slack shortcut capture check.")
    parser.add_argument("--workspace", required=True, help="Synthetic workspace identifier")
    parser.add_argument(
        "--workspace-name", required=True, help="Workspace name used in the modal consent line"
    )
    parser.add_argument("--public-channel", required=True, help="Approved public channel id")
    parser.add_argument("--private-channel", required=True, help="Approved private channel id")
    parser.add_argument(
        "--fail-first-submission",
        action="store_true",
        help="Force one visible submission error instead of a success acknowledgement",
    )
    return parser.parse_args()


class SlackReceiver(ThreadingHTTPServer):
    """Receives Slack interactivity requests on a loopback port.

    Interaction requests are signature-verified against the raw body on the
    HTTP thread, then handled inline so the acknowledgement deadline applies to
    the actual work. Threading matters: a slow `views.open` for one
    interaction must not hold another interaction's acknowledgement past
    Slack's three-second deadline.
    """

    def __init__(
        self,
        listening_url: str,
        *,
        client: WebClient,
        signing_secret: str,
        workspace_name: str,
        public_channel: str,
        private_channel: str,
        fail_first_submission: bool,
    ) -> None:
        parsed = urlparse(listening_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise SystemExit("The Slack receiver requires a loopback HTTP listening URL.")
        if parsed.port is None:
            raise SystemExit("The loopback listening URL must include a port.")
        self.signing_secret = signing_secret
        self.workspace_name = workspace_name
        self.public_channel = public_channel
        self.private_channel = private_channel
        self.fail_first_submission = fail_first_submission
        self.approved_channel_ids = frozenset({public_channel, private_channel})
        self.client = client
        self.ledger = CaptureLedger(public_channel=public_channel, private_channel=private_channel)
        self.contexts: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        super().__init__((parsed.hostname, parsed.port), SlackInteractionHandler)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

    def handle_interaction(
        self,
        *,
        body: str,
        request_timestamp: str | None,
        retry_num: str | None = None,
        retry_reason: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Parse one verified interaction and answer with a response action.

        Returns `(status, payload)`. The handler times the acknowledgement and
        writes it back onto the capture record once the body is out.
        """
        try:
            request_ts = float(request_timestamp) if request_timestamp else None
        except ValueError:
            request_ts = None
        skew_s = time.time() - request_ts if request_ts is not None else None
        payload = json.loads(parse_qs(body).get("payload", ["{}"])[0])
        kind = payload.get("type")
        if retry_num is not None:
            self.ledger.record_retry(str(kind), retry_num=retry_num, retry_reason=retry_reason)
        if kind == "message_action":
            return self.handle_message_action(payload, skew_s=skew_s)
        if kind == "view_submission":
            return self.handle_view_submission(payload)
        print(f"Ignored interaction of type {kind!r}.")
        return 200, {}

    def prune_contexts(self) -> None:
        with self._lock:
            self.contexts = {
                key: value
                for key, value in self.contexts.items()
                if value["expires_at"] > time.monotonic()
            }

    def handle_message_action(
        self, payload: dict[str, Any], *, skew_s: float | None
    ) -> tuple[int, dict[str, Any]]:
        self.prune_contexts()
        try:
            shortcut = parse_message_shortcut(payload)
        except ShortcutPayloadError as error:
            print(f"Malformed message_action payload: {error}")
            return 200, {}
        try:
            check_source_allowed(shortcut, approved_channel_ids=self.approved_channel_ids)
        except ChannelRejected as reject:
            self.ledger.record_rejection(
                reason=reject.reason,
                channel_id=reject.channel_id,
                channel_name=shortcut.channel_name,
            )
            print(f"Rejected source {reject.channel_id} ({reject.reason}); text not retained.")
            return 200, {}
        duplicate = self.ledger.is_duplicate(shortcut.source_key())
        context_id = f"ctx-{secrets.token_hex(8)}"
        with self._lock:
            self.contexts[context_id] = {
                "shortcut": shortcut,
                "expires_at": time.monotonic() + CONTEXT_TTL_S,
            }
        view = build_capture_modal(
            shortcut,
            workspace_name=self.workspace_name,
            captured_on=date.today(),
            context_id=context_id,
        )
        views_open_start = time.monotonic()
        try:
            self.client.views_open(trigger_id=shortcut.trigger_id, view=view)
        except SlackApiError as error:
            slack_error = slack_error_code(error)
            print(f"views.open failed ({slack_error}); the capture is failed and not covered.")
            self.ledger.record_capture(
                shortcut,
                views_open_ms=None,
                skew_s=skew_s,
                duplicate=duplicate,
                views_open_error=slack_error,
            )
            with self._lock:
                self.contexts.pop(context_id, None)
            return 200, {}
        views_open_ms = (time.monotonic() - views_open_start) * 1000
        source = "thread" if shortcut.is_thread_reply else "root"
        self.ledger.record_capture(
            shortcut,
            views_open_ms=views_open_ms,
            skew_s=skew_s,
            duplicate=duplicate,
        )
        print(
            f"Modal opened for {shortcut.channel_id} ({source}) views_open_ms={views_open_ms:.0f} "
            f"skew_s={skew_s}. Now submit or cancel inside the modal."
        )
        return 200, {}

    def handle_view_submission(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        view = payload.get("view")
        context_id = view.get("private_metadata") if isinstance(view, dict) else None
        stored = None
        if isinstance(context_id, str):
            with self._lock:
                stored = self.contexts.get(context_id)
        if stored is None or not isinstance(context_id, str):
            print("Submission arrived with unknown or expired context; rejecting visibly.")
            self.ledger.record_expired_submission()
            return 200, {
                "response_action": "errors",
                "errors": {"report_title": "Context expired. Retake the shortcut."},
            }
        shortcut: MessageShortcut = stored["shortcut"]
        if self.fail_first_submission and not self.ledger.forced_error_recorded():
            self.ledger.mark_submission(shortcut, committed=False, forced=True)
            return 200, {
                "response_action": "errors",
                "errors": {"report_title": "Forced visible error to prove the failure path."},
            }
        try:
            parse_capture_submission(payload, resolve_context=lambda _cid: shortcut)
        except SubmissionErrors as error:
            self.ledger.mark_submission(shortcut, committed=False)
            return 200, {"response_action": "errors", "errors": error.errors}
        except ValueError:
            self.ledger.mark_submission(shortcut, committed=False)
            return 200, {
                "response_action": "errors",
                "errors": {"report_title": "Could not parse this submission."},
            }
        self.ledger.mark_submission(shortcut, committed=True)
        with self._lock:
            self.contexts.pop(context_id, None)
        print(f"Submission committed for {shortcut.channel_id}.")
        return 200, {"response_action": "clear"}


class SlackInteractionHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        receiver = receiver_of(self, SlackReceiver)
        if urlparse(self.path).path != INTERACTIONS_PATH:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        received = time.monotonic()
        try:
            verify_slack_signature(
                signing_secret=receiver.signing_secret,
                body=body,
                timestamp=self.headers.get("X-Slack-Request-Timestamp"),
                signature=self.headers.get("X-Slack-Signature"),
            )
        except InvalidSlackSignature:
            print("Rejected a missing or badly signed interaction request (401).")
            self.send_error(401)
            return
        try:
            status, response = receiver.handle_interaction(
                body=body.decode("utf-8"),
                request_timestamp=self.headers.get("X-Slack-Request-Timestamp"),
                retry_num=self.headers.get("X-Slack-Retry-Num"),
                retry_reason=self.headers.get("X-Slack-Retry-Reason"),
            )
        except Exception:
            self.send_error(500)
            raise
        encoded = json.dumps(response).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        receiver.ledger.record_ack((time.monotonic() - received) * 1000)

    def log_message(self, _format: str, *args: object) -> None:
        return


def print_checklist(args: argparse.Namespace) -> None:
    print("Do this first, in another terminal, so the Request URL matches:")
    print(f"  cloudflared tunnel --url http://127.0.0.1:{args.receiver_port}")
    print("Then update the app's Interactivity Request URL to the printed trycloudflare URL.")
    print("Run these six interactions in the Slack workspace:")
    print("  1. Shortcut on a root message in the approved public channel.")
    print("  2. Shortcut on a thread reply in the approved public channel.")
    print("  3. Shortcut on a root message in the approved private channel.")
    print("  4. Shortcut on a thread reply in the approved private channel.")
    print("  5. Shortcut on a message in a DM channel (must be rejected).")
    print("  6. Shortcut on a message in an unapproved channel (must be rejected).")
    print("Submit the modal once per capture; press Ctrl-C here when done.")


def run(args: argparse.Namespace) -> None:
    signing_secret = required_environment("RESCRIBO_SLACK_SIGNING_SECRET")
    listening_url = required_environment("RESCRIBO_SLACK_RECEIVER_URL")
    client = WebClient(token=required_environment("RESCRIBO_SLACK_BOT_TOKEN"))

    evidence: dict[str, Any] = {
        "check": "slack-shortcut-capture",
        "workspace": args.workspace,
        "started_at": utc_now(),
    }
    evidence.update(check_granted_scopes(client))
    receiver = SlackReceiver(
        listening_url,
        client=client,
        signing_secret=signing_secret,
        workspace_name=args.workspace_name,
        public_channel=args.public_channel,
        private_channel=args.private_channel,
        fail_first_submission=args.fail_first_submission,
    )
    args.receiver_port = receiver.server_port
    receiver.start()
    print(f"Receiver on http://127.0.0.1:{receiver.server_port}{INTERACTIONS_PATH}")
    print_checklist(args)
    ledger = receiver.ledger
    announced: list[str] = []
    try:
        while not ledger.complete(require_forced_error=args.fail_first_submission):
            time.sleep(1)
            outstanding = ledger.outstanding(require_forced_error=args.fail_first_submission)
            if outstanding != announced:
                print("Still outstanding: " + "; ".join(outstanding))
                announced = outstanding
    except KeyboardInterrupt:
        print("Interrupted; writing what was recorded so far.")
    finally:
        receiver.stop()

    evidence["rejections"] = ledger.rejections()
    evidence["captures"] = ledger.sanitised_captures()
    evidence["observed_retries"] = ledger.retries()
    evidence["coverage_complete"] = ledger.complete(require_forced_error=args.fail_first_submission)
    evidence["finished_at"] = utc_now()
    output = json.dumps(evidence, indent=2, sort_keys=True)
    print(output)
    evidence_path = REPOSITORY_ROOT / ".cache" / "slack-shortcut-result.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(f"{output}\n", encoding="utf-8")
    print(f"Sanitised result written to {evidence_path.relative_to(REPOSITORY_ROOT)}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
