"""Celery tasks that apply verified, deduplicated GitHub webhook deliveries."""

from typing import Any
from uuid import UUID

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from accounts.models import Workspace
from connections.models import Connection
from feedback.engineering_issues import apply_installation_webhook, apply_issue_webhook
from feedback.models import EngineeringIssue, Problem
from integrations.github_app.webhooks import IssueEvent, parse_installation_event, parse_issue_event


@shared_task
def process_github_delivery(*, event_name: str, payload: dict[str, Any]) -> None:
    """Resolve the installation, then apply a tracked issue or access-loss event.

    An unrecognised installation, untracked action, or malformed payload is a
    no-op or a loud task failure, not a silent partial application: the caller
    already verified the signature, so a shape we do not expect is unexpected.
    """
    installation = payload.get("installation")
    installation_id = str(installation["id"]) if isinstance(installation, dict) else None
    if installation_id is None:
        return
    if event_name == "issues":
        event = parse_issue_event(payload)
        if event is not None:
            apply_issue_webhook(installation_id=installation_id, event=event)
        return
    if event_name in ("installation", "installation_repositories"):
        installation_event = parse_installation_event(event_name, payload)
        if installation_event is not None:
            apply_installation_webhook(installation_id=installation_id, event=installation_event)


@shared_task
def reconcile_github_issues() -> None:
    """Persist sync requests for active links; workers perform the provider reads."""
    connection_ids = (
        Connection.objects.filter(
            provider=Connection.Provider.GITHUB, status=Connection.Status.ACTIVE
        )
        .order_by("workspace_id", "id")
        .values_list("pk", flat=True)
    )
    for connection_id in connection_ids:
        hint = Connection.objects.filter(pk=connection_id).values("workspace_id").first()
        if hint is None:
            continue
        dispatch_ids: list[str] = []
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=hint["workspace_id"])
            connection = Connection.objects.select_for_update().get(pk=connection_id)
            if connection.status != Connection.Status.ACTIVE:
                continue
            targets = []
            issue_hints = (
                EngineeringIssue.objects.filter(connection_id=connection.pk, active=True)
                .order_by("problem_id", "pk")
                .values("pk", "problem_id")
            )
            for issue_hint in issue_hints:
                Problem.objects.select_for_update().get(pk=issue_hint["problem_id"])
                issue = EngineeringIssue.objects.select_for_update().get(pk=issue_hint["pk"])
                if not issue.active:
                    continue
                if issue.sync_requested_generation <= issue.sync_completed_generation:
                    issue.sync_requested_generation += 1
                    issue.save(update_fields=["sync_requested_generation"])
                targets.append(
                    {
                        "issue_id": str(issue.pk),
                        "generation": issue.sync_requested_generation,
                        "done": False,
                    }
                )
                if issue.sync_requested_generation > issue.sync_completed_generation:
                    dispatch_ids.append(str(issue.pk))
            connection.reconciliation_started_at = timezone.now()
            connection.reconciliation_binding_revision = connection.binding_revision
            connection.reconciliation_targets = targets
            connection.save(
                update_fields=[
                    "reconciliation_started_at",
                    "reconciliation_binding_revision",
                    "reconciliation_targets",
                ]
            )
        for issue_id in dispatch_ids:
            try:
                sync_github_issue.delay(issue_id)
            except Exception:
                # The generation remains pending for the minute dispatcher to publish.
                continue


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
    apply_issue_webhook(
        installation_id=issue.connection.external_id,
        event=IssueEvent(
            action="edited",
            number=issue.number,
            issue_id=issue.issue_id,
            repository=issue.connection.repository,
            repository_id=issue.repository_id,
            state_reason=None,
            updated_at=timezone.now().isoformat(),
        ),
    )
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
        Workspace.objects.select_for_update().get(pk=hint["workspace_id"])
        connection = Connection.objects.select_for_update().get(pk=hint["connection_id"])
        Problem.objects.select_for_update().get(pk=hint["problem_id"])
        issue = EngineeringIssue.objects.select_for_update().get(pk=issue_id)
        if (
            connection.reconciliation_binding_revision != connection.binding_revision
            or connection.reconciliation_started_at is None
            or issue.access != EngineeringIssue.Access.OK
            or issue.last_successful_sync_at is None
            or issue.last_successful_sync_at < connection.reconciliation_started_at
        ):
            return
        targets = list(connection.reconciliation_targets)
        for target in targets:
            if (
                target["issue_id"] == str(issue.pk)
                and issue.sync_completed_generation >= target["generation"]
            ):
                target["done"] = True
        connection.reconciliation_targets = targets
        updates = ["reconciliation_targets"]
        if targets and all(target["done"] for target in targets):
            connection.last_reconciled_at = timezone.now()
            updates.append("last_reconciled_at")
        connection.save(update_fields=updates)
