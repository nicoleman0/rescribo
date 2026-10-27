"""Endpoint safety for Settings base URLs. DNS is patched; nothing leaves the machine."""

import socket
from typing import Any
from unittest.mock import patch

import httpcore
import httpx
import pytest

from connections.errors import SetupError
from integrations.model import endpoint
from integrations.model.clients import Endpoint, generate_json

BLOCKED = [
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "100.64.0.1",
    "::1",
    "fc00::1",
    "fe80::1",
    "::ffff:127.0.0.1",
    "0.0.0.0",
    "224.0.0.1",
]
PUBLIC = "93.184.216.34"


def resolves_to(*addresses: str) -> Any:
    def getaddrinfo(host: str, port: int, *args: Any, **kwargs: Any) -> list[Any]:
        return [
            (
                socket.AF_INET6 if ":" in address else socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                (address, port),
            )
            for address in addresses
        ]

    return patch("integrations.model.endpoint.socket.getaddrinfo", getaddrinfo)


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.test/v1",
        "https://user:pass@api.example.test/v1",
        "https://api.example.test/v1?key=1",
        "https://api.example.test/v1#x",
        "https:///v1",
        "https://api.example.test:99999/v1",
        "https://" + "a" * 500 + ".test",
    ],
)
def test_settings_url_rejects_unsafe_shapes(url: str) -> None:
    with pytest.raises(SetupError) as excinfo:
        endpoint.validate_settings_url(url)
    assert excinfo.value.code == "invalid_base_url"


def test_settings_url_drops_trailing_slash() -> None:
    assert endpoint.validate_settings_url("https://api.example.test/v1/") == (
        "https://api.example.test/v1"
    )


@pytest.mark.parametrize("address", BLOCKED)
def test_non_public_addresses_are_blocked_at_connect(address: str) -> None:
    with (
        resolves_to(address),
        patch.object(httpcore.SyncBackend, "connect_tcp") as connect,
        pytest.raises(SetupError) as excinfo,
    ):
        endpoint.GuardedBackend().connect_tcp("api.example.test", 443)
    assert excinfo.value.code == "endpoint_blocked"
    assert address not in excinfo.value.detail
    connect.assert_not_called()


def test_one_private_answer_refuses_the_host() -> None:
    with (
        resolves_to(PUBLIC, "10.0.0.1"),
        patch.object(httpcore.SyncBackend, "connect_tcp") as connect,
        pytest.raises(SetupError, match="public addresses"),
    ):
        endpoint.GuardedBackend().connect_tcp("api.example.test", 443)
    connect.assert_not_called()


def test_public_address_connects_to_the_checked_address() -> None:
    with resolves_to(PUBLIC), patch.object(httpcore.SyncBackend, "connect_tcp") as connect:
        endpoint.GuardedBackend().connect_tcp("api.example.test", 443, timeout=5)
    assert connect.call_args.args[:2] == (PUBLIC, 443)


def test_rebinding_is_caught_on_the_next_connection() -> None:
    backend = endpoint.GuardedBackend()
    with resolves_to(PUBLIC), patch.object(httpcore.SyncBackend, "connect_tcp"):
        backend.connect_tcp("api.example.test", 443)
    with (
        resolves_to("127.0.0.1"),
        patch.object(httpcore.SyncBackend, "connect_tcp") as connect,
        pytest.raises(SetupError, match="public addresses"),
    ):
        backend.connect_tcp("api.example.test", 443)
    connect.assert_not_called()


def test_guarded_client_refuses_before_any_socket_opens() -> None:
    with (
        resolves_to("127.0.0.1"),
        patch.object(httpcore.SyncBackend, "connect_tcp") as connect,
        pytest.raises(SetupError, match="public addresses"),
    ):
        with endpoint.guarded_client() as http:
            http.post("https://api.example.test/v1/chat/completions")
    connect.assert_not_called()


def test_clients_ignore_proxy_variables_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:3128")
    for factory in (endpoint.guarded_client, endpoint.config_client):
        with factory() as http:
            assert http.trust_env is False
            assert http.follow_redirects is False


def test_redirect_is_an_error_without_a_second_request() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    with pytest.raises(SetupError) as excinfo:
        generate_json(
            http,
            Endpoint("openai", "https://api.example.test/v1", "m", private_allowed=False),
            "key",
            system="s",
            user="u",
            schema={"type": "object"},
            max_tokens=10,
        )
    assert excinfo.value.code == "provider_unavailable"
    assert len(seen) == 1
