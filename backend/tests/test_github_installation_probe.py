import json
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from integrations.github_app.client import GitHubAppClient
from integrations.github_app.probe import InstallationProbe, InvalidInstallation
from integrations.github_app.state import InvalidOAuthState, OAuthStateStore


@pytest.fixture
def private_key() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def test_oauth_state_is_bound_single_use_and_not_stored_raw(tmp_path: Path) -> None:
    store = OAuthStateStore(tmp_path)
    state = store.create("workspace-a", "owner/repository", now=100)

    assert state not in next(tmp_path.iterdir()).read_text(encoding="utf-8")
    with pytest.raises(InvalidOAuthState, match="another workspace"):
        store.consume(state, "workspace-b", now=101)
    assert store.consume(state, "workspace-a", now=101) == "owner/repository"
    with pytest.raises(InvalidOAuthState, match="already been used"):
        store.consume(state, "workspace-a", now=102)


def test_oauth_state_expires(tmp_path: Path) -> None:
    store = OAuthStateStore(tmp_path, lifetime_seconds=10)
    state = store.create("workspace-a", "owner/repository", now=100)

    with pytest.raises(InvalidOAuthState, match="expired"):
        store.consume(state, "workspace-a", now=111)


def test_probe_verifies_user_access_and_restricts_installation_token(private_key: bytes) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/repos/owner/disposable/installation":
            return httpx.Response(
                200,
                json={
                    "id": 42,
                    "permissions": {"issues": "write", "metadata": "read"},
                    "repository_selection": "selected",
                    "suspended_at": None,
                },
            )
        if request.url.path == "/user/installations/42/repositories":
            assert request.headers["Authorization"] == "Bearer user-token"
            return httpx.Response(
                200,
                json={"total_count": 1, "repositories": [{"full_name": "owner/disposable"}]},
            )
        if request.url.path == "/app/installations/42/access_tokens":
            assert json.loads(request.content) == {
                "repositories": ["disposable"],
                "permissions": {"issues": "write", "metadata": "read"},
            }
            return httpx.Response(
                201,
                json={"token": "installation-token", "expires_at": "2026-09-20T21:00:00Z"},
            )
        if request.url.path == "/repos/owner/disposable":
            assert request.headers["Authorization"] == "Bearer installation-token"
            return httpx.Response(
                200,
                json={"full_name": "owner/disposable", "visibility": "private"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        client = GitHubAppClient(http, app_id="123", private_key=private_key)
        result = InstallationProbe(client).run(
            user_token="user-token",
            expected_repository="owner/disposable",
        )

    assert result.connection_status == "active"
    assert result.repository == "owner/disposable"
    assert result.visibility == "private"
    assert result.user_access_verified is True
    assert len(requests) == 4


def test_probe_rejects_unexpected_selected_repository(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/one/installation":
            return httpx.Response(
                200,
                json={
                    "id": 42,
                    "permissions": {"issues": "write", "metadata": "read"},
                    "repository_selection": "selected",
                    "suspended_at": None,
                },
            )
        return httpx.Response(
            200,
            json={
                "total_count": 2,
                "repositories": [{"full_name": "owner/one"}, {"full_name": "owner/two"}],
            },
        )

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        probe = InstallationProbe(GitHubAppClient(http, app_id="123", private_key=private_key))
        with pytest.raises(InvalidInstallation, match="unexpected number"):
            probe.run(
                user_token="user-token",
                expected_repository="owner/one",
            )


def test_probe_allows_named_additional_repository(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/owner/disposable/installation":
            return httpx.Response(
                200,
                json={
                    "id": 42,
                    "permissions": {"issues": "write", "metadata": "read"},
                    "repository_selection": "selected",
                    "suspended_at": None,
                },
            )
        if request.url.path == "/user/installations/42/repositories":
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "repositories": [
                        {"full_name": "owner/anchor"},
                        {"full_name": "owner/disposable"},
                    ],
                },
            )
        if request.url.path == "/app/installations/42/access_tokens":
            return httpx.Response(
                201,
                json={"token": "installation-token", "expires_at": "2026-09-20T21:00:00Z"},
            )
        if request.url.path == "/repos/owner/disposable":
            return httpx.Response(
                200,
                json={"full_name": "owner/disposable", "visibility": "private"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        result = InstallationProbe(
            GitHubAppClient(http, app_id="123", private_key=private_key)
        ).run(
            user_token="user-token",
            expected_repository="owner/disposable",
            additional_repositories={"owner/anchor"},
        )

    assert result.connection_status == "active"
    assert result.repository == "owner/disposable"


def test_probe_rejects_extra_app_permissions(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 42,
                "permissions": {"contents": "read", "issues": "write", "metadata": "read"},
                "repository_selection": "selected",
                "suspended_at": None,
            },
        )

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        probe = InstallationProbe(GitHubAppClient(http, app_id="123", private_key=private_key))
        with pytest.raises(InvalidInstallation, match="only Issues write"):
            probe.run(user_token="user-token", expected_repository="owner/disposable")


@pytest.mark.parametrize(
    ("status_code", "suspended_at", "expected_status"),
    [(404, None, "revoked_or_unavailable"), (200, "2026-09-20T20:00:00Z", "suspended")],
)
def test_probe_reports_inactive_installations(
    private_key: bytes,
    status_code: int,
    suspended_at: str | None,
    expected_status: str,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "id": 42,
                "permissions": {"issues": "write", "metadata": "read"},
                "repository_selection": "selected",
                "suspended_at": suspended_at,
            },
        )

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        result = InstallationProbe(
            GitHubAppClient(http, app_id="123", private_key=private_key)
        ).run(
            user_token="user-token",
            expected_repository="owner/disposable",
        )

    assert result.connection_status == expected_status
    assert result.repository == "owner/disposable"
    assert result.user_access_verified is False
