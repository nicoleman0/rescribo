"""Invalidation and validity rules for prepared report notifications.

Lock order: report, follow-up, then notification. When locking multiple notification rows,
order them by (created_at, id).
"""

from datetime import datetime
from uuid import UUID

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
    inflight = list(
        Operation.objects.filter(
            pk__in=[pk for pk, state, _ in rows if state == State.QUEUED],
            lease_token__isnull=False,
        ).values_list("pk", flat=True)
    )
    pending = [pk for pk, state, _ in rows if state in PENDING_STATES and pk not in inflight]
    uncertain = [
        pk for pk, state, invalidated in rows if state == State.UNCERTAIN and invalidated is None
    ]
    changes = {"invalidated_at": now, "invalidation_reason": reason, "updated_at": now}
    cancelled = Operation.objects.filter(pk__in=pending).update(state=State.CANCELLED, **changes)
    preserved = Operation.objects.filter(pk__in=inflight).update(state=State.UNCERTAIN, **changes)
    flagged = Operation.objects.filter(pk__in=uncertain).update(**changes)
    return cancelled + preserved + flagged


def stale_reason(*, operation: ReportNotificationOperation, report: Report) -> str | None:
    """Return why a prepared notification may not be sent now, or None when it still may.

    Senders call this with freshly locked rows immediately before the external write.
    """
    if not_sendable := invalidation_or_state_reason(operation):
        return not_sendable
    return freshness_reason(operation=operation, report=report)


def invalidation_or_state_reason(operation: ReportNotificationOperation) -> str | None:
    if operation.invalidated_at is not None:
        return "invalidated"
    if operation.state not in SENDABLE_STATES:
        return "not_sendable"
    return None


def freshness_reason(*, operation: ReportNotificationOperation, report: Report) -> str | None:
    """Why the prepared content no longer matches the report, ignoring send state.

    Failed and uncertain rows are retried only after this returns None: revocation,
    reassignment, edits, and reopenings all invalidate the draft.
    """
    if operation.workspace_id != report.workspace_id or operation.report_id != report.pk:
        return "wrong_report"
    if operation.report_version != report.version:
        return "report_changed"
    if report.problem is None or operation.problem_id != report.problem_id:
        return "problem_changed"
    if reason := report_delivery_blocker(
        report=report,
        problem_id=operation.problem_id,
        resolution_revision=operation.resolution_revision,
    ):
        return reason
    if not operation.recipient.is_active:
        return "recipient_inactive"
    return None


def report_delivery_blocker(
    *, report: Report, problem_id: UUID, resolution_revision: int
) -> str | None:
    """One eligibility rule shared by preparation, approval, resend, and workers."""
    if report.problem_id is None or report.problem_id != problem_id:
        return "problem_changed"
    if report.triage_state != Report.TriageState.LINKED:
        return "report_not_linked"
    if report.problem is None:
        return "problem_changed"
    if report.problem.state != report.problem.State.FIX_AVAILABLE:
        return "fix_not_confirmed"
    if report.problem.resolution_revision < 1:
        return "fix_not_confirmed"
    if report.problem.resolution_revision != resolution_revision:
        return "resolution_changed"
    return None
