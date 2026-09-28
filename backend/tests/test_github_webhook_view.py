"""HTTP tests for signed GitHub receipt persistence and dispatch."""

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client, TestCase, override_settings

from connections.models import GitHubWebhookReceipt
from operations.models import InboundReceipt

pytestmark = pytest.mark.django_db

WEBHOOK_URL = "/api/integrations/github/webhook/"
SECRET = "wh-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"


def tracked_payload() -> dict[str, Any]:
    return {
        "action": "closed",
        "installation": {"id": 42},
        "issue": {
            "id": 555,
            "number": 7,
            "state_reason": "completed",
            "updated_at": "2026-09-20T21:00:00Z",
        },
        "repository": {"id": 999, "full_name": "acme/widgets"},
        "sender": {"login": "must-not-be-stored"},
    }


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
def test_valid_delivery_persists_only_normalized_fields_then_dispatches(client: Client) -> None:
    with (
        patch("connections.views.process_inbound_receipt.delay") as task,
        TestCase.captureOnCommitCallbacks(execute=True),
    ):
        response = post_webhook(client, tracked_payload())

    assert response.status_code == 202
    task.assert_called_once()
    receipt = InboundReceipt.objects.get(provider="github", delivery_id="d-1")
    assert receipt.normalized["issue_id"] == "555"
    assert receipt.normalized["repository_id"] == "999"
    assert "sender" not in receipt.normalized
    assert GitHubWebhookReceipt.objects.filter(delivery_id="d-1").exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_bad_signature_is_rejected_before_storage_or_processing(client: Client) -> None:
    with (
        patch("connections.views.process_inbound_receipt.delay") as task,
        TestCase.captureOnCommitCallbacks(execute=True),
    ):
        response = post_webhook(client, tracked_payload(), secret="wrong-secret")

    assert response.status_code == 401
    task.assert_not_called()
    assert not InboundReceipt.objects.exists()
    assert not GitHubWebhookReceipt.objects.exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_duplicate_delivery_id_does_not_create_or_dispatch_twice(client: Client) -> None:
    with (
        patch("connections.views.process_inbound_receipt.delay") as task,
        TestCase.captureOnCommitCallbacks(execute=True),
    ):
        first = post_webhook(client, tracked_payload(), delivery="d-dup")
        second = post_webhook(client, tracked_payload(), delivery="d-dup")

    assert first.status_code == second.status_code == 202
    assert task.call_count == 1
    assert InboundReceipt.objects.filter(delivery_id="d-dup").count() == 1


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET="")
def test_missing_operator_secret_fails_closed(client: Client) -> None:
    with patch("connections.views.process_inbound_receipt.delay") as task:
        response = post_webhook(client, tracked_payload())

    assert response.status_code >= 400
    task.assert_not_called()
    assert not InboundReceipt.objects.exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_missing_delivery_id_is_rejected(client: Client) -> None:
    body = json.dumps(tracked_payload()).encode()
    response = client.post(
        WEBHOOK_URL,
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=sign(body),
        HTTP_X_GITHUB_EVENT="issues",
    )
    assert response.status_code == 400
    assert not InboundReceipt.objects.exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_malformed_tracked_event_is_rejected_and_irrelevant_event_is_ignored(
    client: Client,
) -> None:
    malformed = tracked_payload()
    malformed["issue"]["id"] = True
    assert post_webhook(client, malformed).status_code == 400
    assert not InboundReceipt.objects.exists()
    assert post_webhook(client, tracked_payload(), event="ping").status_code == 204
    assert not InboundReceipt.objects.exists()


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_broker_failure_keeps_pending_receipt(client: Client) -> None:
    with patch("connections.views.process_inbound_receipt.delay", side_effect=RuntimeError):
        response = post_webhook(client, tracked_payload())

    assert response.status_code == 202
    assert InboundReceipt.objects.get(delivery_id="d-1").status == InboundReceipt.Status.PENDING
