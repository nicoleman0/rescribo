#!/usr/bin/env python3
import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import environ
import httpx

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))

environ.Env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)
environ.Env.read_env(REPOSITORY_ROOT / ".env.github-feasibility", overwrite=False)

from integrations.github_app import (  # noqa: E402
    GitHubAppClient,
    InstallationProbe,
    OAuthStateStore,
)


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} before running this check.")
    return value


def state_store() -> OAuthStateStore:
    return OAuthStateStore(REPOSITORY_ROOT / ".cache" / "github-installation-state")


def create_authorisation_url(workspace_id: str, repository: str) -> str:
    client_id = required_environment("RESCRIBO_GITHUB_CLIENT_ID")
    redirect_uri = required_environment("RESCRIBO_GITHUB_REDIRECT_URI")
    state = state_store().create(workspace_id, repository)
    query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "state": state})
    return f"https://github.com/login/oauth/authorize?{query}"


def start(workspace_id: str, repository: str) -> None:
    authorisation_url = create_authorisation_url(workspace_id, repository)
    print(f"Open this URL and authorise the test GitHub App:\n{authorisation_url}")
    print("Then run the complete command with the returned code and state.")


def complete(*, workspace: str, state: str, code: str) -> None:
    repository = state_store().consume(state, workspace)
    private_key_path = Path(required_environment("RESCRIBO_GITHUB_PRIVATE_KEY_PATH"))
    with httpx.Client(base_url="https://api.github.com", timeout=15) as http:
        client = GitHubAppClient(
            http,
            app_id=required_environment("RESCRIBO_GITHUB_APP_ID"),
            private_key=private_key_path.read_bytes(),
        )
        user_token = client.exchange_user_code(
            client_id=required_environment("RESCRIBO_GITHUB_CLIENT_ID"),
            client_secret=required_environment("RESCRIBO_GITHUB_CLIENT_SECRET"),
            code=code,
            redirect_uri=required_environment("RESCRIBO_GITHUB_REDIRECT_URI"),
        )
        result = InstallationProbe(client).run(
            user_token=user_token,
            expected_repository=repository,
        )
    output = json.dumps(result.as_dict(), indent=2, sort_keys=True)
    print(output)
    evidence_path = REPOSITORY_ROOT / ".cache" / "github-installation-result.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(f"{output}\n", encoding="utf-8")
    print(f"Sanitised result written to {evidence_path.relative_to(REPOSITORY_ROOT)}")


def run_with_callback(workspace: str, repository: str) -> None:
    redirect_uri = urlparse(required_environment("RESCRIBO_GITHUB_REDIRECT_URI"))
    if redirect_uri.scheme != "http" or redirect_uri.hostname not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The live callback listener requires an HTTP loopback redirect URI.")
    if redirect_uri.port is None:
        raise SystemExit("The loopback redirect URI must include a port.")

    callback: dict[str, str] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request_uri = urlparse(self.path)
            if request_uri.path != redirect_uri.path:
                self.send_error(404)
                return
            values = parse_qs(request_uri.query)
            code = values.get("code", [""])[0]
            state = values.get("state", [""])[0]
            if not code or not state:
                self.send_error(400)
                return
            callback.update(code=code, state=state)
            message = b"GitHub authorization received. You can close this tab."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = HTTPServer((redirect_uri.hostname, redirect_uri.port), CallbackHandler)
    server.timeout = 180
    print(f"Open this URL within three minutes:\n{create_authorisation_url(workspace, repository)}")
    server.handle_request()
    server.server_close()
    if not callback:
        raise SystemExit("No GitHub callback was received within three minutes.")
    complete(workspace=workspace, state=callback["state"], code=callback["code"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the opt-in GitHub App installation check.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("--workspace", required=True, help="Synthetic workspace identifier")
    start_parser.add_argument("--repository", required=True, help="Expected owner/name")
    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument(
        "--workspace", required=True, help="Same synthetic workspace identifier"
    )
    complete_parser.add_argument("--state", required=True)
    complete_parser.add_argument("--code", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--workspace", required=True, help="Synthetic workspace identifier")
    run_parser.add_argument("--repository", required=True, help="Expected owner/name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "start":
        start(args.workspace, args.repository)
    elif args.command == "complete":
        complete(workspace=args.workspace, state=args.state, code=args.code)
    else:
        run_with_callback(args.workspace, args.repository)


if __name__ == "__main__":
    main()
