"""Celery tasks that apply verified, deduplicated GitHub webhook deliveries."""

from uuid import UUID

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.services import lock_workspace
from connections.models import Connection
from feedback.demo import reset_demo
from feedback.engineering_issues import sync_issue
from feedback.models import (
    EngineeringIssue,
    IssueReconciliation,
    IssueReconciliationTarget,
    Problem,
)
from operations.dispatch import dispatch_task


@shared_task
def reconcile_github_issues() -> None:
    """Persist sync requests for active links; workers perform the provider reads."""
    connection_ids = (
        Connection.objects.filter(
            provider=Connection.Provider.GITHUB, status=Connection.Status.ACTIVE
        )
        .exclude(workspace__is_demo=True)
        .order_by("workspace_id", "id")
        .values_list("pk", flat=True)
    )
    for connection_id in connection_ids:
        hint = Connection.objects.filter(pk=connection_id).values("workspace_id").first()
        if hint is None:
            continue
        dispatch_ids: list[str] = []
        with transaction.atomic():
            lock_workspace(hint["workspace_id"])
            connection = Connection.objects.select_for_update().get(pk=connection_id)
            if connection.status != Connection.Status.ACTIVE:
                continue
            run, _ = IssueReconciliation.objects.update_or_create(
                connection=connection,
                defaults={
                    "started_at": timezone.now(),
                    "binding_revision": connection.binding_revision,
                },
            )
            run.targets.all().delete()
            issue_hints = (
                EngineeringIssue.objects.filter(connection_id=connection.pk, active=True)
                .order_by("problem_id", "pk")
                .values("pk", "problem_id")
            )
            for issue_hint in issue_hints:
                Problem.objects.select_for_update(no_key=True).get(pk=issue_hint["problem_id"])
                issue = EngineeringIssue.objects.select_for_update().get(pk=issue_hint["pk"])
                if not issue.active:
                    continue
                if issue.sync_requested_generation <= issue.sync_completed_generation:
                    issue.sync_requested_generation += 1
                    issue.save(update_fields=["sync_requested_generation"])
                IssueReconciliationTarget.objects.create(
                    run=run, issue=issue, generation=issue.sync_requested_generation
                )
                if issue.sync_requested_generation > issue.sync_completed_generation:
                    dispatch_ids.append(str(issue.pk))
            if not run.targets.exists():
                connection.last_reconciled_at = run.started_at
                connection.save(update_fields=["last_reconciled_at"])
        for issue_id in dispatch_ids:
            dispatch_task("feedback.tasks.sync_github_issue", issue_id)


@shared_task
def sync_github_issue(issue_id: str) -> None:
    """Fetch an issue through the same current-state application path as webhooks."""
    issue = (
        EngineeringIssue.objects.filter(pk=issue_id, active=True)
        .select_related("connection")
        .first()
    )
    if issue is None:
        return
    if issue.connection.status != Connection.Status.ACTIVE:
        return
    sync_issue(issue_id=issue.pk)
    _complete_reconciliation_target(issue.pk)


def _complete_reconciliation_target(issue_id: UUID) -> None:
    hint = (
        EngineeringIssue.objects.filter(pk=issue_id)
        .values("workspace_id", "connection_id", "problem_id")
        .first()
    )
    if hint is None:
        return
    with transaction.atomic():
        lock_workspace(hint["workspace_id"])
        connection = Connection.objects.select_for_update().get(pk=hint["connection_id"])
        Problem.objects.select_for_update(no_key=True).get(pk=hint["problem_id"])
        issue = EngineeringIssue.objects.select_for_update().get(pk=issue_id)
        run = IssueReconciliation.objects.filter(connection=connection).first()
        if (
            run is None
            or run.binding_revision != connection.binding_revision
            or issue.access != EngineeringIssue.Access.OK
            or issue.last_successful_sync_at is None
            or issue.last_successful_sync_at < run.started_at
        ):
            return
        run.targets.filter(issue=issue, generation__lte=issue.sync_completed_generation).update(
            done=True
        )
        if not run.targets.filter(done=False, issue__active=True).exists():
            connection.last_reconciled_at = timezone.now()
            connection.save(update_fields=["last_reconciled_at"])


@shared_task
def reset_demo_workspace() -> None:
    reset_demo(visitor_password=settings.RESCRIBO_DEMO_PASSWORD or None)
