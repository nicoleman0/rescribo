import hashlib
import hmac
import json
from collections.abc import Callable

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from integrations.github_app.client import GitHubAPIError, GitHubAppClient
from integrations.github_app.issues import (
    EngineeringIssueSnapshot,
    IssueLinkError,
    parse_issue_reference,
    resolve_issue_link,
)
from integrations.github_app.webhooks import (
    InvalidWebhookPayload,
    InvalidWebhookSignature,
    IssueEvent,
    apply_issue_event,
    parse_installation_event,
    parse_issue_event,
    verify_webhook_signature,
)


@pytest.fixture
def private_key() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def make_client(
    private_key: bytes, handler: Callable[[httpx.Request], httpx.Response]
) -> GitHubAppClient:
    http = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    return GitHubAppClient(http, app_id="123", private_key=private_key)


ISSUE_PAYLOAD = {
    "id": 555,
    "number": 7,
    "title": "Export button does nothing",
    "state": "open",
    "state_reason": None,
    "html_url": "https://github.com/owner/disposable/issues/7",
    "repository_url": "https://api.github.com/repos/owner/disposable",
    "repository": {"id": 999, "full_name": "owner/disposable"},
    "updated_at": "2026-09-20T21:00:00Z",
}


def test_create_and_read_issue_round_trip(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/repos/owner/disposable/issues":
            assert request.headers["Authorization"] == "Bearer installation-token"
            assert json.loads(request.content) == {"title": "Title", "body": "Body"}
            return httpx.Response(201, json={**ISSUE_PAYLOAD, "title": "Title"})
        if request.method == "GET" and request.url.path == "/repos/owner/disposable/issues/7":
            return httpx.Response(200, json=ISSUE_PAYLOAD)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = make_client(private_key, handler)
    created = client.create_issue(
        installation_token="installation-token",
        owner="owner",
        name="disposable",
        title="Title",
        body="Body",
    )
    fetched = client.get_issue(
        installation_token="installation-token", owner="owner", name="disposable", number=7
    )

    assert created["number"] == 7
    assert fetched["title"] == ISSUE_PAYLOAD["title"]


def test_parse_issue_reference_accepts_numbers_and_bound_urls() -> None:
    assert parse_issue_reference("7", expected_repository="owner/disposable") == 7
    assert (
        parse_issue_reference(
            "https://github.com/owner/disposable/issues/7", expected_repository="owner/disposable"
        )
        == 7
    )
    with pytest.raises(IssueLinkError, match="other/repository"):
        parse_issue_reference(
            "https://github.com/other/repository/issues/7", expected_repository="owner/disposable"
        )
    with pytest.raises(IssueLinkError, match="issue number or"):
        parse_issue_reference("not-an-issue", expected_repository="owner/disposable")
    with pytest.raises(IssueLinkError, match="issue number or"):
        parse_issue_reference("0", expected_repository="owner/disposable")
    with pytest.raises(IssueLinkError, match="issue number or"):
        parse_issue_reference("²", expected_repository="owner/disposable")


def test_resolve_issue_link_returns_sanitised_issue(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/owner/disposable/issues/7"
        return httpx.Response(200, json=ISSUE_PAYLOAD)

    linked = resolve_issue_link(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        reference="https://github.com/owner/disposable/issues/7",
    )

    assert linked == EngineeringIssueSnapshot(
        issue_id="555",
        number=7,
        title="Export button does nothing",
        url="https://github.com/owner/disposable/issues/7",
        state="open",
        state_reason=None,
        updated_at="2026-09-20T21:00:00Z",
        repository_id="999",
        repository_name="owner/disposable",
    )


def test_resolve_issue_link_rejects_pull_requests(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                **ISSUE_PAYLOAD,
                "pull_request": {"url": "https://api.github.com/repos/owner/disposable/pulls/7"},
            },
        )

    with pytest.raises(IssueLinkError, match="Pull requests"):
        resolve_issue_link(
            make_client(private_key, handler),
            expected_repository_id="999",
            installation_token="installation-token",
            expected_repository="owner/disposable",
            reference="7",
        )


def test_resolve_issue_link_rejects_issues_from_other_repositories(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("Cross-repository references must be rejected before any request.")

    with pytest.raises(IssueLinkError, match="other/repository"):
        resolve_issue_link(
            make_client(private_key, handler),
            expected_repository_id="999",
            installation_token="installation-token",
            expected_repository="owner/disposable",
            reference="https://github.com/other/repository/issues/7",
        )


def test_resolve_issue_link_rejects_unknown_issues(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(IssueLinkError, match="not found"):
        resolve_issue_link(
            make_client(private_key, handler),
            expected_repository_id="999",
            installation_token="installation-token",
            expected_repository="owner/disposable",
            reference="7",
        )


def test_resolve_issue_link_rejects_moved_issues(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, json={"message": "Moved Permanentely"})

    with pytest.raises(IssueLinkError, match="not found"):
        resolve_issue_link(
            make_client(private_key, handler),
            expected_repository_id="999",
            installation_token="installation-token",
            expected_repository="owner/disposable",
            reference="7",
        )


def sign(secret: bytes, body: bytes) -> str:
    return f"sha256={hmac.new(secret, body, hashlib.sha256).hexdigest()}"


def test_webhook_signature_verification() -> None:
    body = b'{"action":"closed"}'
    verify_webhook_signature(
        secret=b"wh-secret", body=body, signature_header=sign(b"wh-secret", body)
    )
    with pytest.raises(InvalidWebhookSignature, match="missing"):
        verify_webhook_signature(secret=b"wh-secret", body=body, signature_header=None)
    with pytest.raises(InvalidWebhookSignature, match="malformed"):
        verify_webhook_signature(secret=b"wh-secret", body=body, signature_header="sha1=abc")
    with pytest.raises(InvalidWebhookSignature, match="does not match"):
        verify_webhook_signature(
            secret=b"wh-secret", body=body, signature_header=sign(b"other", body)
        )
    with pytest.raises(InvalidWebhookSignature, match="does not match"):
        verify_webhook_signature(
            secret=b"wh-secret",
            body=b'{"action":"reopened"}',
            signature_header=sign(b"wh-secret", body),
        )


def issue_payload(action: str, *, state_reason: str | None = "completed") -> dict:
    return {
        "action": action,
        "issue": {
            "id": 555,
            "number": 7,
            "state_reason": state_reason,
            "updated_at": "2026-09-20T21:05:00Z",
        },
        "repository": {"id": 999, "full_name": "owner/disposable"},
    }


def test_parse_issue_event_tracks_close_reopen_edit_delete() -> None:
    event = parse_issue_event(issue_payload("closed"))
    assert event == IssueEvent(
        action="closed",
        number=7,
        repository="owner/disposable",
        state_reason="completed",
        updated_at="2026-09-20T21:05:00Z",
        repository_id="999",
        issue_id="555",
    )
    assert parse_issue_event(issue_payload("opened")) is None
    assert parse_issue_event(issue_payload("labeled")) is None
    transferred = parse_issue_event(issue_payload("transferred"))
    assert transferred is not None and transferred.action == "transferred"
    with pytest.raises(InvalidWebhookPayload):
        parse_issue_event({"action": "closed", "issue": {}, "repository": {}})


def test_parse_installation_event_flags_access_loss() -> None:
    deleted = parse_installation_event("installation", {"action": "deleted"})
    assert deleted is not None and deleted.access_lost is True
    suspended = parse_installation_event("installation", {"action": "suspend"})
    assert suspended is not None and suspended.access_lost is True
    unsuspended = parse_installation_event("installation", {"action": "unsuspend"})
    assert unsuspended is not None and unsuspended.access_lost is False
    removed = parse_installation_event(
        "installation_repositories",
        {
            "action": "removed",
            "repositories_removed": [{"id": 999, "full_name": "owner/disposable"}],
        },
    )
    assert removed is not None
    assert removed.access_lost is True
    assert removed.repositories_removed == ("owner/disposable",)
    added = parse_installation_event(
        "installation_repositories",
        {"action": "added", "repositories_added": [{"id": 999, "full_name": "owner/disposable"}]},
    )
    assert added is not None and added.access_lost is False
    assert parse_installation_event("ping", {"zen": "Keep it logically awesome."}) is None


def closed_event() -> IssueEvent:
    event = parse_issue_event(issue_payload("closed"))
    assert event is not None
    return event


def test_apply_issue_event_fetches_current_state(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/owner/disposable/issues/7"
        return httpx.Response(
            200,
            json={
                **ISSUE_PAYLOAD,
                "state": "closed",
                "state_reason": "not_planned",
                "updated_at": "2026-09-20T21:05:00Z",
            },
        )

    outcome = apply_issue_event(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        event=closed_event(),
        stored_updated_at="2026-09-20T21:00:00Z",
    )

    assert outcome.applied is True
    assert outcome.access == "ok"
    assert outcome.snapshot is not None
    assert outcome.snapshot.state == "closed"
    assert outcome.snapshot.state_reason == "not_planned"
    assert outcome.snapshot.updated_at == "2026-09-20T21:05:00Z"


def test_apply_issue_event_rejects_stale_deliveries(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**ISSUE_PAYLOAD, "state": "closed", "updated_at": "2026-09-20T21:00:00Z"},
        )

    outcome = apply_issue_event(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        event=closed_event(),
        stored_updated_at="2026-09-20T21:30:00Z",
    )

    assert outcome.applied is False
    assert outcome.access == "ok"
    assert outcome.snapshot is not None
    assert outcome.snapshot.updated_at == "2026-09-20T21:00:00Z"


def test_apply_issue_event_maps_inaccessible_issues_to_access_lost(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    outcome = apply_issue_event(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        event=closed_event(),
        stored_updated_at=None,
    )

    assert outcome.applied is False
    assert outcome.access == "access_lost"
    assert outcome.snapshot is None


def test_apply_issue_event_maps_moved_issues_to_access_lost(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, json={"message": "Moved Permanentely"})

    outcome = apply_issue_event(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        event=closed_event(),
        stored_updated_at=None,
    )

    assert outcome.applied is False
    assert outcome.access == "access_lost"


def test_apply_issue_event_treats_transferred_foreign_repository_as_access_lost(
    private_key: bytes,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("A transferred event must not fetch from the destination repository.")

    event = IssueEvent(
        repository_id="999",
        issue_id="555",
        action="transferred",
        number=7,
        repository="other/destination",
        state_reason=None,
        updated_at="2026-09-20T21:05:00Z",
    )
    outcome = apply_issue_event(
        make_client(private_key, handler),
        expected_repository_id="999",
        installation_token="installation-token",
        expected_repository="owner/disposable",
        event=event,
        stored_updated_at="2026-09-20T21:00:00Z",
    )

    assert outcome.applied is False
    assert outcome.access == "access_lost"


def test_apply_issue_event_rejects_events_for_other_repositories(private_key: bytes) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("Events for other repositories must be rejected before any request.")

    foreign = IssueEvent(
        repository_id="999",
        issue_id="555",
        action="closed",
        number=7,
        repository="other/repository",
        state_reason="completed",
        updated_at="2026-09-20T21:05:00Z",
    )
    with pytest.raises(InvalidWebhookPayload, match="other/repository"):
        apply_issue_event(
            make_client(private_key, handler),
            expected_repository_id="999",
            installation_token="installation-token",
            expected_repository="owner/disposable",
            event=foreign,
            stored_updated_at=None,
        )


def test_installation_lifecycle_client_calls(private_key: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE" and request.url.path == "/app/installations/42":
            assert request.headers["Authorization"].startswith("Bearer ey")
            return httpx.Response(204)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = make_client(private_key, handler)
    client.delete_installation(installation_id=42)


@pytest.mark.parametrize(
    "status,headers,limited,delay",
    [
        (403, {"X-RateLimit-Remaining": "4999", "X-RateLimit-Reset": "9999999999"}, False, None),
        (403, {"X-RateLimit-Remaining": "0", "Retry-After": "30"}, True, 30),
        (403, {"Retry-After": "30"}, True, 30),
        (429, {"Retry-After": "30"}, True, 30),
    ],
)
@pytest.mark.parametrize("listing", [False, True])
def test_rate_limit_metadata_is_shared_by_reads_and_listing(
    private_key: bytes,
    status: int,
    headers: dict[str, str],
    limited: bool,
    delay: int | None,
    listing: bool,
) -> None:
    client = make_client(private_key, lambda request: httpx.Response(status, headers=headers))
    with pytest.raises(GitHubAPIError) as caught:
        if listing:
            client.list_issues(installation_token="token", owner="owner", name="disposable", page=1)
        else:
            client.get_issue(installation_token="token", owner="owner", name="disposable", number=7)
    assert caught.value.rate_limited is limited
    assert caught.value.retry_after_seconds == delay


def test_errors_name_the_failed_request(private_key: bytes) -> None:
    client = make_client(private_key, lambda request: httpx.Response(401))
    with pytest.raises(GitHubAPIError) as caught:
        client.create_installation_token(installation_id=1, repository_id="999")
    assert caught.value.operation == "installation token creation"
    assert caught.value.status_code == 401
