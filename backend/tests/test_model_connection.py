"""Model connection services and API on real PostgreSQL. The provider is a mock transport."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from cryptography.fernet import Fernet
from django.test import Client, override_settings

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections.credentials import decrypt
from connections.errors import SetupError
from connections.model_access import model_client
from connections.model_connection import connect_model
from connections.models import Connection
from feedback.models import ReportNotificationOperation
from feedback.reports import link_report
from integrations.model import endpoint
from integrations.model.config import DeploymentModel

pytestmark = pytest.mark.django_db

KEY = "sk-secret-marker-5e1d"
NEW_KEY = "sk-new-marker-2b7c"
BASE = "https://api.example.test/v1"
MANAGED = DeploymentModel("openai", "http://ollama:11434/v1", "llama3.3", "TEST_MODEL_KEY")


@dataclass
class FakeProvider:
    """Answers the connection test like a model would, or fails as told."""

    status: int = 200
    content: str | None = None
    requests: list[httpx.Request] = field(default_factory=list)
    clients: list[str] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "nope"})
        body = json.loads(request.content)
        nonce = re.search(r'nonce "([0-9a-f]+)"', body["messages"][-1]["content"])
        assert nonce is not None
        content = self.content or json.dumps({"status": "ok", "nonce": nonce.group(1)})
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}
        )

    def client(self, kind: str) -> httpx.Client:
        self.clients.append(kind)
        return httpx.Client(transport=httpx.MockTransport(self.handle))


@pytest.fixture(autouse=True)
def credential_key() -> Iterator[None]:
    with override_settings(
        RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode(), RESCRIBO_MODEL_DEPLOYMENT=None
    ):
        yield


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    fake = FakeProvider()
    monkeypatch.setattr(endpoint, "guarded_client", lambda: fake.client("guarded"))
    monkeypatch.setattr(endpoint, "config_client", lambda: fake.client("config"))
    return fake


@pytest.fixture
def owner(client: Client) -> Membership:
    actor = make_membership(role="owner")
    login(client, actor)
    return actor


def login(client: Client, actor: Membership) -> None:
    client.force_login(actor.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = actor.user.session_generation
    session.save()


def post(client: Client, actor: Membership, path: str, body: dict[str, Any]) -> Any:
    return client.post(
        f"/api/workspaces/{actor.workspace_id}/{path}", body, content_type="application/json"
    )


def connect(actor: Membership, **overrides: Any) -> None:
    values: dict[str, Any] = {
        "api_style": "openai",
        "base_url": BASE,
        "model": "gpt-test",
        "api_key": KEY,
        "consent": True,
    }
    connect_model(actor, **(values | overrides))


def row_of(actor: Membership) -> Connection:
    return Connection.objects.get(workspace_id=actor.workspace_id, provider="model")


def test_owner_connects_and_the_key_is_encrypted(provider: FakeProvider, owner: Membership) -> None:
    connect(owner)
    row = row_of(owner)
    assert (row.status, row.api_style, row.base_url, row.model) == (
        "active",
        "openai",
        BASE,
        "gpt-test",
    )
    assert row.consented_at and row.last_success_at
    assert KEY not in row.credential and decrypt(row.credential) == KEY
    assert provider.clients == ["guarded"]
    request = provider.requests[0]
    assert str(request.url) == f"{BASE}/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"consent": False}, "consent_required"),
        ({"api_key": ""}, "key_required"),
        ({"base_url": "http://api.example.test/v1"}, "invalid_base_url"),
        ({"api_style": "cohere"}, "invalid_request"),
    ],
)
def test_refusals_before_any_request_save_nothing(
    provider: FakeProvider, owner: Membership, overrides: dict[str, Any], code: str
) -> None:
    with pytest.raises(SetupError) as excinfo:
        connect(owner, **overrides)
    assert excinfo.value.code == code
    assert provider.requests == []
    assert not Connection.objects.filter(provider="model").exists()


@pytest.mark.parametrize(
    ("status", "content", "code"),
    [
        (401, None, "model_auth_rejected"),
        (404, None, "model_not_found"),
        (200, "plain text", "model_no_structured_output"),
        (200, json.dumps({"status": "ok", "nonce": "stale"}), "model_no_structured_output"),
    ],
)
def test_failed_test_saves_nothing(
    provider: FakeProvider, owner: Membership, status: int, content: str | None, code: str
) -> None:
    provider.status, provider.content = status, content
    with pytest.raises(SetupError) as excinfo:
        connect(owner)
    assert excinfo.value.code == code
    assert not Connection.objects.filter(provider="model").exists()


def test_failed_test_leaves_an_existing_connection_unchanged(
    provider: FakeProvider, owner: Membership
) -> None:
    connect(owner)
    before = row_of(owner)
    provider.status = 401
    with pytest.raises(SetupError):
        connect(owner, model="other", api_key=NEW_KEY)
    after = row_of(owner)
    assert (after.model, after.credential, after.version) == (
        before.model,
        before.credential,
        before.version,
    )


def test_demo_and_non_owner_are_refused_without_a_request(provider: FakeProvider) -> None:
    demo = make_membership(role="owner", workspace=make_workspace(slug="demo", is_demo=True))
    with pytest.raises(SetupError, match="demo"):
        connect(demo)
    member = make_membership(
        role="member",
        workspace=make_workspace(slug="member-only"),
        user=make_user(email="member-only@example.test"),
    )
    with pytest.raises(Exception, match="permission"):
        connect(member)
    assert provider.requests == []
    assert not Connection.objects.filter(provider="model").exists()


def test_changing_only_the_model_reuses_the_stored_key(
    provider: FakeProvider, owner: Membership
) -> None:
    connect(owner)
    connect(owner, model="gpt-other", api_key="")
    row = row_of(owner)
    assert row.model == "gpt-other" and decrypt(row.credential) == KEY
    assert provider.requests[-1].headers["authorization"] == f"Bearer {KEY}"
    assert json.loads(provider.requests[-1].content)["model"] == "gpt-other"


@pytest.mark.parametrize(
    "overrides",
    [{"base_url": "https://other.example.test/v1"}, {"api_style": "anthropic"}],
)
def test_changing_endpoint_needs_a_new_key(
    provider: FakeProvider, owner: Membership, overrides: dict[str, Any]
) -> None:
    connect(owner)
    sent = len(provider.requests)
    with pytest.raises(SetupError) as excinfo:
        connect(owner, api_key="", **overrides)
    assert excinfo.value.code == "key_required"
    assert len(provider.requests) == sent
    assert row_of(owner).base_url == BASE


def test_model_client_guard(provider: FakeProvider, owner: Membership) -> None:
    demo = make_workspace(slug="demo", is_demo=True)
    with pytest.raises(SetupError, match="demo"):
        model_client(demo.pk)
    with pytest.raises(SetupError) as excinfo:
        model_client(owner.workspace_id)
    assert excinfo.value.code == "model_not_connected"
    connect(owner)
    row = row_of(owner)
    for status, consented in (("error", row.consented_at), ("active", None)):
        Connection.objects.filter(pk=row.pk).update(status=status, consented_at=consented)
        with pytest.raises(SetupError) as excinfo:
            model_client(owner.workspace_id)
        assert excinfo.value.code == "model_not_connected"
    Connection.objects.filter(pk=row.pk).update(status="active", consented_at=row.consented_at)
    sent = len(provider.requests)
    client = model_client(owner.workspace_id)
    assert client.endpoint.base_url == BASE and not client.endpoint.private_allowed
    assert KEY not in repr(client)
    # The refusals above built no request.
    assert sent == 1


def test_managed_deployment(
    provider: FakeProvider, owner: Membership, monkeypatch: pytest.MonkeyPatch, client: Client
) -> None:
    monkeypatch.setenv("TEST_MODEL_KEY", KEY)
    with override_settings(RESCRIBO_MODEL_DEPLOYMENT=MANAGED):
        with pytest.raises(SetupError) as excinfo:
            model_client(owner.workspace_id)
        assert excinfo.value.code == "model_not_connected"
        with pytest.raises(SetupError) as excinfo:
            connect(owner)
        assert excinfo.value.code == "deployment_managed"
        assert provider.requests == []
        connect_model(owner, api_style="", base_url="", model="", api_key="", consent=True)
        row = row_of(owner)
        assert (row.status, row.base_url, row.credential) == ("active", "", "")
        assert provider.clients == ["config"]
        assert str(provider.requests[0].url) == "http://ollama:11434/v1/chat/completions"
        assert provider.requests[0].headers["authorization"] == f"Bearer {KEY}"
        resolved = model_client(owner.workspace_id)
        assert resolved.endpoint.model == "llama3.3" and resolved.endpoint.private_allowed
        listed = client.get(f"/api/workspaces/{owner.workspace_id}/connections/").json()
        assert listed[0]["base_url"] == MANAGED.base_url
        deployment = client.get(
            f"/api/workspaces/{owner.workspace_id}/connections/model/deployment/"
        ).json()
        assert deployment == {
            "managed": True,
            "api_style": "openai",
            "base_url": MANAGED.base_url,
            "model": "llama3.3",
        }
    # Consent was for the deployment default, not whatever Settings would name.
    with pytest.raises(SetupError, match="Connect a model provider"):
        model_client(owner.workspace_id)


def test_settings_connection_stops_when_a_deployment_default_appears(
    provider: FakeProvider, owner: Membership, monkeypatch: pytest.MonkeyPatch, client: Client
) -> None:
    connect(owner)
    monkeypatch.setenv("TEST_MODEL_KEY", KEY)
    with override_settings(RESCRIBO_MODEL_DEPLOYMENT=MANAGED):
        with pytest.raises(SetupError) as excinfo:
            model_client(owner.workspace_id)
        assert excinfo.value.code == "model_not_connected"
        listed = client.get(f"/api/workspaces/{owner.workspace_id}/connections/").json()
        assert listed[0]["status"] == "disconnected"


def test_refresh_moves_an_active_row_to_error(
    provider: FakeProvider, owner: Membership, client: Client
) -> None:
    connect(owner)
    provider.status = 401
    response = post(client, owner, "connections/model/refresh/", {"version": 2})
    assert response.status_code == 400 and response.json()["reason"] == "model_auth_rejected"
    row = row_of(owner)
    assert row.status == "error" and row.error_code == "model_auth_rejected"
    listed = client.get(f"/api/workspaces/{owner.workspace_id}/connections/").json()
    assert "rejected the API key" in listed[0]["error_detail"]
    provider.status = 200
    assert post(client, owner, "connections/model/refresh/", {"version": 3}).status_code == 204
    assert row_of(owner).status == "active"


def test_model_failure_and_disconnect_leave_notifications_alone(
    provider: FakeProvider, owner: Membership, client: Client
) -> None:
    report = make_report(actor=owner)
    problem = make_problem(actor=owner)
    report = link_report(
        actor=owner, report_id=report.pk, problem_id=problem.pk, expected_version=1
    )
    make_notification(report=report)
    connect(owner)
    provider.status = 500
    post(client, owner, "connections/model/refresh/", {"version": 2})
    body = {"version": 3, "confirmation": "DISCONNECT"}
    assert post(client, owner, "connections/model/disconnect/", body).status_code == 204
    assert ReportNotificationOperation.objects.get(report=report).state == "draft"


def test_disconnect_clears_key_settings_and_consent(
    provider: FakeProvider, owner: Membership, client: Client
) -> None:
    connect(owner)
    body = {"version": 2, "confirmation": "DISCONNECT"}
    assert post(client, owner, "connections/model/disconnect/", body).status_code == 204
    row = row_of(owner)
    assert (row.status, row.credential, row.api_style, row.base_url, row.model) == (
        "disconnected",
        "",
        "",
        "",
        "",
    )
    assert row.consented_at is None
    with pytest.raises(SetupError):
        model_client(owner.workspace_id)
    with pytest.raises(SetupError) as excinfo:
        connect(owner, api_key="")
    assert excinfo.value.code == "key_required"


def test_api_connect_and_list(provider: FakeProvider, owner: Membership, client: Client) -> None:
    body = {
        "api_style": "openai",
        "base_url": BASE + "/",
        "model": "gpt-test",
        "api_key": KEY,
        "consent": True,
    }
    response = post(client, owner, "connections/model/connect/", body)
    assert response.status_code == 204
    listed = client.get(f"/api/workspaces/{owner.workspace_id}/connections/")
    assert KEY not in listed.content.decode()
    model = next(item for item in listed.json() if item["provider"] == "model")
    assert (model["status"], model["api_style"], model["base_url"], model["model"]) == (
        "active",
        "openai",
        BASE,
        "gpt-test",
    )
    assert model["operations"] == {"queued": 0, "running": 0, "failed": 0, "uncertain": 0}
    deployment = client.get(f"/api/workspaces/{owner.workspace_id}/connections/model/deployment/")
    assert deployment.json() == {"managed": False, "api_style": "", "base_url": "", "model": ""}


def test_api_refusals(provider: FakeProvider, owner: Membership, client: Client) -> None:
    body = {"api_style": "openai", "base_url": BASE, "model": "m", "api_key": KEY}
    response = post(client, owner, "connections/model/connect/", body | {"consent": False})
    assert response.status_code == 400 and response.json()["reason"] == "consent_required"
    response = post(
        client,
        owner,
        "connections/model/connect/",
        body | {"consent": True, "base_url": "http://api.example.test/v1"},
    )
    assert response.status_code == 400
    assert "https://" in response.json()["field_errors"]["base_url"][0]
    provider.status = 401
    response = post(client, owner, "connections/model/connect/", body | {"consent": True})
    assert response.status_code == 400 and response.json()["reason"] == "model_auth_rejected"
    assert KEY not in response.content.decode()
    for path in ("setup/", "callback/"):
        method = client.post if path == "setup/" else client.get
        assert (
            method(f"/api/workspaces/{owner.workspace_id}/connections/model/{path}").status_code
            == 404
        )


def test_member_reads_but_cannot_change(provider: FakeProvider, owner: Membership) -> None:
    connect(owner)
    member = make_membership(
        role="member", workspace=owner.workspace, user=make_user(email="m@example.test")
    )
    member_client = Client()
    login(member_client, member)
    listed = member_client.get(f"/api/workspaces/{owner.workspace_id}/connections/").json()
    assert listed[0]["model"] == "gpt-test"
    body = {"api_style": "openai", "base_url": BASE, "model": "m", "api_key": KEY, "consent": True}
    assert post(member_client, member, "connections/model/connect/", body).status_code == 403
    assert (
        post(member_client, member, "connections/model/refresh/", {"version": 2}).status_code == 403
    )
    assert row_of(owner).model == "gpt-test"


def test_owner_of_another_workspace_cannot_touch_this_row(
    provider: FakeProvider, owner: Membership
) -> None:
    connect(owner)
    other = make_membership(
        role="owner",
        workspace=make_workspace(slug="other"),
        user=make_user(email="other@example.test"),
    )
    other_client = Client()
    login(other_client, other)
    base = f"/api/workspaces/{owner.workspace_id}/connections/model/"
    body = {"api_style": "openai", "base_url": BASE, "model": "x", "api_key": KEY, "consent": True}
    sent = len(provider.requests)
    for path, payload in (
        ("connect/", body),
        ("refresh/", {"version": 2}),
        ("disconnect/", {"version": 2, "confirmation": "DISCONNECT"}),
    ):
        response = other_client.post(base + path, payload, content_type="application/json")
        assert response.status_code in (403, 404)
    assert len(provider.requests) == sent
    row = row_of(owner)
    assert (row.status, row.model, row.version) == ("active", "gpt-test", 2)
