"""Owner deletion of primary records; upstream content and backups are not erased."""

import logging
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, ValidationError

from accounts.demo import is_demo_workspace
from accounts.models import Invitation, Membership, Workspace
from connections.errors import PROVIDER_ERRORS
from connections.models import Connection
from connections.services import cancel_notifications, lock_owner
from feedback.models import (
    Activity,
    EngineeringIssue,
    FollowUp,
    Problem,
    Report,
    ReportNotificationOperation,
)
from feedback.services import require_version, write_activity
from integrations.slack import client as slack_client
from operations.models import ExternalOperation

logger = logging.getLogger(__name__)


def delete_report(actor: Membership, report_id: UUID, version: int, confirmation: str) -> None:
    with transaction.atomic():
        lock_owner(actor)
        report = (
            Report.objects.select_for_update()
            .filter(pk=report_id, workspace_id=actor.workspace_id)
            .first()
        )
        if report is None:
            raise NotFound()
        require_version(row=report, expected_version=version)
        if confirmation != "DELETE":
            raise ValidationError(
                {"confirmation": ["Type DELETE to confirm permanent report deletion."]}
            )
        ReportNotificationOperation.objects.filter(
            report=report, workspace_id=actor.workspace_id
        ).delete()
        FollowUp.objects.filter(report=report, workspace_id=actor.workspace_id).delete()
        Activity.objects.filter(workspace_id=actor.workspace_id).filter(
            Q(record_type="report", record_id=report_id) | Q(metadata__report_id=str(report_id))
        ).delete()
        report.delete()
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_DELETED,
            record_type="report",
            record_id=report_id,
        )


def _require_workspace_confirmation(confirmation: str, workspace: Workspace) -> None:
    if confirmation != workspace.slug:
        raise ValidationError(
            {"confirmation": ["Type the workspace slug to confirm permanent deletion."]}
        )


def _revoke_slack_token(workspace_id: UUID) -> None:
    """Best effort: a Slack outage must not block deletion, and no lock is held here."""
    if is_demo_workspace(workspace_id):
        return
    credential = (
        Connection.objects.filter(workspace_id=workspace_id, provider=Connection.Provider.SLACK)
        .exclude(credential="")
        .values_list("credential", flat=True)
        .first()
    )
    if credential is None:
        return
    try:
        slack_client.revoke_token(credential)
    except PROVIDER_ERRORS as error:
        logger.warning(
            "Slack token revocation failed during workspace deletion: %s", type(error).__name__
        )


def delete_workspace(actor: Membership, confirmation: str) -> None:
    # Reject before the network call; the transaction below repeats the checks under locks.
    with transaction.atomic():
        _require_workspace_confirmation(confirmation, lock_owner(actor))
    _revoke_slack_token(actor.workspace_id)
    with transaction.atomic():
        workspace = lock_owner(actor, deleting=True)
        _require_workspace_confirmation(confirmation, workspace)
        cancel_notifications(actor.workspace_id)
        Connection.objects.filter(workspace=workspace).update(
            credential="", external_id="", status="disconnected"
        )
        purge_workspace_content(workspace)
        workspace.delete()


def purge_workspace_content(workspace: Workspace) -> None:
    """Delete a workspace's records, keeping the workspace, memberships, and connections."""
    # Explicit order handles PROTECT history references before membership removal.
    ReportNotificationOperation.objects.filter(workspace=workspace).delete()
    FollowUp.objects.filter(workspace=workspace).delete()
    ExternalOperation.objects.filter(workspace=workspace).delete()
    Activity.objects.filter(workspace=workspace).delete()
    Report.objects.filter(workspace=workspace).delete()
    EngineeringIssue.objects.filter(workspace=workspace).delete()
    Problem.objects.filter(workspace=workspace).delete()
    Invitation.objects.filter(workspace=workspace).delete()
