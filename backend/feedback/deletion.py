"""Owner deletion of primary records; upstream content and backups are not erased."""

from uuid import UUID

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import Invitation, Membership
from connections.models import Connection
from connections.services import cancel_notifications, lock_owner
from feedback.models import Activity, Problem, Report, ReportNotificationOperation
from feedback.services import require_version, write_activity


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


def delete_workspace(actor: Membership, confirmation: str) -> None:
    with transaction.atomic():
        workspace = lock_owner(actor)
        if confirmation != workspace.slug:
            raise ValidationError(
                {"confirmation": ["Type the workspace slug to confirm permanent deletion."]}
            )
        cancel_notifications(actor)
        Connection.objects.filter(workspace=workspace).update(
            credential="", external_id="", status="disconnected"
        )
        # Explicit order handles PROTECT history references before membership removal.
        ReportNotificationOperation.objects.filter(workspace=workspace).delete()
        Activity.objects.filter(workspace=workspace).delete()
        Report.objects.filter(workspace=workspace).delete()
        Problem.objects.filter(workspace=workspace).delete()
        Invitation.objects.filter(workspace=workspace).delete()
        workspace.delete()
