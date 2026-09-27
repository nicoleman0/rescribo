"""HTTP tests for the shared GitHub webhook route: signature, dedupe, and dispatch."""

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client, override_settings

from connections.models import GitHubWebhookReceipt

pytestmark = pytest.mark.django_db

WEBHOOK_URL = "/api/integrations/github/webhook/"
SECRET = "wh-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"


def post_webhook(
    client: Client,
    payload: dict[str, Any],
    *,
    event: str = "issues",
    delivery: str = "d-1",
    secret: str = SECRET,
    signed_body: bytes | None = None,
) -> Any:
    body = json.dumps(payload).encode()
    return client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=sign(signed_body if signed_body is not None else body, secret),
        HTTP_X_GITHUB_EVENT=event,
        HTTP_X_GITHUB_DELIVERY=delivery,
    )


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_valid_delivery_is_accepted_and_enqueued(client: Client) -> None:
    payload = {"action": "closed", "installation": {"id": 42}}
    with patch("connections.views.process_github_delivery") as task:
        response = post_webhook(client, payload)

    assert response.status_code == 202
    task.delay.assert_called_once_with(event_name="issues", payload=payload)
    assert GitHubWebhookReceipt.objects.filter(delivery_id="d-1").exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_bad_signature_is_rejected_before_any_processing(client: Client) -> None:
    payload = {"action": "closed", "installation": {"id": 42}}
    with patch("connections.views.process_github_delivery") as task:
        response = post_webhook(client, payload, secret="wrong-secret")

    assert response.status_code == 401
    task.delay.assert_not_called()
    assert not GitHubWebhookReceipt.objects.exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_duplicate_delivery_id_is_not_reprocessed(client: Client) -> None:
    payload = {"action": "closed", "installation": {"id": 42}}
    with patch("connections.views.process_github_delivery") as task:
        first = post_webhook(client, payload, delivery="d-dup")
        second = post_webhook(client, payload, delivery="d-dup")

    assert first.status_code == second.status_code == 202
    assert task.delay.call_count == 1
    assert GitHubWebhookReceipt.objects.filter(delivery_id="d-dup").count() == 1


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET="")
def test_missing_operator_secret_fails_closed(client: Client) -> None:
    payload = {"action": "closed", "installation": {"id": 42}}
    with patch("connections.views.process_github_delivery") as task:
        response = post_webhook(client, payload, secret="whatever")

    assert response.status_code >= 400
    task.delay.assert_not_called()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_missing_delivery_id_is_rejected(client: Client) -> None:
    body = json.dumps({"action": "closed"}).encode()
    response = client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=sign(body),
        HTTP_X_GITHUB_EVENT="issues",
    )

    assert response.status_code == 400
