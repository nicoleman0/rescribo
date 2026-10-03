"""Follow-up reads, employee-notification drafts, and customer outcomes.

Delivery ordering follows notifications.py: the report row locks first, then the
follow-up's notification rows. Nothing here resends an ambiguous write.
"""

from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.db import models, transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from accounts.models import Membership
from connections.models import Connection, ExternalIdentity
from feedback.errors import (
    ConfirmationRequired,
    DeliveryNotReady,
    InvalidTransition,
    MessageRequired,
    NotFound,
    ReasonRequired,
    VersionConflict,
)
from feedback.models import Activity, FollowUp, Problem, Report, ReportSource
from feedback.models import ReportNotificationOperation as Operation
from feedback.notifications import (
    freshness_reason,
    invalidate_pending_notifications,
    report_delivery_blocker,
)
from feedback.services import finish_mutation, require_version, write_activity
from operations.dispatch import dispatch_task

SENT_OR_ACTIVE_STATES = (
    Operation.State.QUEUED,
    Operation.State.FAILED,
    Operation.State.UNCERTAIN,
    Operation.State.SENT,
)
PROBLEM_STATES = (Operation.State.FAILED, Operation.State.UNCERTAIN)
EDITS = (Operation.State.DRAFT, Operation.State.FAILED)
BUCKETS = (
    "needs_approval",
    "delivery_problem",
    "awaiting_contact",
    "awaiting_confirmation",
    "completed",
)

CONTACTED_FROM_PENDING = (
    FollowUp.ContactState.CONTACTED,
    FollowUp.ContactState.STILL_AFFECTED,
    FollowUp.ContactState.NO_RESPONSE,
)
CONTACTED_FROM_CONTACTED = (
    FollowUp.ContactState.CONFIRMED,
    FollowUp.ContactState.STILL_AFFECTED,
    FollowUp.ContactState.NO_RESPONSE,
)
RECORDABLE_STATES = {
    FollowUp.ContactState.PENDING: CONTACTED_FROM_PENDING,
    FollowUp.ContactState.CONTACTED: CONTACTED_FROM_CONTACTED,
}


def recipient_for_report(report: Report) -> Membership:
    """The employee customer contact lands with: the assignee for manual reports."""
    if report.source.kind == ReportSource.Kind.MANUAL and report.assignee is not None:
        return report.assignee
    return report.submitted_by


def _allowed_outcome_states(*, from_state: str) -> tuple[str, ...]:
    return RECORDABLE_STATES.get(FollowUp.ContactState(from_state), ())


def _can_record_outcome(*, actor: Membership, report: Report) -> bool:
    """The assigned member, the original submitter, or any owner may record an outcome."""
    if actor.role == Membership.Role.OWNER:
        return True
    if report.assignee_id == actor.pk:
        return True
    if report.submitted_by_id == actor.pk:
        return True
    return False


def _has_operation(states: tuple[str, ...]) -> Exists:
    return Exists(
        Operation.objects.filter(
            workspace_id=OuterRef("workspace_id"),
            follow_up=OuterRef("pk"),
            state__in=states,
        )
    )


def workspace_follow_ups(*, actor: Membership) -> QuerySet[FollowUp]:
    """Rows the member may read, with their one non-cancelled notification if any."""
    # The workspace filter is applied before any bucket condition.
    return (
        FollowUp.objects.filter(workspace_id=actor.workspace_id)
        .select_related("report", "problem", "recipient__user")
        .annotate(
            active_notification_state=_active_notification_state(),
        )
    )


def _active_notification_state() -> models.Subquery:
    return models.Subquery(
        Operation.objects.filter(workspace_id=OuterRef("workspace_id"), follow_up=OuterRef("pk"))
        .exclude(state=Operation.State.CANCELLED)
        .values("state")[:1]
    )


def search_follow_ups(*, actor: Membership, bucket: str) -> QuerySet[FollowUp]:
    follow_ups = workspace_follow_ups(actor=actor)
    if bucket == "needs_approval":
        pending = _has_operation(tuple(SENT_OR_ACTIVE_STATES))
        return follow_ups.filter(models.Q(contact_state=FollowUp.ContactState.PENDING) & ~pending)
    if bucket == "delivery_problem":
        return follow_ups.filter(_has_operation(PROBLEM_STATES))
    if bucket == "awaiting_contact":
        return follow_ups.filter(
            models.Q(contact_state=FollowUp.ContactState.PENDING)
            & _has_operation((Operation.State.SENT,))
        )
    if bucket == "awaiting_confirmation":
        return follow_ups.filter(contact_state=FollowUp.ContactState.CONTACTED)
    if bucket == "completed":
        return follow_ups.filter(
            contact_state__in=[
                FollowUp.ContactState.CONFIRMED,
                FollowUp.ContactState.STILL_AFFECTED,
                FollowUp.ContactState.NO_RESPONSE,
            ]
        )
    raise ValueError(f"Unknown follow-up bucket: {bucket}")


def get_follow_up(*, actor: Membership, follow_up_id: UUID) -> FollowUp:
    try:
        return workspace_follow_ups(actor=actor).get(pk=follow_up_id)
    except FollowUp.DoesNotExist as error:
        raise NotFound(record="follow_up") from error


def follow_up_history(*, workspace_id: UUID, follow_up: FollowUp) -> QuerySet[Activity]:
    return (
        Activity.objects.filter(
            workspace_id=workspace_id,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
        )
        .select_related("actor_membership__user")
        .order_by("-created_at", "-id")
    )


def locked_follow_up_and_report(
    *, actor: Membership, follow_up_id: UUID
) -> tuple[FollowUp, Report]:
    """Lock the report before its follow-up and notification rows."""
    hint = (
        FollowUp.objects.filter(workspace_id=actor.workspace_id, pk=follow_up_id)
        .values("report_id")
        .first()
    )
    if hint is None:
        raise NotFound(record="follow_up")
    report = (
        Report.objects.select_related("problem")
        .select_for_update(of=("self",))
        .filter(workspace_id=actor.workspace_id, pk=hint["report_id"])
        .first()
    )
    if report is None:
        raise NotFound(record="report")
    follow_up = (
        FollowUp.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, pk=follow_up_id, report_id=report.pk)
        .first()
    )
    if follow_up is None:
        raise NotFound(record="follow_up")
    return follow_up, report


def report_link(report_id: UUID) -> str:
    return f"{settings.RESCRIBO_PUBLIC_BASE_URL}/inbox/{report_id}"


def _locked_outcome_rows(*, actor: Membership, follow_up_id: UUID) -> tuple[FollowUp, Report]:
    snapshot = (
        FollowUp.objects.filter(workspace_id=actor.workspace_id, pk=follow_up_id)
        .values("report__problem_id", "report__version")
        .first()
    )
    if snapshot is None:
        raise NotFound(record="follow_up")
    # Fix confirmation and issue reopening also lock the problem before its reports.
    if snapshot["report__problem_id"] is not None:
        problem = (
            Problem.objects.select_for_update()
            .filter(workspace_id=actor.workspace_id, pk=snapshot["report__problem_id"])
            .first()
        )
        if problem is None:
            raise VersionConflict(current=get_follow_up(actor=actor, follow_up_id=follow_up_id))
    follow_up, report = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
    require_version(row=report, expected_version=snapshot["report__version"])
    return follow_up, report


def default_message(*, report: Report) -> str:
    """Report title, the approved fix note, the fix version, and a link to the report.

    Nothing from other customers' reports or the GitHub issue is ever included.
    """
    problem = report.problem
    if problem is None:
        raise AssertionError("A follow-up's report must reference a problem.")
    available = f'The fix for "{report.title}" is available.'
    if problem.fix_version.strip():
        available = f'The fix for "{report.title}" is available ({problem.fix_version.strip()}).'
    parts = [available]
    if problem.fix_note.strip():
        parts.append(problem.fix_note.strip())
    parts.append(f"Track it in Rescribo: {report_link(report.pk)}")
    return "\n\n".join(parts)


def current_notification(follow_up: FollowUp, *, lock: bool = False) -> Operation | None:
    rows = getattr(follow_up, "notifications", None)
    if isinstance(rows, list) and not lock:
        return rows[0] if rows else None
    query = Operation.objects.filter(
        workspace_id=follow_up.workspace_id, follow_up=follow_up
    ).exclude(state=Operation.State.CANCELLED)
    if lock:
        query = query.select_for_update()
    return query.first()


def _require_notification_identity(
    *, operation: Operation, notification_id: UUID, draft_version: int
) -> None:
    if operation.pk != notification_id or operation.draft_version != draft_version:
        raise VersionConflict(current=operation)


def _require_send_reconciled(operation: Operation) -> None:
    if operation.lease_token is not None:
        raise DeliveryNotReady(
            reason="send_in_progress",
            detail=(
                "The worker is still resolving this send. Wait for reconciliation before acting."
            ),
        )


def has_slack_identity(follow_up: FollowUp) -> bool:
    return ExternalIdentity.objects.filter(
        workspace_id=follow_up.workspace_id,
        provider=Connection.Provider.SLACK,
        membership=follow_up.recipient,
    ).exists()


def slack_readiness(*, follow_up: FollowUp) -> tuple[Connection, ExternalIdentity]:
    """The active Slack connection and the recipient's identity, never a guessed one."""
    connection = (
        Connection.objects.select_for_update()
        .filter(workspace_id=follow_up.workspace_id, provider=Connection.Provider.SLACK)
        .first()
    )
    identity = (
        ExternalIdentity.objects.select_for_update()
        .filter(
            workspace_id=follow_up.workspace_id,
            provider=Connection.Provider.SLACK,
            membership=follow_up.recipient,
        )
        .first()
    )
    if connection is None or connection.status != Connection.Status.ACTIVE:
        raise DeliveryNotReady(
            reason="slack_connection_inactive",
            detail="Connect an active Slack workspace before sending.",
        )
    if identity is None:
        raise DeliveryNotReady(
            reason="no_slack_identity",
            detail="This member has not linked a Slack account. Offer copy to clipboard instead.",
        )
    if identity.provider_team_id and identity.provider_team_id != connection.external_id:
        raise DeliveryNotReady(
            reason="no_slack_identity",
            detail="This member's Slack account is not in the connected workspace.",
        )
    return connection, identity


def draft_notification(
    *, actor: Membership, follow_up_id: UUID, now: datetime | None = None
) -> Operation:
    """Create the exact-content draft once; the row is later edited, never replaced."""
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, report = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        blocker = report_delivery_blocker(
            report=report,
            problem_id=follow_up.problem_id,
            resolution_revision=follow_up.resolution_revision,
        )
        if blocker is not None:
            raise DeliveryNotReady(
                reason=blocker,
                detail="Confirm the fix and link this report before preparing a message.",
            )
        operation = current_notification(follow_up, lock=True)
        if operation is not None:
            return operation
        return Operation.objects.create(
            workspace_id=follow_up.workspace_id,
            report=report,
            problem=follow_up.problem,
            follow_up=follow_up,
            recipient=follow_up.recipient,
            resolution_revision=follow_up.resolution_revision,
            report_version=report.version,
            message=default_message(report=report),
            created_at=current,
            updated_at=current,
        )


def edit_notification(
    *,
    actor: Membership,
    follow_up_id: UUID,
    message: str,
    notification_id: UUID,
    draft_version: int,
    now: datetime | None = None,
) -> Operation:
    """Replace the unsent draft content. Conflicting edits return the current row."""
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, _ = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        operation = current_notification(follow_up, lock=True)
        if operation is None:
            raise NotFound(record="notification")
        if operation.state not in EDITS:
            raise InvalidTransition(action="edit_notification", from_state=operation.state)
        _require_notification_identity(
            operation=operation, notification_id=notification_id, draft_version=draft_version
        )
        clean_message = message.strip()
        if not clean_message:
            raise MessageRequired()
        operation.message = clean_message
        operation.draft_version += 1
        operation.updated_at = current
        operation.save(update_fields=["message", "draft_version", "updated_at"])
        return operation


def approve_notification(
    *,
    actor: Membership,
    follow_up_id: UUID,
    notification_id: UUID,
    draft_version: int,
    now: datetime | None = None,
) -> Operation:
    """Approve the exact content for delivery and queue one send. Never automatic.

    A retry of a failed draft is a fresh approval through the same use case.
    """
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, report = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        operation = current_notification(follow_up, lock=True)
        if operation is None:
            raise NotFound(record="notification")
        if operation.state not in EDITS:
            raise InvalidTransition(action="approve_notification", from_state=operation.state)
        _require_notification_identity(
            operation=operation, notification_id=notification_id, draft_version=draft_version
        )
        if operation.invalidated_at is not None:
            raise DeliveryNotReady(
                reason="approval_stale",
                detail="The report changed since the draft. Review the message before approving.",
            )
        blocker = freshness_reason(operation=operation, report=report)
        if blocker is not None:
            raise DeliveryNotReady(
                reason=blocker,
                detail="The report changed since the draft. Review the message before approving.",
            )
        # Fresh readiness immediately before queuing: same rules the task rechecks.
        slack_readiness(follow_up=follow_up)
        if not Membership.objects.filter(
            pk=follow_up.recipient_id, workspace_id=follow_up.workspace_id, is_active=True
        ).exists():
            raise DeliveryNotReady(
                reason="recipient_inactive",
                detail="Reassign this follow-up to an active member before sending.",
            )
        operation.state = Operation.State.QUEUED
        operation.approved_by = actor
        operation.approved_at = current
        operation.due_at = current
        operation.attempts = 0
        operation.safe_error = ""
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = current
        operation.save(
            update_fields=[
                "state",
                "approved_by",
                "approved_at",
                "due_at",
                "attempts",
                "safe_error",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        write_activity(
            actor=actor,
            action=Activity.Action.NOTIFICATION_APPROVED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={"draft_version": operation.draft_version},
            now=current,
        )
        operation_id = operation.pk
        transaction.on_commit(
            lambda: dispatch_task(
                "connections.tasks.send_follow_up_notification", str(operation_id)
            )
        )
    return operation


def mark_notification_delivered(
    *,
    actor: Membership,
    follow_up_id: UUID,
    notification_id: UUID,
    draft_version: int,
    now: datetime | None = None,
) -> Operation:
    """Resolve an uncertain delivery after a member saw the message in Slack."""
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, _ = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        operation = current_notification(follow_up, lock=True)
        if operation is None:
            raise NotFound(record="notification")
        _require_notification_identity(
            operation=operation, notification_id=notification_id, draft_version=draft_version
        )
        _require_send_reconciled(operation)
        if operation.state != Operation.State.UNCERTAIN:
            raise InvalidTransition(action="mark_delivered", from_state=operation.state)
        operation.state = Operation.State.SENT
        operation.sent_at = current
        operation.delivery_confirmed_by = actor
        operation.delivery_confirmed_at = current
        operation.safe_error = ""
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = current
        operation.save(
            update_fields=[
                "state",
                "sent_at",
                "delivery_confirmed_by",
                "delivery_confirmed_at",
                "safe_error",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        write_activity(
            actor=actor,
            action=Activity.Action.NOTIFICATION_SENT,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={"manual_delivery_confirmation": True},
            now=current,
        )
        return operation


def send_notification_again(
    *,
    actor: Membership,
    follow_up_id: UUID,
    notification_id: UUID,
    draft_version: int,
    checked_slack: bool,
    now: datetime | None = None,
) -> Operation:
    """Queue an uncertain send only after an explicit human duplicate check."""
    if not checked_slack:
        raise ConfirmationRequired()
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, report = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        operation = current_notification(follow_up, lock=True)
        if operation is None:
            raise NotFound(record="notification")
        if operation.state != Operation.State.UNCERTAIN:
            raise InvalidTransition(action="send_again", from_state=operation.state)
        _require_notification_identity(
            operation=operation, notification_id=notification_id, draft_version=draft_version
        )
        _require_send_reconciled(operation)
        if operation.invalidated_at is not None:
            raise DeliveryNotReady(
                reason="approval_stale",
                detail="The report changed. Prepare and approve a new message before sending.",
            )
        blocker = freshness_reason(operation=operation, report=report)
        if blocker is not None:
            raise DeliveryNotReady(
                reason=blocker,
                detail="The report changed. Prepare and approve a new message before sending.",
            )
        if follow_up.recipient_id != operation.recipient_id:
            raise DeliveryNotReady(
                reason="recipient_changed",
                detail="The notification recipient changed. Review the new recipient before sending.",  # noqa: E501
            )
        slack_readiness(follow_up=follow_up)
        operation.state = Operation.State.QUEUED
        operation.approved_by = actor
        operation.approved_at = current
        operation.due_at = current
        operation.safe_error = ""
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = current
        operation.save(
            update_fields=[
                "state",
                "approved_by",
                "approved_at",
                "due_at",
                "safe_error",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        write_activity(
            actor=actor,
            action=Activity.Action.NOTIFICATION_APPROVED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={"draft_version": operation.draft_version, "checked_before_resend": True},
            now=current,
        )
        operation_id = operation.pk
        transaction.on_commit(
            lambda: dispatch_task(
                "connections.tasks.send_follow_up_notification", str(operation_id)
            )
        )
        return operation


def cancel_notification(
    *,
    actor: Membership,
    follow_up_id: UUID,
    notification_id: UUID,
    draft_version: int,
    now: datetime | None = None,
) -> Operation:
    """Cancel an unresolved send without changing the customer-contact outcome."""
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, _ = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        operation = current_notification(follow_up, lock=True)
        if operation is None:
            raise NotFound(record="notification")
        _require_notification_identity(
            operation=operation, notification_id=notification_id, draft_version=draft_version
        )
        _require_send_reconciled(operation)
        if operation.state != Operation.State.UNCERTAIN:
            raise InvalidTransition(action="cancel_notification", from_state=operation.state)
        operation.state = Operation.State.CANCELLED
        operation.invalidated_at = current
        operation.invalidation_reason = Operation.InvalidationReason.MEMBER_CANCELLED
        operation.safe_error = ""
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = current
        operation.save(
            update_fields=[
                "state",
                "invalidated_at",
                "invalidation_reason",
                "safe_error",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        write_activity(
            actor=actor,
            action=Activity.Action.NOTIFICATION_CANCELLED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            now=current,
        )
        return operation


# Customer outcomes


def record_outcome(
    *,
    actor: Membership,
    follow_up_id: UUID,
    state: str,
    note: str,
    expected_version: int,
    slack_team_id: str | None = None,
    slack_user_id: str | None = None,
    now: datetime | None = None,
) -> FollowUp:
    """Record a customer-contact outcome for one follow-up.

    Recording: the assigned member, the original submitter, or an owner.
    Delivery state and contact state are independent; this never changes the
    notification row.
    """
    current = now or timezone.now()
    clean_note = note.strip()
    if state == FollowUp.ContactState.NO_RESPONSE and not clean_note:
        raise MessageRequired()
    with transaction.atomic():
        follow_up, report = _locked_outcome_rows(actor=actor, follow_up_id=follow_up_id)
        require_version(row=follow_up, expected_version=expected_version)
        next_state = FollowUp.ContactState(state)
        allowed = _allowed_outcome_states(from_state=follow_up.contact_state)
        if next_state not in allowed:
            raise InvalidTransition(action="record_outcome", from_state=follow_up.contact_state)
        if slack_team_id is None:
            authorized = _can_record_outcome(actor=actor, report=report)
        else:
            identity = (
                ExternalIdentity.objects.select_for_update()
                .filter(
                    workspace_id=actor.workspace_id,
                    membership_id=actor.pk,
                    provider=Connection.Provider.SLACK,
                    provider_team_id=slack_team_id,
                    provider_user_id=slack_user_id,
                )
                .first()
            )
            connection = (
                Connection.objects.select_for_update()
                .filter(
                    workspace_id=actor.workspace_id,
                    provider=Connection.Provider.SLACK,
                    external_id=slack_team_id,
                    status=Connection.Status.ACTIVE,
                )
                .first()
            )
            authorized = bool(
                actor.is_active
                and follow_up.recipient_id == actor.pk
                and identity is not None
                and connection is not None
            )
        if not authorized:
            raise InvalidTransition(action="record_outcome", from_state=follow_up.contact_state)
        previous_state = follow_up.contact_state
        follow_up.contact_state = next_state
        follow_up.outcome_note = clean_note
        follow_up.outcome_at = current
        follow_up.outcome_by = actor
        follow_up.report_version = report.version
        update_fields = [
            "contact_state",
            "outcome_note",
            "outcome_at",
            "outcome_by",
            "report_version",
        ]
        finish_mutation(row=follow_up, now=current, update_fields=update_fields)
        if next_state == FollowUp.ContactState.STILL_AFFECTED and report.problem_id is not None:
            _flag_problem_needs_review(actor=actor, problem_id=report.problem_id, now=current)
        write_activity(
            actor=actor,
            action=Activity.Action.OUTCOME_RECORDED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={"from_state": previous_state, "to_state": next_state},
            now=current,
        )
        return follow_up


def correct_outcome(
    *,
    actor: Membership,
    follow_up_id: UUID,
    state: str,
    note: str,
    reason: str,
    expected_version: int,
    now: datetime | None = None,
) -> FollowUp:
    """Owner-only move of a recorded outcome to another state, with a required reason."""
    if actor.role != Membership.Role.OWNER:
        raise InvalidTransition(action="correct_outcome", from_state="")
    clean_reason = reason.strip()
    if not clean_reason:
        raise ReasonRequired()
    current = now or timezone.now()
    clean_note = note.strip()
    if state == FollowUp.ContactState.NO_RESPONSE and not clean_note:
        raise MessageRequired()
    with transaction.atomic():
        follow_up, report = _locked_outcome_rows(actor=actor, follow_up_id=follow_up_id)
        require_version(row=follow_up, expected_version=expected_version)
        if follow_up.contact_state == FollowUp.ContactState.PENDING:
            raise InvalidTransition(action="correct_outcome", from_state=follow_up.contact_state)
        next_state = FollowUp.ContactState(state)
        if next_state == follow_up.contact_state:
            raise InvalidTransition(action="correct_outcome", from_state=follow_up.contact_state)
        previous_state = follow_up.contact_state
        follow_up.contact_state = next_state
        follow_up.outcome_note = clean_note
        follow_up.outcome_at = current
        follow_up.outcome_by = actor
        follow_up.report_version = report.version
        update_fields = [
            "contact_state",
            "outcome_note",
            "outcome_at",
            "outcome_by",
            "report_version",
        ]
        finish_mutation(row=follow_up, now=current, update_fields=update_fields)
        if next_state == FollowUp.ContactState.STILL_AFFECTED and report.problem_id is not None:
            _flag_problem_needs_review(actor=actor, problem_id=report.problem_id, now=current)
        write_activity(
            actor=actor,
            action=Activity.Action.OUTCOME_CORRECTED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={
                "from_state": previous_state,
                "to_state": next_state,
                "reason": clean_reason,
            },
            now=current,
        )
        return follow_up


def _flag_problem_needs_review(*, actor: Membership, problem_id: UUID, now: datetime) -> None:
    problem = (
        Problem.objects.select_for_update(of=("self",))
        .filter(workspace_id=actor.workspace_id, pk=problem_id)
        .first()
    )
    if problem is None or problem.needs_review:
        return
    problem.needs_review = True
    finish_mutation(row=problem, now=now, update_fields=["needs_review"])
    write_activity(
        actor=actor,
        action=Activity.Action.PROBLEM_UPDATED,
        record_type=Activity.RecordType.PROBLEM,
        record_id=problem.pk,
        metadata={"fields": ["needs_review"], "reason": "still_affected_outcome"},
        now=now,
    )


# Recipient changes


def change_recipient(
    *,
    actor: Membership,
    follow_up_id: UUID,
    new_recipient_id: UUID,
    now: datetime | None = None,
) -> FollowUp:
    """Owner-only reassignment of the follow-up's intended employee recipient.

    Cancels the unsent notification with reason `reassigned` and records a
    `recipient_changed` activity. Delivery state never changes contact state.
    """
    if actor.role != Membership.Role.OWNER:
        raise InvalidTransition(action="change_recipient", from_state="")
    current = now or timezone.now()
    with transaction.atomic():
        follow_up, report = locked_follow_up_and_report(actor=actor, follow_up_id=follow_up_id)
        new_recipient = (
            Membership.objects.select_for_update()
            .filter(workspace_id=actor.workspace_id, pk=new_recipient_id, is_active=True)
            .first()
        )
        if new_recipient is None:
            raise NotFound(record="recipient")
        if not ExternalIdentity.objects.filter(
            workspace_id=actor.workspace_id,
            membership=new_recipient,
            provider=Connection.Provider.SLACK,
        ).exists():
            raise InvalidTransition(action="change_recipient", from_state="")
        if new_recipient.pk == follow_up.recipient_id:
            raise InvalidTransition(action="change_recipient", from_state="")
        previous_recipient_id = follow_up.recipient_id
        follow_up.recipient = new_recipient
        follow_up.report_version = report.version
        finish_mutation(
            row=follow_up,
            now=current,
            update_fields=["recipient", "report_version"],
        )
        if current_notification(follow_up, lock=True) is not None:
            invalidate_pending_notifications(
                report=report,
                reason=Operation.InvalidationReason.REASSIGNED,
                now=current,
            )
        write_activity(
            actor=actor,
            action=Activity.Action.RECIPIENT_CHANGED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={
                "from_recipient_id": str(previous_recipient_id),
                "to_recipient_id": str(new_recipient.pk),
            },
            now=current,
        )
        return follow_up
