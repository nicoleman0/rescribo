"""Persisted preview, approval, and recovery for GitHub issue creates."""

from datetime import timedelta
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from accounts.models import Membership, Workspace
from connections.models import Connection
from feedback.models import EngineeringIssue, Problem
from operations.models import ExternalOperation

DRAFT_TTL = timedelta(minutes=15)
LEASE_TTL = timedelta(seconds=45)


def marker_for(operation_id: UUID) -> str:
    return f"<!-- rescribo-operation:{operation_id} -->"


def exact_body(operation: ExternalOperation) -> str:
    marker = marker_for(operation.pk)
    clean = operation.body.replace(marker, "").rstrip()
    return f"{clean}\n\n{marker}" if clean else marker


def create_draft(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    title: str | None = None,
    body: str | None = None,
) -> ExternalOperation:
    if not Membership.objects.filter(
        pk=actor.pk, workspace_id=actor.workspace_id, is_active=True
    ).exists():
        raise PermissionDenied()
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        connection = (
            Connection.objects.select_for_update()
            .filter(
                workspace_id=actor.workspace_id,
                provider=Connection.Provider.GITHUB,
            )
            .first()
        )
        if (
            connection is None
            or connection.status != Connection.Status.ACTIVE
            or not connection.external_id
        ):
            raise ValidationError({"reason": "connection_not_ready"})
        problem = (
            Problem.objects.select_for_update()
            .filter(
                pk=problem_id,
                workspace_id=actor.workspace_id,
            )
            .first()
        )
        if problem is None:
            raise NotFound()
        if not Membership.objects.filter(
            pk=actor.pk, workspace_id=actor.workspace_id, is_active=True
        ).exists():
            raise PermissionDenied()
        if problem.version != expected_version:
            raise ValidationError(
                {"reason": "version_conflict", "current_version": str(problem.version)}
            )
        if EngineeringIssue.objects.filter(problem=problem, active=True).exists():
            raise ValidationError({"reason": "issue_already_linked"})
        if ExternalOperation.objects.filter(
            problem=problem,
            state__in=["queued", "running", "uncertain"],
        ).exists():
            raise ValidationError({"reason": "issue_create_unresolved"})
        summary = problem.summary.strip()
        default_body = "\n\n".join(
            filter(
                None,
                [
                    summary,
                    f"View in Rescribo: {settings.RESCRIBO_PUBLIC_BASE_URL}/problems/{problem.pk}",
                ],
            )
        )
        chosen_title = (title if title is not None else problem.title).strip()
        chosen_body = body if body is not None else default_body
        if not chosen_title or len(chosen_title) > 256 or len(chosen_body) > 10000:
            raise ValidationError({"reason": "invalid_issue_content"})
        if "<!-- rescribo-operation:" in chosen_body:
            raise ValidationError({"reason": "invalid_issue_content"})
        operation = ExternalOperation.objects.create(
            kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
            workspace_id=actor.workspace_id,
            connection=connection,
            problem=problem,
            requester=actor,
            action_key=uuid4(),
            title=chosen_title,
            body=chosen_body,
            destination=connection.repository,
            repository_id=connection.repository_id,
            problem_version=problem.version,
            binding_revision=connection.binding_revision,
            expires_at=timezone.now() + DRAFT_TTL,
        )
        return operation


def approve_draft(
    *,
    actor: Membership,
    problem_id: UUID,
    draft_id: UUID,
    draft_version: int,
    approved: bool,
) -> ExternalOperation:
    if approved is not True:
        raise ValidationError({"reason": "approval_required"})
    hint = (
        ExternalOperation.objects.filter(pk=draft_id, problem_id=problem_id)
        .values("workspace_id", "connection_id")
        .first()
    )
    if hint is None or hint["workspace_id"] != actor.workspace_id:
        raise NotFound()
    expired = False
    try:
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=actor.workspace_id)
            connection = Connection.objects.select_for_update().get(pk=hint["connection_id"])
            problem = Problem.objects.select_for_update().get(
                pk=problem_id, workspace_id=actor.workspace_id
            )
            operation = ExternalOperation.objects.select_for_update().get(
                pk=draft_id,
                problem=problem,
                workspace_id=actor.workspace_id,
            )
            if not Membership.objects.filter(
                pk=actor.pk, workspace_id=actor.workspace_id, is_active=True
            ).exists():
                raise PermissionDenied()
            if operation.state in {"queued", "running", "succeeded", "uncertain"}:
                if operation.requester_id == actor.pk and operation.draft_version == draft_version:
                    return operation
                raise ValidationError({"reason": "operation_conflict"})
            if (
                operation.state != ExternalOperation.State.DRAFT
                or operation.requester_id != actor.pk
            ):
                raise NotFound()
            now = timezone.now()
            if operation.expires_at is None or operation.expires_at <= now:
                operation.state = ExternalOperation.State.CANCELLED
                operation.safe_error = "draft_expired"
                operation.completed_at = now
                operation.save(update_fields=["state", "safe_error", "completed_at"])
                expired = True
            elif (
                operation.draft_version != draft_version
                or problem.version != operation.problem_version
            ):
                raise ValidationError({"reason": "version_conflict"})
            elif (
                connection.status != Connection.Status.ACTIVE
                or connection.binding_revision != operation.binding_revision
                or connection.repository != operation.destination
            ):
                raise ValidationError({"reason": "binding_changed"})
            elif EngineeringIssue.objects.filter(problem=problem, active=True).exists():
                raise ValidationError({"reason": "issue_already_linked"})
            elif not expired:
                operation.state = ExternalOperation.State.QUEUED
                operation.approved_at = now
                operation.due_at = now
                operation.save(update_fields=["state", "approved_at", "due_at"])
                operation_id = operation.pk
                transaction.on_commit(lambda: _dispatch_create(operation_id))
        if expired:
            raise ValidationError({"reason": "draft_expired"})
        return operation
    except IntegrityError as error:
        raise ValidationError({"reason": "issue_create_unresolved"}) from error


def _dispatch_create(operation_id: UUID) -> None:
    try:
        from operations.tasks import process_github_issue_create

        process_github_issue_create.delay(str(operation_id))
    except Exception:
        # The due-time dispatcher retries committed work if the broker is down.
        return


def operation_for_member(
    *, actor: Membership, problem_id: UUID, operation_id: UUID
) -> ExternalOperation:
    try:
        return ExternalOperation.objects.get(
            pk=operation_id,
            workspace_id=actor.workspace_id,
            problem_id=problem_id,
        )
    except ExternalOperation.DoesNotExist as error:
        raise NotFound() from error
