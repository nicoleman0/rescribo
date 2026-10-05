"""Receipt payload retention. The row stays so redeliveries remain duplicates."""

from datetime import timedelta

from django.utils import timezone

from operations.models import InboundReceipt

RECEIPT_PAYLOAD_RETENTION = timedelta(days=7)


def purge_receipt_payloads() -> int:
    """Clear webhook-derived fields on old succeeded receipts; return rows changed."""
    return InboundReceipt.objects.filter(
        status=InboundReceipt.Status.SUCCEEDED,
        received_at__lt=timezone.now() - RECEIPT_PAYLOAD_RETENTION,
    ).update(normalized={}, action="", installation_id="", repository_id="", issue_id="")
