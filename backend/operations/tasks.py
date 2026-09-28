"""Leased GitHub issue operations and recovery tasks."""

from datetime import timedelta
from uuid import UUID, uuid4

import httpx
from celery import shared_task
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Membership, Workspace
from connections.models import Connection
from feedback.engineering_issues import _supersede_and_create
from feedback.models import Activity, EngineeringIssue, Problem
from integrations.github_app.client import GitHubAPIError
from integrations.github_app.issues import (
    IssueLinkError,
    parse_issue_payload,
    parse_issue_reference,
)
from integrations.github_app.settings import github_client
from operations.github_issue_create import LEASE_TTL, exact_body, marker_for
from operations.models import ExternalOperation, InboundReceipt


def _mark(operation_id: UUID, token: UUID, *, state: str, safe_error: str) -> None:
    ExternalOperation.objects.filter(
        pk=operation_id,
        state=ExternalOperation.State.RUNNING,
        lease_token=token,
    ).update(
        state=state,
        safe_error=safe_error,
        completed_at=timezone.now(),
        lease_token=None,
        lease_expires_at=None,
    )


@shared_task
def process_github_issue_create(operation_id: str) -> None:
    operation_uuid = UUID(operation_id)
    now = timezone.now()
    token = uuid4()
    hint = (
        ExternalOperation.objects.filter(pk=operation_uuid)
        .values("workspace_id", "connection_id", "problem_id")
        .first()
    )
    if hint is None:
        return
    with transaction.atomic():
        workspace = Workspace.objects.select_for_update().filter(pk=hint["workspace_id"]).first()
        connection = Connection.objects.select_for_update().filter(pk=hint["connection_id"]).first()
        problem = Problem.objects.select_for_update().filter(pk=hint["problem_id"]).first()
        operation = ExternalOperation.objects.select_for_update().filter(pk=operation_uuid).first()
        if workspace is None or connection is None or problem is None:
            return
        if operation is None or operation.state != ExternalOperation.State.QUEUED:
            return
        if operation.due_at > now:
            return
        operation.state = ExternalOperation.State.RUNNING
        operation.attempts += 1
        operation.started_at = now
        operation.lease_token = token
        operation.lease_expires_at = now + LEASE_TTL
        operation.save(
            update_fields=[
                "state",
                "attempts",
                "started_at",
                "lease_token",
                "lease_expires_at",
            ]
        )

    # Verify the frozen approval immediately before the external write.
    with transaction.atomic():
        workspace = Workspace.objects.select_for_update().filter(pk=operation.workspace_id).first()
        connection = (
            Connection.objects.select_for_update().filter(pk=operation.connection_id).first()
        )
        problem = (
            Problem.objects.select_for_update()
            .filter(
                pk=operation.problem_id,
                workspace_id=operation.workspace_id,
            )
            .first()
        )
        current = ExternalOperation.objects.select_for_update().filter(pk=operation_uuid).first()
        requester_active = Membership.objects.filter(
            pk=operation.requester_id,
            workspace_id=operation.workspace_id,
            is_active=True,
        ).exists()
        if (
            workspace is None
            or problem is None
            or connection is None
            or current is None
            or current.lease_token != token
            or current.state != ExternalOperation.State.RUNNING
        ):
            return
        if (
            not requester_active
            or problem.version != operation.problem_version
            or connection.status != Connection.Status.ACTIVE
            or connection.binding_revision != operation.binding_revision
            or connection.repository_id != operation.repository_id
            or EngineeringIssue.objects.filter(problem=problem, active=True).exists()
        ):
            current.state = ExternalOperation.State.CANCELLED
            current.safe_error = "approval_stale"
            current.completed_at = now
            current.lease_token = None
            current.lease_expires_at = None
            current.save(
                update_fields=[
                    "state",
                    "safe_error",
                    "completed_at",
                    "lease_token",
                    "lease_expires_at",
                ]
            )
            return

    owner, name = connection.repository.split("/", 1)
    try:
        with github_client() as client:
            token_value, _ = client.create_installation_token(
                installation_id=int(operation.connection.external_id),
                repository_id=operation.repository_id,
            )
            try:
                try:
                    repository = client.get_repository_by_id(
                        installation_token=token_value,
                        repository_id=operation.repository_id,
                    )
                except Exception:
                    _mark(
                        operation_uuid,
                        token,
                        state=ExternalOperation.State.FAILED,
                        safe_error="repository_unavailable",
                    )
                    return
                if str(repository.get("id")) != operation.connection.repository_id:
                    _mark(
                        operation_uuid,
                        token,
                        state=ExternalOperation.State.FAILED,
                        safe_error="repository_identity_changed",
                    )
                    return
                canonical = repository.get("full_name")
                if not isinstance(canonical, str) or canonical.count("/") != 1:
                    _mark(
                        operation_uuid,
                        token,
                        state=ExternalOperation.State.FAILED,
                        safe_error="repository_identity_changed",
                    )
                    return
                owner, name = canonical.split("/", 1)
                created = client.create_issue(
                    installation_token=token_value,
                    owner=owner,
                    name=name,
                    title=operation.title,
                    body=exact_body(operation),
                )
            finally:
                try:
                    client.revoke_installation_token(token=token_value)
                except Exception:
                    pass
        snapshot = parse_issue_payload(created, error=IssueLinkError)
    except httpx.TimeoutException:
        _mark(
            operation_uuid,
            token,
            state=ExternalOperation.State.UNCERTAIN,
            safe_error="write_timeout",
        )
        return
    except GitHubAPIError as error:
        state = (
            ExternalOperation.State.UNCERTAIN
            if error.status_code >= 500
            else ExternalOperation.State.FAILED
        )
        _mark(operation_uuid, token, state=state, safe_error="provider_error")
        return
    except Exception:
        # A malformed success or transport failure after dispatch may follow a write.
        _mark(
            operation_uuid,
            token,
            state=ExternalOperation.State.UNCERTAIN,
            safe_error="write_outcome_unknown",
        )
        return

    try:
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=operation.workspace_id)
            connection = Connection.objects.select_for_update().get(pk=operation.connection_id)
            problem = Problem.objects.select_for_update().get(
                pk=operation.problem_id,
                workspace_id=operation.workspace_id,
            )
            current = ExternalOperation.objects.select_for_update().get(pk=operation_uuid)
            if current.lease_token != token or current.state != ExternalOperation.State.RUNNING:
                return
            if (
                connection.binding_revision != operation.binding_revision
                or connection.repository_id != operation.repository_id
            ):
                current.state = ExternalOperation.State.UNCERTAIN
                current.safe_error = "binding_changed_after_write"
                current.remote_issue_id = snapshot.issue_id
                current.remote_number = snapshot.number
                current.remote_url = snapshot.url
                current.lease_token = None
                current.lease_expires_at = None
                current.save(
                    update_fields=[
                        "state",
                        "safe_error",
                        "remote_issue_id",
                        "remote_number",
                        "remote_url",
                        "lease_token",
                        "lease_expires_at",
                    ]
                )
                return
            member = Membership.objects.get(
                pk=operation.requester_id, workspace_id=operation.workspace_id
            )
            issue = _supersede_and_create(
                actor=member,
                problem=problem,
                connection=connection,
                snapshot=snapshot,
                now=timezone.now(),
                action=Activity.Action.ENGINEERING_ISSUE_CREATED,
            )
            current.state = ExternalOperation.State.SUCCEEDED
            current.remote_issue_id = issue.issue_id
            current.remote_number = issue.number
            current.remote_url = issue.url
            current.completed_at = timezone.now()
            current.safe_error = ""
            current.lease_token = None
            current.lease_expires_at = None
            current.save(
                update_fields=[
                    "state",
                    "remote_issue_id",
                    "remote_number",
                    "remote_url",
                    "completed_at",
                    "safe_error",
                    "lease_token",
                    "lease_expires_at",
                ]
            )
            connection.last_success_at = timezone.now()
            connection.save(update_fields=["last_success_at"])
    except Exception:
        # The POST already returned success. Never submit it a second time.
        _mark(
            operation_uuid,
            token,
            state=ExternalOperation.State.UNCERTAIN,
            safe_error="result_persist_failed",
        )


@shared_task
def dispatch_due_operations() -> None:
    now = timezone.now()
    ids = list(
        ExternalOperation.objects.filter(
            state=ExternalOperation.State.QUEUED,
            due_at__lte=now,
        )
        .order_by("due_at")
        .values_list("pk", flat=True)[:200]
    )
    for operation_id in ids:
        process_github_issue_create.delay(str(operation_id))
    receipts = (
        InboundReceipt.objects.filter(
            status=InboundReceipt.Status.PENDING,
            retry_at__lte=now,
        )
        .order_by("retry_at")
        .values_list("pk", flat=True)[:200]
    )
    for receipt_id in receipts:
        process_inbound_receipt.delay(str(receipt_id))
    pending_issue_ids = (
        EngineeringIssue.objects.filter(
            active=True,
            connection__status=Connection.Status.ACTIVE,
            sync_requested_generation__gt=models.F("sync_completed_generation"),
        )
        .filter(
            models.Q(sync_lease_expires_at__isnull=True) | models.Q(sync_lease_expires_at__lte=now)
        )
        .filter(models.Q(sync_retry_at__isnull=True) | models.Q(sync_retry_at__lte=now))
        .order_by("last_attempted_sync_at")
        .values_list("pk", flat=True)[:200]
    )
    from feedback.tasks import sync_github_issue

    for issue_id in pending_issue_ids:
        sync_github_issue.delay(str(issue_id))
    recovery_ids = ExternalOperation.objects.filter(
        state=ExternalOperation.State.UNCERTAIN,
        recovery_reference__gt="",
        due_at__lte=now,
    ).values_list("pk", flat=True)[:200]
    for operation_id in recovery_ids:
        reconcile_github_issue_create.delay(str(operation_id))
    # A running lease that expires after a POST is uncertain; it is never resent.
    expired = ExternalOperation.objects.filter(
        state=ExternalOperation.State.RUNNING,
        lease_expires_at__lte=now,
    )
    expired.update(
        state=ExternalOperation.State.UNCERTAIN,
        safe_error="worker_lease_expired",
        completed_at=now,
        lease_token=None,
        lease_expires_at=None,
    )


@shared_task
def process_inbound_receipt(receipt_id: str) -> None:
    receipt_uuid = UUID(receipt_id)
    now = timezone.now()
    token = uuid4()
    with transaction.atomic():
        receipt = InboundReceipt.objects.select_for_update().filter(pk=receipt_uuid).first()
        if receipt is None or receipt.status == InboundReceipt.Status.SUCCEEDED:
            return
        if receipt.retry_at > now:
            return
        if (
            receipt.status == InboundReceipt.Status.RUNNING
            and receipt.lease_expires_at
            and receipt.lease_expires_at > now
        ):
            return
        receipt.status = InboundReceipt.Status.RUNNING
        receipt.attempts += 1
        receipt.lease_token = token
        receipt.lease_expires_at = now + LEASE_TTL
        receipt.save(update_fields=["status", "attempts", "lease_token", "lease_expires_at"])
        event_name = receipt.event
        installation_id = receipt.installation_id
        normalized = receipt.normalized
        attempts = receipt.attempts
    try:
        if event_name == "issues":
            from integrations.github_app.webhooks import IssueEvent

            issue_event = IssueEvent(**normalized)
            from feedback.engineering_issues import apply_issue_webhook

            apply_issue_webhook(installation_id=installation_id, event=issue_event)
        elif event_name in {"installation", "installation_repositories"}:
            from integrations.github_app.webhooks import InstallationEvent

            installation_event = InstallationEvent(**normalized)
            from feedback.engineering_issues import apply_installation_webhook

            apply_installation_webhook(installation_id=installation_id, event=installation_event)
    except Exception:
        with transaction.atomic():
            current = (
                InboundReceipt.objects.select_for_update()
                .filter(
                    pk=receipt_uuid,
                    lease_token=token,
                )
                .first()
            )
            if current is None:
                return
            current.status = (
                InboundReceipt.Status.FAILED if attempts >= 12 else InboundReceipt.Status.PENDING
            )
            current.safe_error = "processing_failed"
            current.retry_at = now + timedelta(seconds=min(3600, 2 ** min(attempts, 10)))
            current.lease_token = None
            current.lease_expires_at = None
            current.save(
                update_fields=[
                    "status",
                    "safe_error",
                    "retry_at",
                    "lease_token",
                    "lease_expires_at",
                ]
            )
        return
    InboundReceipt.objects.filter(pk=receipt_uuid, lease_token=token).update(
        status=InboundReceipt.Status.SUCCEEDED,
        safe_error="",
        lease_token=None,
        lease_expires_at=None,
    )


@shared_task
def revalidate_github_connection(connection_id: str) -> None:
    """Recheck a selected repository after installation access may have changed."""
    hint = (
        Connection.objects.filter(pk=connection_id)
        .values("workspace_id", "external_id", "repository", "repository_id", "binding_revision")
        .first()
    )
    if hint is None or not hint["external_id"] or not hint["repository"]:
        return
    owner, name = hint["repository"].split("/", 1)
    repository: dict[str, object] | None = None
    try:
        with github_client() as client:
            token, _ = client.create_installation_token(
                installation_id=int(hint["external_id"]), repository_id=hint["repository_id"]
            )
            try:
                repository = client.get_repository_by_id(
                    installation_token=token, repository_id=hint["repository_id"]
                )
            finally:
                client.revoke_installation_token(token=token)
        if str(repository.get("id")) != hint["repository_id"]:
            return
        canonical = repository.get("full_name")
        if not isinstance(canonical, str) or canonical.count("/") != 1:
            return
    except Exception:
        return
    issue_ids: list[str] = []
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=hint["workspace_id"])
        connection = Connection.objects.select_for_update().filter(pk=connection_id).first()
        if (
            connection is None
            or connection.external_id != hint["external_id"]
            or connection.repository_id != hint["repository_id"]
            or connection.binding_revision != hint["binding_revision"]
        ):
            return
        connection.status = Connection.Status.ACTIVE
        connection.error_code = ""
        connection.repository = canonical
        connection.last_success_at = timezone.now()
        connection.version += 1
        connection.save(
            update_fields=["status", "error_code", "repository", "last_success_at", "version"]
        )
        for row in (
            EngineeringIssue.objects.filter(connection=connection, active=True)
            .order_by("problem_id", "pk")
            .values("pk", "problem_id")
        ):
            Problem.objects.select_for_update().get(pk=row["problem_id"])
            issue = EngineeringIssue.objects.select_for_update().get(pk=row["pk"])
            issue.sync_requested_generation += 1
            issue.save(update_fields=["sync_requested_generation"])
            issue_ids.append(str(issue.pk))
    from feedback.tasks import sync_github_issue

    for issue_id in issue_ids:
        try:
            sync_github_issue.delay(issue_id)
        except Exception:
            continue


def _recover(operation: ExternalOperation) -> list[dict[str, object]]:
    owner, name = operation.connection.repository.split("/", 1)
    with github_client() as client:
        token, _ = client.create_installation_token(
            installation_id=int(operation.connection.external_id),
            repository_id=operation.repository_id,
        )
        try:
            repository = client.get_repository_by_id(
                installation_token=token, repository_id=operation.repository_id
            )
            if (
                str(repository.get("id")) != operation.repository_id
                or not isinstance(repository.get("full_name"), str)
                or repository["full_name"].count("/") != 1
            ):
                return []
            canonical = repository["full_name"]
            owner, name = canonical.split("/", 1)
            if operation.recovery_reference:
                number = parse_issue_reference(
                    operation.recovery_reference,
                    expected_repository=canonical,
                )
                row = client.get_issue(
                    installation_token=token,
                    owner=owner,
                    name=name,
                    number=number,
                )
                body = row.get("body")
                if (
                    "pull_request" in row
                    or not isinstance(body, str)
                    or marker_for(operation.pk) not in body
                ):
                    return []
                return [row]
            matches: list[dict[str, object]] = []
            page = 1
            while True:
                rows, has_next = client.list_issues(
                    installation_token=token,
                    owner=owner,
                    name=name,
                    page=page,
                )
                for row in rows:
                    if "pull_request" in row:
                        continue
                    body = row.get("body")
                    if isinstance(body, str) and marker_for(operation.pk) in body:
                        matches.append(row)
                if not has_next:
                    return matches
                page += 1
                if page > 1000:
                    raise RuntimeError("Issue pagination exceeded its safety limit.")
        finally:
            client.revoke_installation_token(token=token)


@shared_task
def reconcile_github_issue_create(operation_id: str) -> None:
    operation_id_uuid = UUID(operation_id)
    hint = (
        ExternalOperation.objects.filter(pk=operation_id_uuid).select_related("connection").first()
    )
    if hint is None or hint.state != ExternalOperation.State.UNCERTAIN:
        return
    try:
        matches = _recover(hint)
    except Exception:
        return
    if len(matches) != 1:
        return
    try:
        snapshot = parse_issue_payload(matches[0], error=IssueLinkError)
    except IssueLinkError:
        return
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=hint.workspace_id)
        connection = Connection.objects.select_for_update().get(pk=hint.connection_id)
        problem = Problem.objects.select_for_update().get(
            pk=hint.problem_id, workspace_id=hint.workspace_id
        )
        operation = ExternalOperation.objects.select_for_update().get(pk=operation_id_uuid)
        if operation.state != ExternalOperation.State.UNCERTAIN:
            return
        if (
            connection.binding_revision != operation.binding_revision
            or connection.repository_id != operation.repository_id
            or EngineeringIssue.objects.filter(problem=problem, active=True).exists()
        ):
            operation.remote_issue_id = snapshot.issue_id
            operation.remote_number = snapshot.number
            operation.remote_url = snapshot.url
            operation.safe_error = "recovered_binding_conflict"
            operation.save(
                update_fields=["remote_issue_id", "remote_number", "remote_url", "safe_error"]
            )
            return
        member = Membership.objects.get(
            pk=operation.requester_id, workspace_id=operation.workspace_id
        )
        issue = _supersede_and_create(
            actor=member,
            problem=problem,
            connection=connection,
            snapshot=snapshot,
            now=timezone.now(),
            action=Activity.Action.ENGINEERING_ISSUE_CREATED,
        )
        operation.state = ExternalOperation.State.SUCCEEDED
        operation.remote_issue_id = issue.issue_id
        operation.remote_number = issue.number
        operation.remote_url = issue.url
        operation.completed_at = timezone.now()
        operation.safe_error = ""
        operation.save(
            update_fields=[
                "state",
                "remote_issue_id",
                "remote_number",
                "remote_url",
                "completed_at",
                "safe_error",
            ]
        )
