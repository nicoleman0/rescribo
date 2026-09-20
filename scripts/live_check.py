"""Shared loopback helpers for the opt-in live feasibility check scripts."""

import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} before running this check.")
    return value


def receiver_of[ReceiverT: HTTPServer](
    handler: BaseHTTPRequestHandler, expected: type[ReceiverT]
) -> ReceiverT:
    """Narrow `handler.server` to the receiver that owns the handler."""
    server = handler.server
    assert isinstance(server, expected), f"Handler is not bound to a {expected.__name__}."
    return server


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Records the OAuth callback onto `self.server.callback`."""

    def do_GET(self) -> None:  # noqa: N802
        receiver = receiver_of(self, LoopbackOAuthServer)
        request_uri = urlparse(self.path)
        if request_uri.path != receiver.redirect_path:
            self.send_error(404)
            return
        values = parse_qs(request_uri.query)
        code = values.get("code", [""])[0]
        state = values.get("state", [""])[0]
        if not code or not state:
            self.send_error(400)
            return
        receiver.callback.update(code=code, state=state)
        message = b"GitHub authorization received. You can close this tab."
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(message)))
        self.end_headers()
        self.wfile.write(message)

    def log_message(self, _format: str, *args: object) -> None:
        return


class LoopbackOAuthServer(HTTPServer):
    """Single-address HTTP server that captures the OAuth callback in memory."""

    handler = OAuthCallbackHandler

    def __init__(self, redirect_uri: str) -> None:
        parsed = urlparse(redirect_uri)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise SystemExit("The live callback listener requires an HTTP loopback redirect URI.")
        if parsed.port is None:
            raise SystemExit("The loopback redirect URI must include a port.")
        self.redirect_path = parsed.path
        self.port = parsed.port
        self.callback: dict[str, str] = {}
        super().__init__((parsed.hostname, parsed.port), self.handler)

    def wait_callback(self, timeout: int = 180) -> dict[str, str]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.callback:
                return self.callback
            time.sleep(0.1)
        raise SystemExit("No GitHub authorisation callback was received in time.")
