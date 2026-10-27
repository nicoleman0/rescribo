"""Outbound HTTP for model providers.

Base URLs from Settings reach only public addresses. The check runs on every new
TCP connection, so DNS rebinding and pooled reconnects cannot bypass it.
"""

import ipaddress
import socket
import time
from collections.abc import Iterable, Iterator
from typing import Any

import httpcore
import httpx

from connections.errors import SetupError, known_error
from integrations.model.config import base_url_problem

MAX_RESPONSE_BYTES = 1_000_000
TOTAL_SECONDS = 60.0
TIMEOUT = httpx.Timeout(TOTAL_SECONDS, connect=5.0)

HTTPCORE_ERRORS = (
    httpcore.TimeoutException,
    httpcore.NetworkError,
    httpcore.ProtocolError,
    httpcore.ProxyError,
    httpcore.UnsupportedProtocol,
)


def validate_settings_url(url: str) -> str:
    """Return the URL without a trailing slash, or refuse it as owner input."""
    problem = base_url_problem(url, ("https",))
    if problem:
        raise SetupError("invalid_base_url", f"The base URL {problem}.")
    return url.rstrip("/")


def is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


class GuardedBackend(httpcore.SyncBackend):
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.NetworkStream:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror, UnicodeError:
            raise httpcore.ConnectError("Could not resolve the host.") from None
        addresses = list(dict.fromkeys(str(info[4][0]) for info in infos))
        # One private answer refuses the host, so a mixed record cannot win a race.
        if not addresses or not all(is_public(address) for address in addresses):
            # Never name the resolved address: it would map the private network for the caller.
            raise known_error("endpoint_blocked")
        failure: Exception | None = None
        for address in addresses:
            try:
                # TLS still verifies against `host`: httpcore sends it as SNI.
                return super().connect_tcp(address, port, timeout, local_address, socket_options)
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                failure = error
        assert failure is not None
        raise failure


class LimitedStream(httpx.SyncByteStream):
    def __init__(self, stream: Iterable[bytes], request: httpx.Request) -> None:
        self.stream = stream
        self.request = request

    def __iter__(self) -> Iterator[bytes]:
        try:
            yield from self.stream
        except HTTPCORE_ERRORS as error:
            raise httpx.TransportError(type(error).__name__, request=self.request) from None

    def close(self) -> None:
        close = getattr(self.stream, "close", None)
        if close is not None:
            close()


class PoolTransport(httpx.BaseTransport):
    """An httpx transport over an httpcore pool with our network backend."""

    def __init__(self, backend: httpcore.NetworkBackend) -> None:
        self.pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(), network_backend=backend
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert isinstance(request.stream, httpx.SyncByteStream)
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            response = self.pool.handle_request(core_request)
        except httpcore.TimeoutException as error:
            raise httpx.TimeoutException(type(error).__name__, request=request) from None
        except HTTPCORE_ERRORS as error:
            raise httpx.TransportError(type(error).__name__, request=request) from None
        assert isinstance(response.stream, Iterable)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=LimitedStream(response.stream, request),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.pool.close()


def guarded_client() -> httpx.Client:
    """For base URLs entered in Settings."""
    return http_client(GuardedBackend())


def config_client() -> httpx.Client:
    """For the operator's config file, which may name local or private hosts."""
    return http_client(httpcore.SyncBackend())


def http_client(backend: httpcore.NetworkBackend) -> httpx.Client:
    return httpx.Client(
        transport=PoolTransport(backend),
        # Proxy variables and redirects could send the key or content to another host.
        trust_env=False,
        follow_redirects=False,
        timeout=TIMEOUT,
    )


def read_limited(response: httpx.Response, started: float) -> bytes:
    """Read the body under the size cap and the total time limit."""
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_RESPONSE_BYTES or time.monotonic() - started > TOTAL_SECONDS:
            raise known_error("provider_unavailable")
    return bytes(body)
