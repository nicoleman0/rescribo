"""Durable receipt recovery, routing and retry boundaries."""

import logging
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.utils import timezone

from integrations.github_app.webhooks import IssueEvent
from operations.models import InboundReceipt
from operations.tasks import dispatch_due_operations, process_inbound_receipt

pytestmark = pytest.mark.django_db


def test_dispatcher_reclaims_expired_running_receipt_and_routes_it() -> None:
    event = IssueEvent(
        action="closed",
        number=7,
        repository="acme/widgets",
        repository_id="999",
        issue_id="555",
        state_reason=None,
        updated_at=timezone.now().isoformat(),
    )
    receipt = InboundReceipt.objects.create(
        provider="github",
        delivery_id="crashed",
        event="issues",
        installation_id="42",
        normalized=event.as_dict(),
        status="running",
        lease_token=uuid4(),
        lease_expires_at=timezone.now() - timedelta(hours=1),
    )
    with patch("operations.tasks.process_inbound_receipt.delay") as dispatch:
        dispatch_due_operations()
    dispatch.assert_called_once_with(str(receipt.pk))
    with patch("operations.tasks.apply_issue_webhook") as apply_event:
        process_inbound_receipt(str(receipt.pk))
        process_inbound_receipt(str(receipt.pk))
    apply_event.assert_called_once_with(installation_id="42", event=event)
    receipt.refresh_from_db()
    assert receipt.status == "succeeded"
    assert receipt.lease_token is None


def test_active_lease_and_terminal_failure_are_not_reprocessed() -> None:
    receipt = InboundReceipt.objects.create(
        provider="github",
        delivery_id="active",
        event="issues",
        status="running",
        lease_token=uuid4(),
        lease_expires_at=timezone.now() + timedelta(minutes=10),
    )
    with patch("operations.tasks.process_inbound_receipt.delay") as dispatch:
        dispatch_due_operations()
    dispatch.assert_not_called()
    process_inbound_receipt(str(receipt.pk))
    receipt.refresh_from_db()
    assert receipt.attempts == 0
    receipt.status = "failed"
    receipt.save()
    process_inbound_receipt(str(receipt.pk))
    receipt.refresh_from_db()
    assert receipt.attempts == 0


def test_failed_receipt_logs_the_exception_type(caplog: pytest.LogCaptureFixture) -> None:
    receipt = InboundReceipt.objects.create(
        provider="github",
        delivery_id="boom",
        event="issues",
        installation_id="42",
        normalized={"unexpected": "shape"},
    )
    with caplog.at_level(logging.WARNING, logger="operations.tasks"):
        process_inbound_receipt(str(receipt.pk))
    assert "Inbound GitHub receipt processing failed: TypeError" in caplog.text
