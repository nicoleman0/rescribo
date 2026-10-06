"""Slack follow-up delivery and signed outcome-action orchestration."""

import logging
import socket
from dataclasses import dataclass
from datetime import timedelta
from urllib.error import URLError
from uuid import UUID, uuid4

from django.db import transaction
from django.utils import timezone
from slack_sdk.errors import SlackApiError

from accounts.demo import is_demo_workspace
from accounts.models import Membership
from connections.models import Connection, ExternalIdentity
from connections.slack_inbound import active_connection, record_provider_failure
from feedback.models import Activity, FollowUp, Report
from feedback.models import ReportNotificationOperation as Operation
from feedback.notifications import stale_reason
from feedback.services import write_system_activity
from integrations.slack import client
from integrations.slack.errors import slack_error_code
from integrations.slack.messages import follow_up_message_blocks
from operations.dispatch import dispatch_task

logger = logging.getLogger(__name__)

LEASE_TTL = timedelta(seconds=60)


class SendBlocked(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SendContext:
    credential: str
    team_id: str
    slack_user_id: str
    follow_up_id: UUID
    message: str
    # Demo workspaces send through the fake client and never reach Slack.
    simulated: bool


@dataclass(frozen=True)
class SendHint:
    workspace_id: UUID
    report_id: UUID
    follow_up_id: UUID


def _hint(operation_id: UUID) -> SendHint | None:
    values = (
        Operation.objects.filter(pk=operation_id)
        .values("workspace_id", "report_id", "follow_up_id")
        .first()
    )
    if values is None:
        return None
    return SendHint(**values)


def _locked_rows(
    *, hint: SendHint, operation_id: UUID
) -> tuple[Report, FollowUp, Operation] | None:
    report = (
        Report.objects.select_related("problem")
        .select_for_update(of=("self",))
        .filter(workspace_id=hint.workspace_id, pk=hint.report_id)
        .first()
    )
    if report is None:
        return None
    follow_up = (
        FollowUp.objects.select_for_update()
        .filter(
            workspace_id=hint.workspace_id,
            pk=hint.follow_up_id,
            report_id=report.pk,
        )
        .first()
    )
    if follow_up is None:
        return None
    operation = (
        Operation.objects.select_for_update(of=("self",))
        .select_related("recipient")
        .filter(
            workspace_id=hint.workspace_id,
            report_id=report.pk,
            follow_up_id=follow_up.pk,
            pk=operation_id,
        )
        .first()
    )
    if operation is None:
        return None
    return report, follow_up, operation


def _claim(operation_id: UUID) -> tuple[SendHint, UUID] | None:
    hint = _hint(operation_id)
    if hint is None:
        return None
    now, token = timezone.now(), uuid4()
    with transaction.atomic():
        rows = _locked_rows(hint=hint, operation_id=operation_id)
        if rows is None:
            return None
        _, _, operation = rows
        if operation.state != Operation.State.QUEUED:
            return None
        if operation.due_at is not None and operation.due_at > now:
            return None
        if operation.lease_token is not None:
            if operation.lease_expires_at is not None and operation.lease_expires_at > now:
                return None
            operation.state = Operation.State.UNCERTAIN
            operation.safe_error = "worker_lease_expired"
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = now
            operation.save(
                update_fields=[
                    "state",
                    "safe_error",
                    "lease_token",
                    "lease_expires_at",
                    "updated_at",
                ]
            )
            return None
        operation.attempts += 1
        operation.lease_token = token
        operation.lease_expires_at = now + LEASE_TTL
        operation.updated_at = now
        operation.save(update_fields=["attempts", "lease_token", "lease_expires_at", "updated_at"])
    return hint, token


def _target(*, workspace_id: UUID, follow_up: FollowUp) -> tuple[Connection, str]:
    configured = Connection.objects.filter(
        workspace_id=workspace_id, provider=Connection.Provider.SLACK
    ).first()
    if (
        configured is None
        or configured.status != Connection.Status.ACTIVE
        or not configured.external_id
    ):
        raise SendBlocked("slack_connection_inactive")
    connection = active_connection(configured.external_id)
    if (
        connection is None
        or connection.workspace_id != workspace_id
        or connection.pk != configured.pk
    ):
        raise SendBlocked("slack_connection_inactive")
    identity = ExternalIdentity.objects.filter(
        workspace_id=workspace_id,
        membership_id=follow_up.recipient_id,
        provider=Connection.Provider.SLACK,
        provider_team_id=connection.external_id,
    ).first()
    if identity is None or not identity.provider_user_id:
        raise SendBlocked("recipient_unlinked")
    if not Membership.objects.filter(
        workspace_id=workspace_id, pk=follow_up.recipient_id, is_active=True
    ).exists():
        raise SendBlocked("recipient_inactive")
    return connection, identity.provider_user_id


def _authorize(*, hint: SendHint, operation_id: UUID, token: UUID) -> SendContext:
    with transaction.atomic():
        rows = _locked_rows(hint=hint, operation_id=operation_id)
        if rows is None:
            raise SendBlocked("operation_missing")
        report, follow_up, operation = rows
        if (
            operation.state != Operation.State.QUEUED
            or operation.lease_token != token
            or operation.invalidated_at is not None
        ):
            raise SendBlocked("operation_not_sendable")
        if follow_up.recipient_id != operation.recipient_id:
            raise SendBlocked("recipient_changed")
        if not Membership.objects.filter(
            workspace_id=hint.workspace_id, pk=follow_up.recipient_id, is_active=True
        ).exists():
            raise SendBlocked("recipient_inactive")
        blocker = stale_reason(operation=operation, report=report)
        if blocker is not None:
            _cancel_stale(operation=operation, reason=blocker)
        else:
            connection, user_id = _target(workspace_id=hint.workspace_id, follow_up=follow_up)
            context = SendContext(
                credential=connection.credential,
                team_id=connection.external_id,
                slack_user_id=user_id,
                follow_up_id=follow_up.pk,
                message=operation.message,
                simulated=is_demo_workspace(hint.workspace_id),
            )
    if blocker is not None:
        raise SendBlocked("approval_stale")
    return context


def _cancel_stale(*, operation: Operation, reason: str) -> None:
    now = timezone.now()
    operation.state = Operation.State.CANCELLED
    operation.invalidated_at = now
    operation.invalidation_reason = Operation.InvalidationReason.STALE
    operation.safe_error = reason[:200]
    operation.lease_token = None
    operation.lease_expires_at = None
    operation.updated_at = now
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


def _mark_failure(
    *, hint: SendHint, operation_id: UUID, token: UUID, code: str, uncertain: bool
) -> None:
    now = timezone.now()
    with transaction.atomic():
        rows = _locked_rows(hint=hint, operation_id=operation_id)
        if rows is None:
            return
        _, _, operation = rows
        owns_lease = operation.lease_token == token
        if operation.state == Operation.State.QUEUED and owns_lease:
            operation.state = Operation.State.UNCERTAIN if uncertain else Operation.State.FAILED
        elif (
            operation.state == Operation.State.UNCERTAIN and owns_lease and operation.invalidated_at
        ):
            operation.state = Operation.State.UNCERTAIN if uncertain else Operation.State.CANCELLED
        elif (
            operation.state == Operation.State.CANCELLED
            and owns_lease
            and uncertain
            and operation.invalidated_at is not None
        ):
            operation.state = Operation.State.UNCERTAIN
        elif operation.state == Operation.State.CANCELLED and owns_lease:
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = now
            operation.save(update_fields=["lease_token", "lease_expires_at", "updated_at"])
            return
        else:
            return
        operation.safe_error = code[:200]
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.updated_at = now
        operation.save(
            update_fields=[
                "state",
                "safe_error",
                "lease_token",
                "lease_expires_at",
                "updated_at",
            ]
        )
        if operation.state == Operation.State.FAILED:
            write_system_activity(
                workspace_id=hint.workspace_id,
                actor_system="slack_delivery",
                action=Activity.Action.NOTIFICATION_FAILED,
                record_type=Activity.RecordType.FOLLOW_UP,
                record_id=hint.follow_up_id,
                metadata={"safe_error": code[:200]},
                now=now,
            )


def _save_conversation(
    *, hint: SendHint, operation_id: UUID, token: UUID, conversation_id: str
) -> bool:
    with transaction.atomic():
        rows = _locked_rows(hint=hint, operation_id=operation_id)
        if rows is None:
            return False
        _, _, operation = rows
        if (
            operation.state == Operation.State.UNCERTAIN
            and operation.lease_token == token
            and operation.invalidated_at
        ):
            operation.state = Operation.State.CANCELLED
            operation.remote_conversation_id = conversation_id
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = timezone.now()
            operation.save(
                update_fields=[
                    "state",
                    "remote_conversation_id",
                    "lease_token",
                    "lease_expires_at",
                    "updated_at",
                ]
            )
            return False
        if operation.state == Operation.State.CANCELLED and operation.lease_token == token:
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = timezone.now()
            operation.save(update_fields=["lease_token", "lease_expires_at", "updated_at"])
            return False
        if operation.state != Operation.State.QUEUED or operation.lease_token != token:
            return False
        operation.remote_conversation_id = conversation_id
        operation.save(update_fields=["remote_conversation_id"])
        return True


def _post_result(
    *,
    hint: SendHint,
    operation_id: UUID,
    token: UUID,
    conversation_id: str,
    message_ts: str,
) -> None:
    now = timezone.now()
    with transaction.atomic():
        rows = _locked_rows(hint=hint, operation_id=operation_id)
        if rows is None:
            return
        _, _, operation = rows
        if operation.state == Operation.State.QUEUED and operation.lease_token == token:
            operation.state = Operation.State.SENT
            operation.sent_at = now
            operation.remote_conversation_id = conversation_id
            operation.remote_message_id = message_ts
            operation.safe_error = ""
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = now
            operation.save(
                update_fields=[
                    "state",
                    "sent_at",
                    "remote_conversation_id",
                    "remote_message_id",
                    "safe_error",
                    "lease_token",
                    "lease_expires_at",
                    "updated_at",
                ]
            )
            write_system_activity(
                workspace_id=hint.workspace_id,
                actor_system="slack_delivery",
                action=Activity.Action.NOTIFICATION_SENT,
                record_type=Activity.RecordType.FOLLOW_UP,
                record_id=hint.follow_up_id,
                now=now,
            )
        elif (
            operation.state in (Operation.State.CANCELLED, Operation.State.UNCERTAIN)
            and operation.lease_token == token
            and operation.invalidated_at is not None
        ):
            # A triage edit raced the Slack POST; preserve the possible delivery for review.
            operation.state = Operation.State.UNCERTAIN
            operation.remote_conversation_id = conversation_id
            operation.remote_message_id = message_ts
            operation.safe_error = "report_changed_during_send"
            operation.lease_token = None
            operation.lease_expires_at = None
            operation.updated_at = now
            operation.save(
                update_fields=[
                    "state",
                    "remote_conversation_id",
                    "remote_message_id",
                    "safe_error",
                    "lease_token",
                    "lease_expires_at",
                    "updated_at",
                ]
            )


def _uncertain_post(error: Exception) -> bool:
    if isinstance(error, SlackApiError):
        status = getattr(error.response, "status_code", 0)
        return isinstance(status, int) and status >= 500
    if isinstance(error, (TimeoutError, socket.timeout, ConnectionError)):
        return True
    if isinstance(error, URLError):
        return isinstance(error.reason, (TimeoutError, socket.timeout, ConnectionError, OSError))
    return isinstance(error, OSError)


def _record_revocation(context: SendContext, error: Exception) -> None:
    connection = active_connection(context.team_id)
    if connection is not None:
        record_provider_failure(connection, error)


def send_follow_up_notification(operation_id: UUID) -> None:
    """Lease one queued row, revalidate around each Slack write, and never resend."""
    claim = _claim(operation_id)
    if claim is None:
        return
    hint, token = claim
    try:
        context = _authorize(hint=hint, operation_id=operation_id, token=token)
    except SendBlocked as blocked:
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code=blocked.code,
            uncertain=False,
        )
        return
    try:
        opened = client.conversations_open(
            context.credential, users=context.slack_user_id, simulated=context.simulated
        )
    except Exception as error:
        _record_revocation(context, error)
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code=slack_error_code(error) or "provider_unavailable",
            uncertain=False,
        )
        logger.warning("Slack conversations.open failed")
        return
    conversation = opened.get("channel")
    conversation_id = conversation.get("id") if isinstance(conversation, dict) else None
    if not isinstance(conversation_id, str) or not conversation_id:
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code="conversation_id_missing",
            uncertain=False,
        )
        return
    if not _save_conversation(
        hint=hint,
        operation_id=operation_id,
        token=token,
        conversation_id=conversation_id,
    ):
        return
    try:
        context = _authorize(hint=hint, operation_id=operation_id, token=token)
    except SendBlocked as blocked:
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code=blocked.code,
            uncertain=False,
        )
        return
    blocks = follow_up_message_blocks(
        message=context.message, follow_up_id=str(context.follow_up_id)
    )
    try:
        posted = client.chat_post_message(
            context.credential,
            channel=conversation_id,
            text=context.message,
            blocks=blocks,
            simulated=context.simulated,
        )
    except Exception as error:
        _record_revocation(context, error)
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code=slack_error_code(error) or "write_outcome_unknown",
            uncertain=_uncertain_post(error),
        )
        logger.warning("Slack chat.postMessage failed")
        return
    message_ts = posted.get("ts")
    if not isinstance(message_ts, str) or not message_ts:
        _mark_failure(
            hint=hint,
            operation_id=operation_id,
            token=token,
            code="write_outcome_unknown",
            uncertain=True,
        )
        return
    _post_result(
        hint=hint,
        operation_id=operation_id,
        token=token,
        conversation_id=conversation_id,
        message_ts=message_ts,
    )


def sweep() -> None:
    """Redispatch unclaimed queued work and expire leases to uncertain."""
    now = timezone.now()
    queued = (
        Operation.objects.filter(
            state=Operation.State.QUEUED,
            due_at__lte=now,
            lease_token__isnull=True,
        )
        .order_by("due_at", "id")
        .values_list("pk", flat=True)[:200]
    )
    for operation_id in queued:
        dispatch_task("connections.tasks.send_follow_up_notification", str(operation_id))

    expired = list(
        Operation.objects.filter(
            state__in=[Operation.State.QUEUED, Operation.State.UNCERTAIN],
            lease_expires_at__lte=now,
        )
        .order_by("workspace_id", "report_id", "id")
        .values("pk", "workspace_id", "report_id", "follow_up_id")[:200]
    )
    for hint_values in expired:
        hint = SendHint(
            workspace_id=hint_values["workspace_id"],
            report_id=hint_values["report_id"],
            follow_up_id=hint_values["follow_up_id"],
        )
        with transaction.atomic():
            rows = _locked_rows(hint=hint, operation_id=hint_values["pk"])
            if rows is None:
                continue
            _, _, operation = rows
            if (
                operation.state in (Operation.State.QUEUED, Operation.State.UNCERTAIN)
                and operation.lease_expires_at is not None
                and operation.lease_expires_at <= now
            ):
                operation.state = Operation.State.UNCERTAIN
                operation.safe_error = "worker_lease_expired"
                operation.lease_token = None
                operation.lease_expires_at = None
                operation.updated_at = now
                operation.save(
                    update_fields=[
                        "state",
                        "safe_error",
                        "lease_token",
                        "lease_expires_at",
                        "updated_at",
                    ]
                )
