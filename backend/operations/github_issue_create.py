"""Persisted preview, approval, and recovery for GitHub issue creates."""

from datetime import timedelta
from uuid import UUID, uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import Membership, Workspace
from connections.models import Connection
from feedback.engineering_issues import default_issue_body, require_active_connection
from feedback.errors import (
    IssueAlreadyLinked,
    IssueCreateUnresolved,
    IssueOperationError,
    NotFound,
    VersionConflict,
)
from feedback.models import EngineeringIssue, Problem
from feedback.services import locked_problem, require_version
from integrations.github_app.issues import IssueLinkError, parse_issue_reference
from integrations.github_app.repository import OPERATION_LEASE_SECONDS
from operations.dispatch import dispatch_task
from operations.models import ExternalOperation

DRAFT_TTL = timedelta(minutes=15)
LEASE_TTL = timedelta(seconds=OPERATION_LEASE_SECONDS)
MARKER_PREFIX = "<!-- rescribo-operation:"


def marker_for(operation_id: UUID) -> str:
    return f"{MARKER_PREFIX}{operation_id} -->"


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
    draft_id: UUID | None = None,
) -> ExternalOperation:
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        connection = require_active_connection(
            Connection.objects.select_for_update()
            .filter(
                workspace_id=actor.workspace_id,
                provider=Connection.Provider.GITHUB,
            )
            .first()
        )
        problem = locked_problem(actor=actor, problem_id=problem_id)
        if not Membership.objects.filter(
            pk=actor.pk, workspace_id=actor.workspace_id, is_active=True
        ).exists():
            raise PermissionDenied()
        require_version(row=problem, expected_version=expected_version)
        if EngineeringIssue.objects.filter(problem=problem, active=True).exists():
            raise IssueAlreadyLinked()
        if ExternalOperation.objects.filter(
            problem=problem,
            state__in=ExternalOperation.UNRESOLVED_STATES,
        ).exists():
            raise IssueCreateUnresolved()
        chosen_title = (title if title is not None else problem.title).strip()
        chosen_body = body if body is not None else default_issue_body(problem)
        if (
            not chosen_title
            or len(chosen_title) > ExternalOperation.TITLE_LIMIT
            or len(chosen_body) > ExternalOperation.BODY_LIMIT
        ):
            raise IssueOperationError(
                "invalid_issue_content",
                detail="Enter a title and body within the limits, without an operation marker.",
            )
        if MARKER_PREFIX in chosen_body:
            raise IssueOperationError(
                "invalid_issue_content",
                detail="Enter a title and body within the limits, without an operation marker.",
            )
        if draft_id is not None:
            operation = (
                ExternalOperation.objects.select_for_update()
                .filter(
                    pk=draft_id,
                    workspace_id=actor.workspace_id,
                    problem=problem,
                    requester=actor,
                    state=ExternalOperation.State.DRAFT,
                    expires_at__gt=timezone.now(),
                )
                .first()
            )
            if operation is None:
                raise NotFound(record="draft")
            operation.title = chosen_title
            operation.body = chosen_body
            operation.draft_version += 1
            operation.problem_version = problem.version
            operation.destination = connection.repository
            operation.repository_id = connection.repository_id
            operation.binding_revision = connection.binding_revision
            operation.expires_at = timezone.now() + DRAFT_TTL
            operation.save()
            return operation
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
        raise IssueOperationError(
            "approval_required", detail="Approve the exact preview before publishing."
        )
    hint = (
        ExternalOperation.objects.filter(pk=draft_id, problem_id=problem_id)
        .values("workspace_id", "connection_id")
        .first()
    )
    if hint is None or hint["workspace_id"] != actor.workspace_id:
        raise NotFound(record="operation")
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
                raise IssueOperationError(
                    "operation_conflict", detail="This approval belongs to another draft or member."
                )
            if (
                operation.state != ExternalOperation.State.DRAFT
                or operation.requester_id != actor.pk
            ):
                raise NotFound(record="operation")
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
                raise VersionConflict(current=problem)
            elif (
                connection.status != Connection.Status.ACTIVE
                or connection.binding_revision != operation.binding_revision
                or connection.repository != operation.destination
            ):
                raise IssueOperationError(
                    "binding_changed",
                    detail="The selected repository changed. Prepare a new preview.",
                )
            elif EngineeringIssue.objects.filter(problem=problem, active=True).exists():
                raise IssueAlreadyLinked()
            else:
                operation.state = ExternalOperation.State.QUEUED
                operation.approved_at = now
                operation.due_at = now
                operation.save(update_fields=["state", "approved_at", "due_at"])
                operation_id = operation.pk
                transaction.on_commit(
                    lambda: dispatch_task(
                        "operations.tasks.process_github_issue_create", str(operation_id)
                    )
                )
        if expired:
            raise IssueOperationError(
                "draft_expired", detail="This preview expired. Prepare a new preview."
            )
        return operation
    except IntegrityError as error:
        raise IssueCreateUnresolved() from error


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
        raise NotFound(record="operation") from error


def request_recovery(
    *,
    actor: Membership,
    problem_id: UUID,
    operation_id: UUID,
    reference: str = "",
) -> ExternalOperation:
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        operation = _locked_uncertain_operation(
            actor=actor, problem_id=problem_id, operation_id=operation_id
        )
        if operation.recovery_requested or operation.lease_token:
            return operation
        if reference:
            try:
                parse_issue_reference(
                    reference, expected_repository=operation.connection.repository
                )
            except IssueLinkError as error:
                raise IssueOperationError("issue_reference_rejected", detail=str(error)) from error
        operation.recovery_reference = reference
        operation.recovery_requested = True
        operation.safe_error = ""
        operation.due_at = max(timezone.now(), operation.due_at)
        operation.save(
            update_fields=["recovery_reference", "recovery_requested", "safe_error", "due_at"]
        )
        transaction.on_commit(
            lambda: dispatch_task(
                "operations.tasks.reconcile_github_issue_create", str(operation.pk)
            )
        )
        return operation


def abandon_creation(
    *,
    actor: Membership,
    problem_id: UUID,
    operation_id: UUID,
    reason: str,
) -> ExternalOperation:
    if not reason.strip():
        raise IssueOperationError(
            "reason_required", detail="Record what you checked before stopping recovery."
        )
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        operation = _locked_uncertain_operation(
            actor=actor, problem_id=problem_id, operation_id=operation_id
        )
        operation.state = ExternalOperation.State.CANCELLED
        operation.resolved_by = actor
        operation.resolution_reason = reason.strip()
        operation.completed_at = timezone.now()
        operation.safe_error = "manually_resolved"
        operation.recovery_requested = False
        operation.recovery_reference = ""
        operation.lease_token = None
        operation.lease_expires_at = None
        operation.save()
        return operation


def _locked_uncertain_operation(
    *,
    actor: Membership,
    problem_id: UUID,
    operation_id: UUID,
) -> ExternalOperation:
    if not Membership.objects.filter(
        pk=actor.pk, workspace_id=actor.workspace_id, is_active=True
    ).exists():
        raise PermissionDenied()
    operation = (
        ExternalOperation.objects.select_for_update()
        .filter(
            pk=operation_id,
            workspace_id=actor.workspace_id,
            problem_id=problem_id,
        )
        .first()
    )
    if operation is None:
        raise NotFound(record="operation")
    if operation.state != ExternalOperation.State.UNCERTAIN:
        raise IssueOperationError(
            "operation_not_uncertain",
            detail="Only an uncertain creation can be recovered or stopped.",
        )
    return operation
