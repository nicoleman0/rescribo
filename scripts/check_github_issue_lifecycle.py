#!/usr/bin/env python3
import argparse
import itertools
import json
import queue
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse

import environ
import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
environ.Env.read_env(REPOSITORY_ROOT / ".env.github-feasibility", overwrite=False)

from integrations.github_app import (  # noqa: E402
    GitHubAppClient,
    InstallationProbe,
    IssueLinkError,
    OAuthStateStore,
    apply_issue_event,
    parse_installation_event,
    parse_issue_event,
    resolve_issue_link,
    verify_webhook_signature,
)
from integrations.github_app.client import GitHubAPIError  # noqa: E402
from integrations.github_app.webhooks import InvalidWebhookSignature  # noqa: E402
from live_check import (  # noqa: E402
    LoopbackOAuthServer,
    OAuthCallbackHandler,
    receiver_of,
    required_environment,
)

ACCESS_LOST_STATUSES = {404, 410}
WEBHOOK_PATH = "/webhooks"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class WebhookCallbackHandler(OAuthCallbackHandler):
    """Adds signature-verified webhook deliveries to the loopback receiver."""

    def do_POST(self) -> None:  # noqa: N802
        receiver = receiver_of(self, LoopbackReceiver)
        if urlparse(self.path).path != WEBHOOK_PATH:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        try:
            verify_webhook_signature(
                secret=receiver.webhook_secret,
                body=body,
                signature_header=self.headers.get("X-Hub-Signature-256"),
            )
        except InvalidWebhookSignature:
            self.send_error(401)
            return
        record = {
            "order": next(receiver.order),
            "delivery_id": self.headers.get("X-GitHub-Delivery"),
            "event": self.headers.get("X-GitHub-Event"),
            "received_at": utc_now(),
            "payload": json.loads(body),
        }
        receiver.delivery_log.append(record)
        receiver.deliveries.put(record)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, _format: str, *args: object) -> None:
        return


class LoopbackReceiver(LoopbackOAuthServer):
    """Receives the OAuth callback and smee-forwarded webhooks on one loopback port.

    Every webhook delivery is signature-verified on arrival. Verified deliveries
    are logged for ordering evidence and queued for phase waits. Raw payloads
    stay in memory and are never written to disk.
    """

    handler = WebhookCallbackHandler

    def __init__(self, redirect_uri: str, *, webhook_secret: bytes) -> None:
        self.webhook_secret = webhook_secret
        self.deliveries: queue.Queue[dict[str, Any]] = queue.Queue()
        self.delivery_log: list[dict[str, Any]] = []
        self.order = itertools.count(1)
        super().__init__(redirect_uri)

    def start(self) -> None:
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.shutdown()
        self.server_close()
        self._thread.join(timeout=5)

    def wait_delivery(self, *, event: str, actions: set[str], timeout: int = 120) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SystemExit(
                    f"No verified {event} delivery for {sorted(actions)} arrived within "
                    f"{timeout} seconds. Check the smee relay and app webhook settings."
                )
            try:
                record = self.deliveries.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if record["event"] != event:
                continue
            if record["payload"].get("action") in actions:
                return record


def issue_access_state(
    client: GitHubAppClient, *, installation_token: str, repository: str, number: int
) -> str:
    owner, _, name = repository.partition("/")
    try:
        client.get_issue(
            installation_token=installation_token, owner=owner, name=name, number=number
        )
    except GitHubAPIError as error:
        if error.status_code in ACCESS_LOST_STATUSES:
            return "access_lost"
        raise
    return "ok"


def expect_link_rejection(
    client: GitHubAppClient, *, installation_token: str, repository: str, reference: str
) -> str:
    try:
        resolve_issue_link(
            client,
            installation_token=installation_token,
            expected_repository=repository,
            reference=reference,
        )
    except IssueLinkError:
        return "rejected"
    raise SystemExit(f"Expected {reference} to be rejected, but it linked successfully.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the opt-in GitHub issue lifecycle check.")
    parser.add_argument("--workspace", required=True, help="Synthetic workspace identifier")
    parser.add_argument("--repository", required=True, help="Disposable owner/name")
    parser.add_argument(
        "--anchor-repository",
        required=True,
        help="Second disposable owner/name kept installed during repository removal",
    )
    parser.add_argument("--smee-url", required=True, help="Disposable smee.io channel URL")
    parser.add_argument(
        "--pull-request-url",
        help="URL of a pull request in the disposable repository (rejection check)",
    )
    parser.add_argument(
        "--other-issue-url", help="URL of an issue in another repository (rejection check)"
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> None:
    if args.anchor_repository == args.repository:
        raise SystemExit("The anchor repository must differ from the lifecycle repository.")
    webhook_secret = required_environment("RESCRIBO_GITHUB_WEBHOOK_SECRET").encode()
    receiver = LoopbackReceiver(
        required_environment("RESCRIBO_GITHUB_REDIRECT_URI"), webhook_secret=webhook_secret
    )
    store = OAuthStateStore(REPOSITORY_ROOT / ".cache" / "github-installation-state")
    evidence: dict[str, Any] = {
        "check": "github-issue-lifecycle",
        "repository": args.repository,
        "started_at": utc_now(),
        "phases": {},
    }
    receiver.start()
    try:
        with httpx.Client(base_url="https://api.github.com", timeout=15) as http:
            client = GitHubAppClient(
                http,
                app_id=required_environment("RESCRIBO_GITHUB_APP_ID"),
                private_key=Path(
                    required_environment("RESCRIBO_GITHUB_PRIVATE_KEY_PATH")
                ).read_bytes(),
            )

            # Phase 1: authorise and verify the installation (as in the installation check).
            client_id = required_environment("RESCRIBO_GITHUB_CLIENT_ID")
            redirect_uri = required_environment("RESCRIBO_GITHUB_REDIRECT_URI")
            state = store.create(args.workspace, args.repository)
            query = urlencode(
                {"client_id": client_id, "redirect_uri": redirect_uri, "state": state}
            )
            authorisation_url = f"https://github.com/login/oauth/authorize?{query}"
            print(f"Open this URL within three minutes:\n{authorisation_url}")
            callback = receiver.wait_callback()
            repository = store.consume(callback["state"], args.workspace)
            if repository != args.repository:
                raise SystemExit("The OAuth state was bound to a different repository.")
            user_token = client.exchange_user_code(
                client_id=client_id,
                client_secret=required_environment("RESCRIBO_GITHUB_CLIENT_SECRET"),
                code=callback["code"],
                redirect_uri=redirect_uri,
            )
            probe = InstallationProbe(client).run(
                user_token=user_token,
                expected_repository=repository,
                additional_repositories={args.anchor_repository},
            )
            evidence["phases"]["installation"] = probe.as_dict()
            if probe.connection_status != "active" or probe.installation_id is None:
                raise SystemExit(f"Installation is not active: {probe.connection_status}.")
            owner, _, name = repository.partition("/")
            installation_token, token_expires_at = client.create_installation_token(
                installation_id=probe.installation_id, repository=name
            )
            evidence["phases"]["installation"]["token_expires_at"] = token_expires_at
            print(f"Installation active for {repository}.")

            # Phase 2: create and read an issue in the selected repository.
            title = f"Rescribo lifecycle check {utc_now()}"
            created = client.create_issue(
                installation_token=installation_token,
                owner=owner,
                name=name,
                title=title,
                body="Disposable issue created by the opt-in lifecycle feasibility check.",
            )
            number = created.get("number")
            if not isinstance(number, int):
                raise SystemExit("GitHub did not return the created issue number.")
            fetched = client.get_issue(
                installation_token=installation_token, owner=owner, name=name, number=number
            )
            evidence["phases"]["create_read"] = {
                "number": number,
                "state": fetched.get("state"),
                "state_reason": fetched.get("state_reason"),
                "title_round_trip": fetched.get("title") == title,
                "updated_at": fetched.get("updated_at"),
            }
            print(f"Created and read issue #{number}.")

            # Phase 3: link-existing resolution and rejections.
            linked = resolve_issue_link(
                client,
                installation_token=installation_token,
                expected_repository=repository,
                reference=f"https://github.com/{repository}/issues/{number}",
            )
            link_evidence: dict[str, Any] = {"self_link": linked.as_dict()}
            if args.pull_request_url:
                link_evidence["pull_request"] = expect_link_rejection(
                    client,
                    installation_token=installation_token,
                    repository=repository,
                    reference=args.pull_request_url,
                )
            else:
                link_evidence["pull_request"] = "not run live; covered by mocked tests"
            if args.other_issue_url:
                link_evidence["other_repository"] = expect_link_rejection(
                    client,
                    installation_token=installation_token,
                    repository=repository,
                    reference=args.other_issue_url,
                )
            else:
                link_evidence["other_repository"] = "not run live; covered by mocked tests"
            evidence["phases"]["link_existing"] = link_evidence
            print("Link-existing resolution verified.")

            # Phase 4: signed close and reopen events, applied from fetched state.
            print(
                "Start the webhook relay in another terminal:\n"
                f"  npx --yes smee --url {args.smee_url} "
                f"--target http://127.0.0.1:{receiver.port}{WEBHOOK_PATH}"
            )
            input("Press Enter once the relay is forwarding...")

            client.update_issue_state(
                installation_token=installation_token,
                owner=owner,
                name=name,
                number=number,
                state="closed",
            )
            closed_record = receiver.wait_delivery(event="issues", actions={"closed"})
            closed_event = parse_issue_event(closed_record["payload"])
            if closed_event is None:
                raise SystemExit("The closed delivery did not parse as an issues event.")
            closed_outcome = apply_issue_event(
                client,
                installation_token=installation_token,
                expected_repository=repository,
                event=closed_event,
                stored_updated_at=str(fetched["updated_at"]),
            )

            client.update_issue_state(
                installation_token=installation_token,
                owner=owner,
                name=name,
                number=number,
                state="open",
            )
            reopened_record = receiver.wait_delivery(event="issues", actions={"reopened"})
            reopened_event = parse_issue_event(reopened_record["payload"])
            if reopened_event is None:
                raise SystemExit("The reopened delivery did not parse as an issues event.")
            reopened_outcome = apply_issue_event(
                client,
                installation_token=installation_token,
                expected_repository=repository,
                event=reopened_event,
                stored_updated_at=closed_outcome.updated_at,
            )
            evidence["phases"]["webhooks"] = {
                "closed": {
                    "event": closed_event.as_dict(),
                    "outcome": closed_outcome.as_dict(),
                },
                "reopened": {
                    "event": reopened_event.as_dict(),
                    "outcome": reopened_outcome.as_dict(),
                },
            }
            if not (closed_outcome.applied and reopened_outcome.applied):
                raise SystemExit("Signed close/reopen events were not applied from fetched state.")
            print("Signed close and reopen events verified and applied from fetched state.")

            # Phase 5: repository removal produces access-lost state.
            print(
                f"Open https://github.com/settings/installations/{probe.installation_id} and "
                f"remove {repository} from the selected repositories. Keep "
                f"{args.anchor_repository} selected."
            )
            removal_record = receiver.wait_delivery(
                event="installation_repositories", actions={"removed"}, timeout=300
            )
            removal_event = parse_installation_event(
                "installation_repositories", removal_record["payload"]
            )
            access_after_removal = issue_access_state(
                client,
                installation_token=installation_token,
                repository=repository,
                number=number,
            )
            evidence["phases"]["repository_removal"] = {
                "event": removal_event.as_dict() if removal_event else None,
                "issue_access": access_after_removal,
            }
            if access_after_removal != "access_lost":
                raise SystemExit("The issue remained accessible after repository removal.")
            print("Repository removal produced access-lost state.")

            # Phase 6: installation revocation produces access-lost state.
            client.delete_installation(installation_id=probe.installation_id)
            deletion_record = receiver.wait_delivery(event="installation", actions={"deleted"})
            deletion_event = parse_installation_event("installation", deletion_record["payload"])
            try:
                client.create_installation_token(
                    installation_id=probe.installation_id, repository=name
                )
            except GitHubAPIError as error:
                if error.status_code not in ACCESS_LOST_STATUSES:
                    raise
                token_access = "access_lost"
            else:
                raise SystemExit("Token creation succeeded after installation deletion.")
            evidence["phases"]["installation_revocation"] = {
                "event": deletion_event.as_dict() if deletion_event else None,
                "token_creation": token_access,
            }
            print("Installation revocation produced access-lost state.")
    finally:
        receiver.stop()

    evidence["finished_at"] = utc_now()
    evidence["deliveries"] = [
        {
            "order": record["order"],
            "delivery_id": record["delivery_id"],
            "event": record["event"],
            "action": record["payload"].get("action"),
            "received_at": record["received_at"],
        }
        for record in receiver.delivery_log
    ]
    output = json.dumps(evidence, indent=2, sort_keys=True)
    print(output)
    evidence_path = REPOSITORY_ROOT / ".cache" / "github-issue-lifecycle-result.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(f"{output}\n", encoding="utf-8")
    print(f"Sanitised result written to {evidence_path.relative_to(REPOSITORY_ROOT)}")


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
