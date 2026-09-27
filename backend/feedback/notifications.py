"""Invalidation and validity rules for prepared report notifications.

Lock order: the report row first, then its notification rows ordered by (created_at, id).
Any future sender must take locks in the same order.
"""

from datetime import datetime

from django.db import transaction

from feedback.models import Report, ReportNotificationOperation

Operation = ReportNotificationOperation
State = Operation.State
PENDING_STATES = (State.DRAFT, State.QUEUED, State.FAILED)
SENDABLE_STATES = (State.DRAFT, State.QUEUED)


def invalidate_pending_notifications(*, report: Report, reason: str, now: datetime) -> int:
    """Cancel unsent notifications for a report locked by the caller's transaction.

    Sent rows are left exactly as they are. Uncertain rows keep their state and gain an
    invalidation so they cannot be sent again without reconciliation. Returns the number of
    rows changed; repeating the call changes nothing.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Invalidate notifications inside the report mutation transaction.")
    if reason not in Operation.InvalidationReason.values:
        raise ValueError(f"Unknown invalidation reason: {reason}")
    rows = list(
        Operation.objects.select_for_update()
        .filter(workspace_id=report.workspace_id, report_id=report.pk)
        .order_by("created_at", "id")
        .values_list("id", "state", "invalidated_at")
    )
    pending = [pk for pk, state, _ in rows if state in PENDING_STATES]
    uncertain = [
        pk for pk, state, invalidated in rows if state == State.UNCERTAIN and invalidated is None
    ]
    changes = {"invalidated_at": now, "invalidation_reason": reason, "updated_at": now}
    cancelled = Operation.objects.filter(pk__in=pending).update(state=State.CANCELLED, **changes)
    flagged = Operation.objects.filter(pk__in=uncertain).update(**changes)
    return cancelled + flagged


def stale_reason(*, operation: ReportNotificationOperation, report: Report) -> str | None:
    """Return why a prepared notification may not be sent now, or None when it still may.

    Senders call this with freshly locked rows immediately before the external write.
    """
    if operation.workspace_id != report.workspace_id or operation.report_id != report.pk:
        return "wrong_report"
    if operation.invalidated_at is not None or operation.state not in SENDABLE_STATES:
        return "not_sendable"
    if operation.report_version != report.version:
        return "report_changed"
    if report.problem is None or operation.problem_id != report.problem_id:
        return "problem_changed"
    if operation.resolution_revision != report.problem.resolution_revision:
        return "resolution_changed"
    if not operation.recipient.is_active:
        return "recipient_inactive"
    return None
