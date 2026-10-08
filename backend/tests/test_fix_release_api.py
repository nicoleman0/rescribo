from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from builders import make_connection, make_membership, make_problem, make_workspace
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections.models import Connection
from feedback.models import Activity, FixRelease, Problem
from feedback.problems import confirm_fix
from integrations.github_app.client import GitHubAppClient

pytestmark = pytest.mark.django_db


def sign_in(client: Client, actor: Membership) -> None:
    client.force_login(actor.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = actor.user.session_generation
    session.save()


def make_provider(
    monkeypatch: pytest.MonkeyPatch,
    *,
    token_status: int = 201,
    release_status: int = 200,
    on_release: Callable[[], Any] | None = None,
) -> list[httpx.Request]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("/access_tokens"):
            if token_status != 201:
                return httpx.Response(token_status, json={"message": "permission missing"})
            assert request.read()
            assert b'"contents":"read"' in request.content
            return httpx.Response(201, json={"token": "release-token", "expires_at": "later"})
        if request.url.path == "/repositories/999":
            return httpx.Response(200, json={"id": 999, "full_name": "acme/widgets"})
        if request.url.path.endswith("/releases"):
            rows = [release(i) for i in range(1, 21)]
            return httpx.Response(
                200, json=rows, headers={"Link": '<https://api.github.com/?page=2>; rel="next"'}
            )
        if "/releases/" in request.url.path:
            if release_status != 200:
                return httpx.Response(release_status)
            if on_release:
                on_release()
            rid = int(request.url.path.rsplit("/", 1)[1])
            return httpx.Response(200, json=release(rid))
        if request.method == "DELETE":
            return httpx.Response(204)
        raise AssertionError(f"Unexpected GitHub request: {request.method} {request.url}")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )

    @contextmanager
    def factory() -> Iterator[GitHubAppClient]:
        with httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(handler)
        ) as http:
            yield GitHubAppClient(http, app_id="123", private_key=key)

    monkeypatch.setattr("feedback.releases.github_client", factory)
    return calls


def release(rid: int) -> dict[str, Any]:
    return {
        "id": rid,
        "tag_name": f"v4.{rid}",
        "name": f"Release {rid}",
        "draft": False,
        "prerelease": rid == 2,
        "published_at": "2026-10-01T12:00:00Z",
        "html_url": f"https://github.com/acme/widgets/releases/tag/v4.{rid}",
    }


def setup_fixed(actor: Membership | None = None) -> tuple[Membership, Connection, Problem]:
    actor = actor or make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    fixed = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Shipped",
        fix_version="4.13",
    )
    return actor, connection, fixed


def test_list_link_replace_and_unlink_release(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, _, problem = setup_fixed()
    sign_in(client, actor)
    calls = make_provider(monkeypatch)
    base = f"/api/workspaces/{actor.workspace_id}"
    listed = client.get(f"{base}/releases/?page=1")
    assert listed.status_code == 200
    assert len(listed.json()["results"]) == 20 and listed.json()["has_next"]
    link_url = f"{base}/problems/{problem.pk}/fix-release/"
    first = client.post(
        link_url,
        {"expected_version": problem.version, "external_id": "1"},
        content_type="application/json",
    )
    assert first.status_code == 200 and first.json()["fix_release"]["tag_name"] == "v4.1"
    assert FixRelease.objects.get(problem=problem).linked_by_id == actor.pk
    second = client.post(
        link_url,
        {"expected_version": first.json()["version"], "external_id": "2"},
        content_type="application/json",
    )
    assert second.status_code == 200 and second.json()["fix_release"]["tag_name"] == "v4.2"
    removed = client.post(
        f"{link_url}unlink/",
        {"expected_version": second.json()["version"]},
        content_type="application/json",
    )
    assert removed.status_code == 200 and removed.json()["fix_release"] is None
    assert not FixRelease.objects.filter(problem=problem).exists()
    assert (
        list(Activity.objects.filter(record_id=problem.pk).values_list("action", flat=True)).count(
            "problem.fix_release_linked"
        )
        == 2
    )
    assert any(request.url.path.endswith("/releases/2") for request in calls)


def test_release_access_422_does_not_disconnect_installation(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, connection, problem = setup_fixed()
    sign_in(client, actor)
    make_provider(monkeypatch, token_status=422)
    response = client.post(
        f"/api/workspaces/{actor.workspace_id}/problems/{problem.pk}/fix-release/",
        {"expected_version": problem.version, "external_id": "1"},
        content_type="application/json",
    )
    connection.refresh_from_db()
    assert response.status_code == 409 and response.json()["reason"] == "release_access_missing"
    assert connection.status == Connection.Status.ACTIVE


def test_missing_connection_and_missing_release_have_distinct_errors(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    fixed = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Shipped",
        fix_version="4.13",
    )
    sign_in(client, actor)
    response = client.get(f"/api/workspaces/{actor.workspace_id}/releases/")
    assert response.status_code == 409 and response.json()["reason"] == "connection_not_ready"
    make_connection(workspace=actor.workspace)
    make_provider(monkeypatch, release_status=404)
    response = client.post(
        f"/api/workspaces/{actor.workspace_id}/problems/{problem.pk}/fix-release/",
        {"expected_version": fixed.version, "external_id": "999"},
        content_type="application/json",
    )
    assert response.status_code == 422 and response.json()["reason"] == "release_not_found"


def test_stale_version_and_open_problem_are_rejected(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, _, fixed = setup_fixed()
    sign_in(client, actor)
    make_provider(monkeypatch)
    url = f"/api/workspaces/{actor.workspace_id}/problems/{fixed.pk}/fix-release/"
    stale = client.post(
        url, {"expected_version": 1, "external_id": "1"}, content_type="application/json"
    )
    assert stale.status_code == 409 and stale.json()["reason"] == "version_conflict"
    open_problem = make_problem(actor=actor)
    response = client.post(
        f"/api/workspaces/{actor.workspace_id}/problems/{open_problem.pk}/fix-release/",
        {"expected_version": open_problem.version, "external_id": "1"},
        content_type="application/json",
    )
    assert response.status_code == 409 and response.json()["reason"] == "invalid_transition"
    assert not FixRelease.objects.filter(problem=open_problem).exists()


def test_demo_release_list_is_refused(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    actor = make_membership(workspace=make_workspace(is_demo=True))
    sign_in(client, actor)
    calls = make_provider(monkeypatch)
    response = client.get(f"/api/workspaces/{actor.workspace_id}/releases/")
    assert response.status_code == 400 and response.json()["reason"] == "demo_workspace"
    assert calls == []


def test_repository_change_during_release_read_aborts_link(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    actor, connection, problem = setup_fixed()
    sign_in(client, actor)
    calls = make_provider(
        monkeypatch,
        on_release=lambda: Connection.objects.filter(pk=connection.pk).update(repository_id="1000"),
    )
    response = client.post(
        f"/api/workspaces/{actor.workspace_id}/problems/{problem.pk}/fix-release/",
        {"expected_version": problem.version, "external_id": "1"},
        content_type="application/json",
    )
    assert (
        response.status_code == 503 and response.json()["reason"] == "release_provider_unavailable"
    )
    assert not FixRelease.objects.filter(problem=problem).exists()
    assert any(request.url.path.endswith("/releases/1") for request in calls)
