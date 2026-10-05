"""Receipt payload purge uses real PostgreSQL; only the Celery dispatch is mocked."""

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from operations.models import InboundReceipt
from operations.receipt_retention import RECEIPT_PAYLOAD_RETENTION, purge_receipt_payloads

pytestmark = pytest.mark.django_db

SECRET = "wh-secret"
PAYLOAD = {
    "action": "closed",
    "installation": {"id": 42},
    "issue": {
        "id": 555,
        "number": 7,
        "state_reason": "completed",
        "updated_at": "2026-09-20T21:00:00Z",
    },
    "repository": {"id": 999, "full_name": "acme/widgets"},
}


def make_receipt(status: str, age: timedelta, delivery_id: str = "d-1") -> InboundReceipt:
    return InboundReceipt.objects.create(
        provider="github",
        delivery_id=delivery_id,
        event="issues",
        action="closed",
        installation_id="42",
        repository_id="999",
        issue_id="555",
        normalized={"issue_id": "555"},
        status=status,
        received_at=timezone.now() - age,
    )


def is_cleared(receipt: InboundReceipt) -> bool:
    receipt.refresh_from_db()
    return (
        receipt.normalized == {}
        and receipt.action == receipt.installation_id == ""
        and receipt.repository_id == receipt.issue_id == ""
    )


OLD = RECEIPT_PAYLOAD_RETENTION + timedelta(hours=1)


def test_old_succeeded_receipt_is_cleared() -> None:
    receipt = make_receipt(InboundReceipt.Status.SUCCEEDED, OLD)
    assert purge_receipt_payloads() == 1
    assert is_cleared(receipt)
    assert (receipt.provider, receipt.delivery_id, receipt.event) == ("github", "d-1", "issues")


def test_recent_succeeded_receipt_is_untouched() -> None:
    receipt = make_receipt(InboundReceipt.Status.SUCCEEDED, RECEIPT_PAYLOAD_RETENTION / 2)
    assert purge_receipt_payloads() == 0
    assert not is_cleared(receipt)
    assert receipt.normalized == {"issue_id": "555"}


@pytest.mark.parametrize(
    "status",
    [InboundReceipt.Status.PENDING, InboundReceipt.Status.RUNNING, InboundReceipt.Status.FAILED],
)
def test_unfinished_receipts_keep_their_payload(status: str) -> None:
    receipt = make_receipt(status, OLD)
    assert purge_receipt_payloads() == 0
    assert not is_cleared(receipt)


def post_webhook(client: Client, delivery: str) -> Any:
    body = json.dumps(PAYLOAD).encode()
    return client.post(
        "/api/integrations/github/webhook/",
        data=body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256="
        + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest(),
        HTTP_X_GITHUB_EVENT="issues",
        HTTP_X_GITHUB_DELIVERY=delivery,
    )


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_redelivery_after_purge_is_still_a_duplicate(client: Client) -> None:
    with (
        patch("connections.views.process_inbound_receipt.delay") as task,
        TestCase.captureOnCommitCallbacks(execute=True),
    ):
        assert post_webhook(client, "d-purged").status_code == 202
        InboundReceipt.objects.update(
            status=InboundReceipt.Status.SUCCEEDED, received_at=timezone.now() - OLD
        )
        assert purge_receipt_payloads() == 1
        assert post_webhook(client, "d-purged").status_code == 202

    assert task.call_count == 1
    receipt = InboundReceipt.objects.get(delivery_id="d-purged")
    assert InboundReceipt.objects.count() == 1
    assert is_cleared(receipt)
