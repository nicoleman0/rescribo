from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from integrations.github_app.client import GitHubAPIError, GitHubAppClient, installation_failure
from integrations.github_app.releases import (
    ReleaseNotFound,
    get_release,
    list_releases,
    parse_release_payload,
)


@pytest.fixture
def client() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return key


def payload(**changes: Any) -> dict[str, Any]:
    return {
        "id": 4,
        "tag_name": "v4.0",
        "name": "",
        "draft": False,
        "prerelease": True,
        "published_at": "2026-01-01T00:00:00Z",
        "html_url": "https://github.com/acme/widgets/releases/tag/v4.0",
        **changes,
    }


def test_release_client_lists_pages_and_fetches_by_id(client: bytes) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/releases"):
            return httpx.Response(
                200,
                json=[payload()],
                headers={"Link": '<https://api.github.com/?page=2>; rel="next"'},
            )
        if request.url.path.endswith("/4"):
            return httpx.Response(200, json=payload())
        raise AssertionError(request.url)

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        api = GitHubAppClient(http, app_id="1", private_key=client)
        rows, has_next = api.list_releases(
            installation_token="token", owner="acme", name="widgets", page=1
        )
        api.get_release(installation_token="token", owner="acme", name="widgets", release_id=4)
    assert rows[0]["id"] == 4 and has_next
    assert dict(requests[0].url.params) == {"per_page": "20", "page": "1"}
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert requests[1].url.path.endswith("/releases/4")


def test_release_payload_validation_and_draft_filtering(client: bytes) -> None:
    assert parse_release_payload(payload(), repository_name="ACME/widgets").name == "v4.0"
    assert parse_release_payload(payload(), repository_name="acme/widgets").prerelease
    with pytest.raises(ValueError):
        parse_release_payload(
            payload(html_url="https://github.com/elsewhere/widgets/releases/tag/v4.0"),
            repository_name="acme/widgets",
        )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[payload(draft=True), payload(id=5)])

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        rows, _ = list_releases(
            GitHubAppClient(http, app_id="1", private_key=client),
            installation_token="token",
            repository_name="acme/widgets",
            page=1,
        )
    assert [row.external_id for row in rows] == ["5"]


def test_get_release_maps_404_and_installation_failure_ignores_422(client: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(handler)
    ) as http:
        with pytest.raises(ReleaseNotFound):
            get_release(
                GitHubAppClient(http, app_id="1", private_key=client),
                installation_token="token",
                repository_name="acme/widgets",
                release_id=9,
            )
    assert installation_failure(GitHubAPIError("installation token creation", 422)) is None
