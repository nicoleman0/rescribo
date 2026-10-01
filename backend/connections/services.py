"""Settings mutations serialize on the workspace, then connection and report rows."""

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from accounts.models import Membership, Workspace
from accounts.tokens import digest, issue_token
from connections import providers
from connections.errors import ERROR_DETAILS
from connections.models import AllowedChannel, Connection, SetupState
from feedback.models import Report
from feedback.notifications import invalidate_pending_notifications
from integrations.slack.policy import REQUIRED_BOT_SCOPES


def lock_owner(actor: Membership) -> Workspace:
    workspace = Workspace.objects.select_for_update().filter(pk=actor.workspace_id).first()
    if workspace is None:
        raise NotFound()
    if not Membership.objects.filter(
        pk=actor.pk, workspace=workspace, role="owner", is_active=True
    ).exists():
        raise PermissionDenied()
    return workspace


def lock_connection(actor: Membership, provider: str, version: int) -> Connection:
    lock_owner(actor)
    row = (
        Connection.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, provider=provider)
        .first()
    )
    if row is None:
        raise NotFound()
    if row.version != version:
        raise providers.SetupError(
            "version_conflict", "Settings changed. Reload them before trying again."
        )
    return row


def callback_url(actor: Membership, provider: str) -> str:
    return (
        f"{settings.RESCRIBO_PUBLIC_BASE_URL}/api/workspaces/"
        f"{actor.workspace_id}/connections/{provider}/callback/"
    )


def start_setup(actor: Membership, provider: str, session_key: str, repository: str) -> str:
    client_id = getattr(settings, f"RESCRIBO_{provider.upper()}_CLIENT_ID")
    client_secret = getattr(settings, f"RESCRIBO_{provider.upper()}_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise providers.SetupError(
            "operator_setup", f"Ask the operator to configure the {provider} OAuth application."
        )
    if provider == "slack":
        providers.cipher()
    issued = issue_token(now=timezone.now(), lifetime=timedelta(minutes=10))
    with transaction.atomic():
        lock_owner(actor)
        SetupState.objects.filter(
            actor__workspace_id=actor.workspace_id, provider=provider, used_at__isnull=True
        ).update(used_at=timezone.now())
        SetupState.objects.create(
            token_digest=issued.digest,
            actor=actor,
            session_digest=digest(session_key),
            provider=provider,
            repository=repository,
            expires_at=issued.expires_at,
        )
    params = dict(
        client_id=client_id, state=issued.secret, redirect_uri=callback_url(actor, provider)
    )
    if provider == "slack":
        params["scope"] = ",".join(sorted(REQUIRED_BOT_SCOPES))
        base = "https://slack.com/oauth/v2/authorize"
    else:
        base = "https://github.com/login/oauth/authorize"
    return f"{base}?{urlencode(params)}"


def finish_setup(actor: Membership, provider: str, session_key: str, state: str, code: str) -> None:
    with transaction.atomic():
        lock_owner(actor)
        pending = (
            SetupState.objects.select_for_update()
            .filter(
                token_digest=digest(state),
                actor=actor,
                provider=provider,
                session_digest=digest(session_key),
                used_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if pending is None:
            raise providers.SetupError(
                "invalid_state",
                "Connection setup expired or was already used. Start again in the same browser.",
            )
        pending.used_at = timezone.now()
        pending.save(update_fields=["used_at"])
        repository = pending.repository
        failure = None
        try:
            with transaction.atomic():
                bind_connection(actor, provider, code, repository)
        except providers.PROVIDER_ERRORS as error:
            failure = providers.safe_provider_error(error)
    if failure is not None:
        raise failure


def bind_connection(actor: Membership, provider: str, code: str, repository: str) -> None:
    if provider == "slack":
        values = providers.slack_setup(code, callback_url(actor, provider))
    else:
        values = providers.github_setup(code, callback_url(actor, provider), repository)
    row, _ = Connection.objects.select_for_update().get_or_create(
        workspace_id=actor.workspace_id, provider=provider
    )
    old_binding = (row.external_id, row.repository_id, row.repository)
    cancel_notifications(actor.workspace_id)
    if row.external_id != values["external_id"]:
        row.channels.all().delete()
    for key, value in values.items():
        setattr(row, key, value)
    if old_binding != (row.external_id, row.repository_id, row.repository):
        row.binding_revision += 1
    row.status = Connection.Status.ACTIVE
    row.error_code = ""
    row.last_success_at = timezone.now()
    row.version += 1
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as error:
        raise providers.SetupError(
            "team_in_use",
            "This Slack workspace is already connected to another product workspace.",
        ) from error


def cancel_notifications(workspace_id: UUID) -> None:
    for report in (
        Report.objects.select_for_update().filter(workspace_id=workspace_id).order_by("id")
    ):
        invalidate_pending_notifications(report=report, reason="disconnected", now=timezone.now())


def disable_slack_team(team_id: str, code: str) -> bool:
    """Fail closed after verified removal or revoked credentials; the owner must reconnect."""
    with transaction.atomic():
        rows = list(
            Connection.objects.select_for_update()
            .filter(provider=Connection.Provider.SLACK, external_id=team_id)
            .exclude(status=Connection.Status.DISCONNECTED)
        )
        for row in rows:
            cancel_notifications(row.workspace_id)
            row.status = Connection.Status.ERROR
            row.error_code = code
            row.version += 1
            row.save(update_fields=["status", "error_code", "version"])
    return bool(rows)


def disconnect(actor: Membership, provider: str, version: int) -> None:
    with transaction.atomic():
        row = lock_connection(actor, provider, version)
        cancel_notifications(actor.workspace_id)
        row.credential = ""
        # Removing the installation binding prevents future installation-token minting.
        row.external_id = ""
        row.binding_revision += 1
        row.status = Connection.Status.DISCONNECTED
        row.error_code = ""
        row.version += 1
        row.save()
        row.channels.all().delete()
        SetupState.objects.filter(
            actor__workspace_id=actor.workspace_id, provider=provider, used_at__isnull=True
        ).update(used_at=timezone.now())


def update_channel(actor: Membership, version: int, channel_id: str, remove: bool) -> None:
    with transaction.atomic():
        row = lock_connection(actor, "slack", version)
        if row.status != Connection.Status.ACTIVE:
            raise providers.SetupError(
                "not_connected", "Reconnect Slack before changing allowed channels."
            )
        if remove:
            row.channels.filter(channel_id=channel_id).delete()
        else:
            details = providers.channel_details(row.credential, channel_id)
            AllowedChannel.objects.update_or_create(
                connection=row,
                channel_id=channel_id,
                defaults={**details, "verified_at": timezone.now()},
            )
        row.version += 1
        row.save(update_fields=["version"])


def refresh_connection(actor: Membership, provider: str, version: int) -> None:
    failure = None
    with transaction.atomic():
        row = lock_connection(actor, provider, version)
        if row.status == Connection.Status.DISCONNECTED:
            raise providers.SetupError(
                "not_connected", "Connect the application before checking its status."
            )
        try:
            providers.check_connection(
                provider, row.credential, row.external_id, row.repository, row.repository_id
            )
        except providers.PROVIDER_ERRORS as error:
            failure = providers.safe_provider_error(error)
            row.status = Connection.Status.ERROR
            row.error_code = failure.code
            cancel_notifications(actor.workspace_id)
        else:
            row.status = Connection.Status.ACTIVE
            row.error_code = ""
            row.last_success_at = timezone.now()
        row.version += 1
        row.save()
    if failure:
        raise failure


def connection_payload(row: Connection) -> dict[str, Any]:
    from feedback.models import ReportNotificationOperation
    from operations.models import ExternalOperation

    if row.provider == "github":
        counts = {
            state: ExternalOperation.objects.filter(
                workspace_id=row.workspace_id,
                kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
                state=operation_state,
            ).count()
            for state, operation_state in (
                ("queued", ExternalOperation.State.QUEUED),
                ("running", ExternalOperation.State.RUNNING),
                ("failed", ExternalOperation.State.FAILED),
                ("uncertain", ExternalOperation.State.UNCERTAIN),
            )
        }
    else:
        counts = {"running": 0} | {
            state: ReportNotificationOperation.objects.filter(
                workspace_id=row.workspace_id, state=state
            ).count()
            for state in ("queued", "failed", "uncertain")
        }
    return {
        key: getattr(row, key)
        for key in (
            "provider",
            "identity",
            "external_id",
            "status",
            "scopes",
            "error_code",
            "last_success_at",
            "last_reconciled_at",
            "repository",
            "visibility",
            "version",
        )
    } | {
        "channels": list(
            row.channels.order_by("channel_id").values(
                "channel_id", "name", "is_private", "verified_at"
            )
        ),
        "operations": counts,
        "error_detail": ERROR_DETAILS.get(row.error_code, ""),
    }
