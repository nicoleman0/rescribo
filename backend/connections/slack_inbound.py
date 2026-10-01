"""Signed Slack interactions and events, resolved to one workspace by team ID.

Callers verify the request signature before anything here runs.
"""

import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.utils import timezone

from connections import services, slack_identity
from connections.errors import PROVIDER_ERRORS
from connections.models import AllowedChannel, Connection, SlackCaptureContext
from feedback.models import Report, ReportSource
from feedback.reports import submit_report
from feedback.submissions import ReportSubmission, SourceSnapshot
from integrations.slack import client
from integrations.slack.errors import REVOCATION_ERRORS, ChannelRejected, slack_error_code
from integrations.slack.modals import (
    CaptureSubmission,
    SubmissionErrors,
    build_capture_modal,
    build_notice_modal,
    parse_capture_submission,
)
from integrations.slack.shortcuts import MessageShortcut, parse_message_shortcut
from operations.dispatch import dispatch_task
from operations.models import InboundReceipt

logger = logging.getLogger(__name__)

CAPTURE_CALLBACK_ID = "submit_customer_feedback"
CONTEXT_LIFETIME = timedelta(minutes=15)
CHANNEL_CACHE_SECONDS = 60

REJECTED_TEXT = (
    "This message can't be captured. Use an approved internal channel that includes the "
    "Rescribo app. Nothing from the message was stored."
)
EXPIRED_TEXT = "This capture expired. Run the shortcut on the message again."
UNLINKED_TEXT = (
    "Your Slack account is not linked to Rescribo. Generate a code in Rescribo settings, "
    "then run the shortcut again."
)


class CaptureRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def report_url(report: Report) -> str:
    return f"{settings.RESCRIBO_PUBLIC_BASE_URL}/inbox/{report.pk}"


def active_connection(team_id: str) -> Connection | None:
    return (
        Connection.objects.select_related("workspace")
        .filter(
            provider=Connection.Provider.SLACK,
            external_id=team_id,
            status=Connection.Status.ACTIVE,
        )
        .first()
    )


def record_provider_failure(connection: Connection, error: Exception) -> None:
    code = slack_error_code(error)
    if code in REVOCATION_ERRORS:
        services.disable_slack_team(connection.external_id, "credentials_revoked")


def _require_allowed(connection: Connection, channel_id: str) -> None:
    if not AllowedChannel.objects.filter(connection=connection, channel_id=channel_id).exists():
        raise ChannelRejected("unapproved_channel", channel_id)


def _check_channel(connection: Connection, channel_id: str, *, cached: bool) -> None:
    """Raise `CaptureRejected` unless the channel is approved and currently eligible."""
    try:
        _require_allowed(connection, channel_id)
        # The connection version changes with every channel edit, which retires old entries.
        key = f"slack-channel:{connection.pk}:{connection.version}:{channel_id}"
        if cached and cache.get(key):
            return
        client.eligible_channel(
            connection.credential,
            channel_id,
            timeout=client.INTERACTIVE_TIMEOUT if cached else 10,
        )
        cache.set(key, True, CHANNEL_CACHE_SECONDS)
    except ChannelRejected as rejected:
        raise CaptureRejected(rejected.reason) from rejected
    except PROVIDER_ERRORS as error:
        record_provider_failure(connection, error)
        raise CaptureRejected("channel_check_failed") from error


def _open(connection: Connection, trigger_id: str, view: dict[str, Any]) -> None:
    try:
        client.open_view(connection.credential, trigger_id=trigger_id, view=view)
    except PROVIDER_ERRORS as error:
        record_provider_failure(connection, error)
        logger.warning("Slack views.open failed: %s", slack_error_code(error) or type(error))


def _existing_report(connection: Connection, shortcut: MessageShortcut) -> Report | None:
    return Report.objects.filter(
        workspace_id=connection.workspace_id,
        source__kind=ReportSource.Kind.SLACK,
        source__external_workspace_id=shortcut.team_id,
        source__external_channel_id=shortcut.channel_id,
        source__external_message_id=shortcut.message_ts,
    ).first()


def start_capture(payload: Mapping[str, Any]) -> None:
    """Open the capture modal. Runs inside Slack's three-second acknowledgement."""
    shortcut = parse_message_shortcut(payload)
    if shortcut.callback_id != CAPTURE_CALLBACK_ID:
        return
    connection = active_connection(shortcut.team_id)
    if connection is None:
        logger.info("Slack shortcut from a team without an active connection")
        return
    try:
        # DMs never reach the allowlist: approved channel IDs are validated as C/G.
        _check_channel(connection, shortcut.channel_id, cached=True)
    except CaptureRejected:
        _open(connection, shortcut.trigger_id, build_notice_modal("Can't capture", REJECTED_TEXT))
        return
    existing = _existing_report(connection, shortcut)
    if existing is not None:
        _open(
            connection,
            shortcut.trigger_id,
            build_notice_modal(
                "Already captured",
                # The actor may not be a member yet, so show no workspace data.
                "This message is already in Rescribo.",
                link_url=report_url(existing),
            ),
        )
        return
    linked = slack_identity.linked_membership(
        workspace_id=connection.workspace_id,
        team_id=shortcut.team_id,
        user_id=shortcut.actor_id,
    )
    now = timezone.now()
    context = SlackCaptureContext.objects.create(
        connection=connection,
        team_id=shortcut.team_id,
        channel_id=shortcut.channel_id,
        actor_id=shortcut.actor_id,
        message_ts=shortcut.message_ts,
        thread_ts=shortcut.thread_ts or "",
        author_external_id=shortcut.author_id or "",
        text=shortcut.text,
        link_required=linked is None,
        created_at=now,
        expires_at=now + CONTEXT_LIFETIME,
    )
    _open(
        connection,
        shortcut.trigger_id,
        build_capture_modal(
            shortcut,
            workspace_name=connection.workspace.name,
            captured_on=now.date(),
            context_id=str(context.pk),
            link_required=context.link_required,
        ),
    )
    dispatch_task("connections.tasks.revalidate_capture_channel", str(context.pk))


def revalidate_capture_channel(context_id: UUID) -> None:
    """Fresh channel check while the modal is open; submission fails closed without it."""
    context = (
        SlackCaptureContext.objects.select_related("connection")
        .filter(pk=context_id, consumed_at__isnull=True, rejected_reason="")
        .first()
    )
    if context is None:
        return
    connection = context.connection
    try:
        if connection.status != Connection.Status.ACTIVE:
            raise CaptureRejected("connection_inactive")
        _check_channel(connection, context.channel_id, cached=False)
    except CaptureRejected as rejected:
        SlackCaptureContext.objects.filter(pk=context.pk, consumed_at__isnull=True).update(
            rejected_reason=rejected.reason, text=""
        )
        return
    SlackCaptureContext.objects.filter(
        pk=context.pk, consumed_at__isnull=True, rejected_reason=""
    ).update(channel_validated_at=timezone.now())


def _settle(context: SlackCaptureContext, *, rejected_reason: str = "") -> None:
    context.consumed_at = timezone.now()
    context.rejected_reason = rejected_reason
    context.text = ""
    context.save(update_fields=["consumed_at", "rejected_reason", "text"])


def _update(view: dict[str, Any]) -> dict[str, Any]:
    return {"response_action": "update", "view": view}


def _errors(errors: Mapping[str, str]) -> dict[str, Any]:
    return {"response_action": "errors", "errors": dict(errors)}


def submit_capture(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Commit the report or return a visible error. Never acknowledge an unsaved report."""
    try:
        submission = parse_capture_submission(payload)
    except SubmissionErrors as invalid:
        return _errors(invalid.errors)
    team = payload.get("team")
    user = payload.get("user")
    team_id = team.get("id") if isinstance(team, Mapping) else None
    user_id = user.get("id") if isinstance(user, Mapping) else None
    try:
        context_id = UUID(submission.context_id)
    except ValueError:
        return _update(build_notice_modal("Capture expired", EXPIRED_TEXT))
    try:
        with transaction.atomic():
            return _submit_locked(submission, context_id, team_id, user_id)
    except DatabaseError:
        logger.exception("Slack capture could not be saved")
        return _errors({"report_title": "The report could not be saved. Submit again."})


def _submit_locked(
    submission: CaptureSubmission, context_id: UUID, team_id: str | None, user_id: str | None
) -> dict[str, Any]:
    # Identity comes from the stored context and the signed actor, never from the view.
    context = (
        SlackCaptureContext.objects.select_for_update()
        .select_related("connection")
        .filter(
            pk=context_id,
            team_id=team_id or "",
            actor_id=user_id or "",
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .first()
    )
    if context is None:
        return _update(build_notice_modal("Capture expired", EXPIRED_TEXT))
    connection = context.connection
    workspace_id = connection.workspace_id
    if submission.link_code.strip():
        try:
            slack_identity.redeem_link_code(
                submission.link_code,
                workspace_id=workspace_id,
                team_id=context.team_id,
                user_id=context.actor_id,
            )
        except slack_identity.LinkCodeRejected as rejected:
            return _errors({"slack_link_code": str(rejected)})
    membership = slack_identity.linked_membership(
        workspace_id=workspace_id, team_id=context.team_id, user_id=context.actor_id
    )
    if membership is None:
        if context.link_required:
            return _errors({"slack_link_code": "Enter the linking code from Rescribo settings."})
        _settle(context, rejected_reason="unlinked")
        return _update(build_notice_modal("Account not linked", UNLINKED_TEXT))
    if context.rejected_reason:
        _settle(context, rejected_reason=context.rejected_reason)
        return _update(build_notice_modal("Can't capture", REJECTED_TEXT))
    if context.channel_validated_at is None:
        return _errors({"report_title": "Still checking this channel. Submit again in a moment."})
    if (
        connection.status != Connection.Status.ACTIVE
        or not AllowedChannel.objects.filter(
            connection=connection, channel_id=context.channel_id
        ).exists()
    ):
        _settle(context, rejected_reason="unapproved_channel")
        return _update(build_notice_modal("Can't capture", REJECTED_TEXT))
    result = submit_report(
        actor=membership,
        submission=ReportSubmission(
            title=submission.title,
            description=submission.additional_context,
            customer_label=submission.customer_reference,
            customer_contact_reference="",
            affected_version=submission.affected_version,
            source=SourceSnapshot(
                kind=ReportSource.Kind.SLACK,
                external_workspace_id=context.team_id,
                external_channel_id=context.channel_id,
                external_message_id=context.message_ts,
                permalink="",
                author_external_id=context.author_external_id,
                author_display_name="",
                snapshot_text=context.text,
            ),
        ),
    )
    _settle(context)
    if result.created:
        source_id = str(result.report.source.pk)
        transaction.on_commit(
            lambda: dispatch_task("connections.tasks.resolve_slack_permalink", source_id)
        )
    heading = "Report submitted" if result.created else "Already captured"
    return _update(
        build_notice_modal(
            heading,
            f"“{result.report.title}” is in the Rescribo inbox.",
            link_url=report_url(result.report),
        )
    )


def resolve_permalink(source_id: UUID) -> None:
    """Attach the message permalink. A failure is recorded for retry, never lost as a report."""
    source = ReportSource.objects.filter(
        pk=source_id, kind=ReportSource.Kind.SLACK, permalink=""
    ).first()
    if source is None:
        return
    connection = Connection.objects.filter(
        workspace_id=source.workspace_id,
        provider=Connection.Provider.SLACK,
        external_id=source.external_workspace_id,
        status=Connection.Status.ACTIVE,
    ).first()
    permalink, error_code = "", ""
    if connection is None:
        error_code = "not_connected"
    else:
        try:
            permalink = client.message_permalink(
                connection.credential,
                channel_id=source.external_channel_id,
                message_ts=source.external_message_id,
            )
        except (*PROVIDER_ERRORS, ValueError) as error:
            record_provider_failure(connection, error)
            error_code = slack_error_code(error) or "unavailable"
    ReportSource.objects.filter(pk=source.pk, permalink="").update(
        permalink=permalink, permalink_error=error_code, permalink_attempted_at=timezone.now()
    )


def sweep() -> None:
    """Delete expired capture contexts and pick up permalinks whose dispatch was lost."""
    now = timezone.now()
    SlackCaptureContext.objects.filter(expires_at__lte=now).delete()
    for source_id in ReportSource.objects.filter(
        kind=ReportSource.Kind.SLACK,
        permalink="",
        permalink_attempted_at__isnull=True,
        captured_at__lte=now - timedelta(minutes=1),
    ).values_list("pk", flat=True)[:100]:
        dispatch_task("connections.tasks.resolve_slack_permalink", str(source_id))


def handle_event(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """URL verification and connection lifecycle. Returns the response body, if any."""
    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge")
        return {"challenge": challenge} if isinstance(challenge, str) else None
    event = payload.get("event")
    team_id = payload.get("team_id")
    event_id = payload.get("event_id")
    if (
        payload.get("type") != "event_callback"
        or not isinstance(event, Mapping)
        or not isinstance(team_id, str)
        or not isinstance(event_id, str)
    ):
        return None
    tokens = event.get("tokens")
    if event.get("type") == "app_uninstalled":
        code = "app_uninstalled"
    elif (
        event.get("type") == "tokens_revoked" and isinstance(tokens, Mapping) and tokens.get("bot")
    ):
        code = "credentials_revoked"
    else:
        return None
    # Slack retries unacknowledged events; the receipt makes processing idempotent.
    with transaction.atomic():
        _, created = InboundReceipt.objects.get_or_create(
            provider=InboundReceipt.Provider.SLACK,
            delivery_id=event_id[:128],
            defaults={
                "event": event["type"],
                "status": InboundReceipt.Status.SUCCEEDED,
                "attempts": 1,
            },
        )
        if created:
            services.disable_slack_team(team_id, code)
    return None
