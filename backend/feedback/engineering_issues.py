"""Linking, creating, and syncing the GitHub issue for a problem."""

import random
from dataclasses import replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Membership, Workspace
from connections.errors import PROVIDER_ERRORS
from connections.models import Connection
from feedback.errors import (
    ConnectionNotReady,
    IssueAlreadyLinked,
    IssueAlreadyLinkedElsewhere,
    IssueProviderUnavailable,
    IssueReferenceRejected,
    NotFound,
)
from feedback.models import Activity, EngineeringIssue, Problem, Report
from feedback.models import ReportNotificationOperation as Operation
from feedback.notifications import invalidate_pending_notifications
from feedback.problem_reads import get_problem
from feedback.services import (
    finish_mutation,
    locked_problem,
    require_version,
    write_activity,
    write_system_activity,
)
from integrations.github_app.client import GitHubAPIError, GitHubAppClient
from integrations.github_app.issues import (
    EngineeringIssueSnapshot,
    IssueLinkError,
    provider_time,
    resolve_issue_link,
)
from integrations.github_app.settings import github_client
from integrations.github_app.webhooks import InstallationEvent, IssueEvent
from integrations.github_app.webhooks import apply_issue_event as fetch_issue_event_outcome

SYSTEM_ACTOR = "github_webhook"


def _active_github_connection(actor: Membership) -> Connection:
    connection = Connection.objects.filter(
        workspace_id=actor.workspace_id, provider=Connection.Provider.GITHUB
    ).first()
    if (
        connection is None
        or connection.status != Connection.Status.ACTIVE
        or not connection.external_id
    ):
        raise ConnectionNotReady()
    return connection


def _installation_token(client: GitHubAppClient, connection: Connection) -> str:
    _, name = connection.repository.split("/", 1)
    token, _ = client.create_installation_token(
        installation_id=int(connection.external_id), repository_id=connection.repository_id
    )
    return token


def link_issue(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    reference: str,
    replace: bool = False,
    now: datetime | None = None,
) -> EngineeringIssue:
    current = now or timezone.now()
    problem = get_problem(actor=actor, problem_id=problem_id)
    require_version(row=problem, expected_version=expected_version)
    connection = _active_github_connection(actor)
    selected_binding = (
        connection.pk,
        connection.binding_revision,
        connection.repository_id,
        connection.repository,
    )
    try:
        with github_client() as client:
            token = _installation_token(client, connection)
            repository = client.get_repository_by_id(
                installation_token=token,
                repository_id=connection.repository_id,
            )
            canonical = repository.get("full_name")
            if (
                str(repository.get("id")) != connection.repository_id
                or not isinstance(canonical, str)
                or canonical.count("/") != 1
            ):
                raise IssueLinkError("The selected repository identity changed.")
            snapshot = resolve_issue_link(
                client,
                installation_token=token,
                expected_repository=canonical,
                expected_repository_id=connection.repository_id,
                reference=reference,
            )
    except IssueLinkError as error:
        raise IssueReferenceRejected(detail=str(error)) from error
    except PROVIDER_ERRORS as error:
        raise IssueProviderUnavailable() from error

    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        connection = Connection.objects.select_for_update().get(pk=connection.pk)
        if (
            selected_binding
            != (
                connection.pk,
                connection.binding_revision,
                connection.repository_id,
                connection.repository,
            )
            or connection.status != Connection.Status.ACTIVE
        ):
            raise IssueProviderUnavailable()
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        from operations.models import ExternalOperation

        if ExternalOperation.objects.filter(
            problem=problem,
            state__in=["queued", "running", "uncertain"],
        ).exists():
            raise IssueAlreadyLinked()
        ExternalOperation.objects.filter(
            problem=problem,
            state=ExternalOperation.State.DRAFT,
        ).update(
            state=ExternalOperation.State.CANCELLED, safe_error="issue_linked", completed_at=current
        )
        return _supersede_and_create(
            actor=actor,
            problem=problem,
            connection=connection,
            snapshot=snapshot,
            now=current,
            action=Activity.Action.ENGINEERING_ISSUE_LINKED,
            replace=replace,
        )


def preview_issue(*, actor: Membership, problem_id: UUID) -> dict[str, str]:
    problem = get_problem(actor=actor, problem_id=problem_id)
    return {"title": problem.title, "body": _default_body(problem)}


def _default_body(problem: Problem) -> str:
    link = f"{settings.RESCRIBO_PUBLIC_BASE_URL}/problems/{problem.pk}"
    summary = problem.summary.strip()
    parts = [summary] if summary else []
    parts.append(f"View in Rescribo: {link}")
    return "\n\n".join(parts)


def refresh_issue(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_issue_id: UUID,
    expected_version: int | None = None,
) -> EngineeringIssue:
    problem = get_problem(actor=actor, problem_id=problem_id)
    if expected_version is not None:
        require_version(row=problem, expected_version=expected_version)
    issue = (
        EngineeringIssue.objects.filter(
            workspace_id=actor.workspace_id, problem=problem, active=True
        )
        .select_related("connection")
        .first()
    )
    if issue is None:
        raise NotFound(record="engineering_issue")
    if issue.pk != expected_issue_id:
        raise IssueAlreadyLinked()
    if issue.connection.status != Connection.Status.ACTIVE:
        raise ConnectionNotReady()
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        connection = Connection.objects.select_for_update().get(pk=issue.connection_id)
        locked_problem = Problem.objects.select_for_update().get(pk=problem.pk)
        locked_issue = EngineeringIssue.objects.select_for_update().get(pk=issue.pk)
        if expected_version is not None:
            require_version(row=locked_problem, expected_version=expected_version)
        if not locked_issue.active or locked_issue.pk != expected_issue_id:
            raise IssueAlreadyLinked()
        if connection.status != Connection.Status.ACTIVE:
            raise ConnectionNotReady()
        if (
            locked_issue.sync_requested_generation <= locked_issue.sync_completed_generation
            and not locked_issue.sync_lease_token
        ):
            locked_issue.sync_requested_generation += 1
            locked_issue.save(update_fields=["sync_requested_generation"])
        generation = locked_issue.sync_requested_generation
        transaction.on_commit(lambda: _dispatch_issue_sync(locked_issue.pk))
    locked_issue.sync_requested_generation = generation
    return locked_issue


def _dispatch_issue_sync(issue_id: UUID) -> None:
    try:
        from feedback.tasks import sync_github_issue

        sync_github_issue.delay(str(issue_id))
    except Exception:
        return


def _supersede_and_create(
    *,
    actor: Membership,
    problem: Problem,
    connection: Connection,
    snapshot: EngineeringIssueSnapshot,
    now: datetime,
    action: str,
    replace: bool = True,
) -> EngineeringIssue:
    """Deactivate the problem's current active issue, if any, then link the new one.

    Relinking the same issue that is already active is a no-op error rather than a
    silent success, matching how the report-linking use case treats a repeat link.
    """
    if snapshot.repository_id != connection.repository_id:
        raise IssueReferenceRejected(detail="The issue belongs to a different repository identity.")
    if connection.repository != snapshot.repository_name:
        connection.repository = snapshot.repository_name
        connection.save(update_fields=["repository"])
    existing = (
        EngineeringIssue.objects.select_for_update()
        .filter(workspace_id=actor.workspace_id, problem=problem, active=True)
        .first()
    )
    if (
        existing is not None
        and existing.repository_id == connection.repository_id
        and existing.issue_id == snapshot.issue_id
    ):
        return existing
    if existing is not None and not replace:
        raise IssueAlreadyLinked()
    if (
        existing is None
        and not replace
        and EngineeringIssue.objects.filter(
            workspace_id=actor.workspace_id, problem=problem, active=True
        ).exists()
    ):
        raise IssueAlreadyLinked()
    if existing is not None:
        existing.active = False
        existing.unlinked_at = now
        existing.save(update_fields=["active", "unlinked_at"])
        for report in Report.objects.select_for_update().filter(problem=problem).order_by("id"):
            invalidate_pending_notifications(report=report, reason="issue_relinked", now=now)
        write_activity(
            actor=actor,
            action=Activity.Action.ENGINEERING_ISSUE_UNLINKED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"issue_url": existing.url},
            now=now,
        )
    historical = (
        EngineeringIssue.objects.select_for_update()
        .select_related("problem")
        .filter(
            workspace_id=actor.workspace_id,
            issue_id=snapshot.issue_id,
        )
        .first()
    )
    if historical is not None and historical.problem_id != problem.pk:
        raise IssueAlreadyLinkedElsewhere(
            problem_id=historical.problem_id,
            problem_title=historical.problem.title,
        )
    issue = historical or EngineeringIssue(
        workspace_id=actor.workspace_id,
        problem=problem,
        connection=connection,
        repository_id=connection.repository_id,
        issue_id=snapshot.issue_id,
        number=snapshot.number,
        url=snapshot.url,
        title=snapshot.title,
        state=snapshot.state,
        state_reason=snapshot.state_reason or "",
        provider_updated_at=provider_time(snapshot.updated_at),
        last_attempted_sync_at=now,
        last_successful_sync_at=now,
        connection_binding_revision=connection.binding_revision,
        connection_installation_id=connection.external_id,
        last_synced_at=now,
        created_by=actor,
        created_at=now,
    )
    if historical is not None:
        historical.connection = connection
        historical.repository_id = connection.repository_id
        historical.number = snapshot.number
        historical.url = snapshot.url
        historical.title = snapshot.title
        historical.state = snapshot.state
        historical.state_reason = snapshot.state_reason or ""
        historical.provider_updated_at = provider_time(snapshot.updated_at)
        historical.connection_binding_revision = connection.binding_revision
        historical.connection_installation_id = connection.external_id
        historical.active = True
        historical.unlinked_at = None
        historical.access = EngineeringIssue.Access.OK
        historical.sync_error = ""
        historical.last_attempted_sync_at = now
        historical.last_successful_sync_at = now
        historical.last_synced_at = now
        historical.save()
    else:
        try:
            issue.save()
        except IntegrityError as error:
            raise _conflicting_link(
                actor=actor, repository_id=connection.repository_id, issue_id=snapshot.issue_id
            ) from error
    write_activity(
        actor=actor,
        action=action,
        record_type=Activity.RecordType.PROBLEM,
        record_id=problem.pk,
        metadata={"issue_url": issue.url, "issue_number": issue.number},
        now=now,
    )
    if issue.state == EngineeringIssue.State.CLOSED:
        _apply_problem_consequences(
            issue=issue,
            problem=problem,
            state=issue.state,
            previous_state=EngineeringIssue.State.OPEN,
            now=now,
        )
    return issue


def _conflicting_link(
    *, actor: Membership, repository_id: str, issue_id: str
) -> IssueAlreadyLinkedElsewhere:
    other = (
        EngineeringIssue.objects.filter(workspace_id=actor.workspace_id, issue_id=issue_id)
        .select_related("problem")
        .first()
    )
    assert other is not None, "Unique violation without a conflicting active row."
    return IssueAlreadyLinkedElsewhere(
        problem_id=other.problem_id, problem_title=other.problem.title
    )


def apply_issue_webhook(
    *, installation_id: str, event: IssueEvent, now: datetime | None = None
) -> None:
    """Fetch current state outside row locks and apply it under a fenced issue lease."""
    current = now or timezone.now()
    connections = Connection.objects.filter(
        provider=Connection.Provider.GITHUB, external_id=installation_id
    ).order_by("workspace_id", "id")
    for candidate in connections:
        candidates = EngineeringIssue.objects.filter(
            workspace_id=candidate.workspace_id,
            connection_id=candidate.pk,
            active=True,
        )
        if event.issue_id:
            candidates = candidates.filter(issue_id=event.issue_id)
        else:
            candidates = candidates.filter(number=event.number)
        if event.repository_id and event.action != "transferred":
            candidates = candidates.filter(repository_id=event.repository_id)
        for hint in candidates.values("pk", "problem_id", "workspace_id"):
            claim = uuid4()
            target_generation = 0
            with transaction.atomic():
                Workspace.objects.select_for_update().get(pk=hint["workspace_id"])
                connection = Connection.objects.select_for_update().get(pk=candidate.pk)
                problem = Problem.objects.select_for_update().get(pk=hint["problem_id"])
                issue = EngineeringIssue.objects.select_for_update().get(pk=hint["pk"])
                issue.sync_requested_generation += 1
                if (
                    issue.sync_lease_token
                    and issue.sync_lease_expires_at
                    and issue.sync_lease_expires_at > current
                ):
                    issue.save(update_fields=["sync_requested_generation"])
                    continue
                if (
                    issue.connection_installation_id != connection.external_id
                    or issue.repository_id != connection.repository_id
                ):
                    issue.access = (
                        EngineeringIssue.Access.DISCONNECTED
                        if connection.status == Connection.Status.DISCONNECTED
                        else EngineeringIssue.Access.INACCESSIBLE
                    )
                    issue.sync_error = "binding_changed"
                    issue.sync_completed_generation = issue.sync_requested_generation
                    issue.save(
                        update_fields=[
                            "access",
                            "sync_error",
                            "sync_requested_generation",
                            "sync_completed_generation",
                        ]
                    )
                    continue
                # A transfer is not followed into another repository. Stable issue ID
                # lets us mark the old link inaccessible even when its repo ID changed.
                if (
                    event.action == "transferred"
                    and event.repository_id
                    and event.repository_id != issue.repository_id
                ):
                    issue.access = EngineeringIssue.Access.INACCESSIBLE
                    issue.sync_error = "issue_transferred"
                    issue.sync_completed_generation = issue.sync_requested_generation
                    issue.save(
                        update_fields=[
                            "access",
                            "sync_error",
                            "sync_requested_generation",
                            "sync_completed_generation",
                        ]
                    )
                    continue
                if connection.status != Connection.Status.ACTIVE:
                    issue.access = (
                        EngineeringIssue.Access.DISCONNECTED
                        if connection.status == Connection.Status.DISCONNECTED
                        else EngineeringIssue.Access.SUSPENDED
                        if "suspend" in connection.error_code
                        else EngineeringIssue.Access.INACCESSIBLE
                    )
                    issue.sync_error = connection.error_code or "connection_unavailable"
                    issue.sync_completed_generation = issue.sync_requested_generation
                    issue.save(
                        update_fields=[
                            "access",
                            "sync_error",
                            "sync_requested_generation",
                            "sync_completed_generation",
                        ]
                    )
                    continue
                issue.sync_lease_token = claim
                issue.sync_lease_expires_at = current + timedelta(seconds=45)
                issue.sync_attempts += 1
                target_generation = issue.sync_requested_generation
                issue.last_attempted_sync_at = current
                issue.save(
                    update_fields=[
                        "sync_requested_generation",
                        "sync_lease_token",
                        "sync_lease_expires_at",
                        "last_attempted_sync_at",
                        "sync_attempts",
                    ]
                )

            try:
                with github_client() as client:
                    token = _installation_token(client, connection)
                    repository = client.get_repository_by_id(
                        installation_token=token,
                        repository_id=connection.repository_id,
                    )
                    canonical = repository.get("full_name")
                    if (
                        str(repository.get("id")) != connection.repository_id
                        or not isinstance(canonical, str)
                        or canonical.count("/") != 1
                    ):
                        raise GitHubAPIError("repository identity lookup", 404)
                    event_for_repository = event
                    if event.repository_id:
                        if event.repository_id != connection.repository_id:
                            raise GitHubAPIError("repository identity lookup", 404)
                        event_for_repository = replace(event, repository=canonical)
                    outcome = fetch_issue_event_outcome(
                        client,
                        installation_token=token,
                        expected_repository=canonical,
                        expected_repository_id=connection.repository_id,
                        event=event_for_repository,
                        stored_updated_at=issue.provider_updated_at.isoformat(),
                        stored_state=issue.state,
                    )
            except PROVIDER_ERRORS as error:
                rate_limited = isinstance(error, GitHubAPIError) and error.rate_limited
                _finish_issue_sync_failure(
                    issue_id=issue.pk,
                    connection_id=connection.pk,
                    problem_id=problem.pk,
                    workspace_id=connection.workspace_id,
                    claim=claim,
                    now=current,
                    error_code="rate_limited" if rate_limited else "provider_unavailable",
                    retry_after_seconds=(
                        error.retry_after_seconds
                        if isinstance(error, GitHubAPIError) and error.rate_limited
                        else None
                    ),
                )
                continue

            with transaction.atomic():
                Workspace.objects.select_for_update().get(pk=connection.workspace_id)
                locked_connection = Connection.objects.select_for_update().get(pk=connection.pk)
                problem = Problem.objects.select_for_update().get(pk=problem.pk)
                issue = EngineeringIssue.objects.select_for_update().get(pk=issue.pk)
                if issue.sync_lease_token != claim:
                    continue
                if (
                    issue.connection_installation_id != locked_connection.external_id
                    or locked_connection.repository_id != issue.repository_id
                ):
                    issue.access = EngineeringIssue.Access.INACCESSIBLE
                    issue.sync_error = "binding_changed"
                    issue.sync_lease_token = None
                    issue.sync_lease_expires_at = None
                    issue.save(
                        update_fields=[
                            "access",
                            "sync_error",
                            "sync_lease_token",
                            "sync_lease_expires_at",
                        ]
                    )
                    continue
                previous_state = issue.state
                issue.access = (
                    EngineeringIssue.Access.INACCESSIBLE
                    if outcome.access == "access_lost"
                    else EngineeringIssue.Access.OK
                )
                if event.action == "deleted" and outcome.access == "access_lost":
                    issue.access = EngineeringIssue.Access.DELETED
                issue.last_synced_at = current
                issue.last_successful_sync_at = (
                    current if outcome.access == "ok" else issue.last_successful_sync_at
                )
                if outcome.access == "ok":
                    issue.sync_attempts = 0
                    issue.sync_retry_at = None
                issue.sync_error = "inaccessible" if outcome.access == "access_lost" else ""
                issue.sync_completed_generation = target_generation
                issue.sync_lease_token = None
                issue.sync_lease_expires_at = None
                update_fields = [
                    "access",
                    "last_synced_at",
                    "last_successful_sync_at",
                    "sync_error",
                    "sync_completed_generation",
                    "sync_attempts",
                    "sync_retry_at",
                    "sync_lease_token",
                    "sync_lease_expires_at",
                ]
                if outcome.applied and outcome.snapshot is not None:
                    issue.state = outcome.snapshot.state
                    issue.state_reason = outcome.snapshot.state_reason or ""
                    issue.title = outcome.snapshot.title
                    issue.url = outcome.snapshot.url
                    issue.provider_updated_at = provider_time(outcome.snapshot.updated_at)
                    update_fields += [
                        "state",
                        "state_reason",
                        "title",
                        "url",
                        "provider_updated_at",
                    ]
                issue.save(update_fields=update_fields)
                if outcome.access == "ok":
                    issue.connection_binding_revision = locked_connection.binding_revision
                    issue.connection_installation_id = locked_connection.external_id
                    update_fields.extend(
                        ["connection_binding_revision", "connection_installation_id"]
                    )
                    locked_connection.last_success_at = current
                    connection_fields = ["last_success_at"]
                    if (
                        outcome.snapshot
                        and locked_connection.repository != outcome.snapshot.repository_name
                    ):
                        locked_connection.repository = outcome.snapshot.repository_name
                        connection_fields.append("repository")
                    locked_connection.save(update_fields=connection_fields)
                state_changed = outcome.applied and issue.state != previous_state
                reopen_event_at = (
                    provider_time(event.updated_at) if event.action == "reopened" else None
                )
                if (
                    reopen_event_at is not None
                    and issue.last_applied_reopen_event_at is not None
                    and reopen_event_at <= issue.last_applied_reopen_event_at
                ):
                    reopen_event_at = None
                if (
                    state_changed
                    and previous_state == EngineeringIssue.State.CLOSED
                    and issue.state == EngineeringIssue.State.OPEN
                ):
                    reopen_event_at = (
                        provider_time(outcome.snapshot.updated_at) if outcome.snapshot else None
                    )
                if state_changed or reopen_event_at is not None:
                    _apply_problem_consequences(
                        issue=issue,
                        problem=problem,
                        state=issue.state,
                        previous_state=previous_state,
                        now=current,
                        reopen_event_at=reopen_event_at,
                    )


def _finish_issue_sync_failure(
    *,
    issue_id: UUID,
    connection_id: UUID,
    problem_id: UUID,
    workspace_id: UUID,
    claim: UUID,
    now: datetime,
    error_code: str,
    retry_after_seconds: int | None = None,
) -> None:
    with transaction.atomic():
        Workspace.objects.select_for_update().get(pk=workspace_id)
        Connection.objects.select_for_update().get(pk=connection_id)
        Problem.objects.select_for_update().get(pk=problem_id)
        issue = EngineeringIssue.objects.select_for_update().get(pk=issue_id)
        if issue.sync_lease_token != claim:
            return
        if error_code != "rate_limited":
            issue.access = EngineeringIssue.Access.INACCESSIBLE
        issue.sync_error = error_code
        delay = retry_after_seconds
        if delay is None:
            delay = min(3600, 2 ** min(issue.sync_attempts, 10))
        delay += random.randint(0, max(1, min(delay // 4, 60)))
        issue.sync_retry_at = now + timedelta(seconds=delay)
        issue.sync_lease_token = None
        issue.sync_lease_expires_at = None
        issue.save(
            update_fields=[
                "access",
                "sync_error",
                "sync_retry_at",
                "sync_lease_token",
                "sync_lease_expires_at",
            ]
        )


def _apply_problem_consequences(
    *,
    issue: EngineeringIssue,
    problem: Problem,
    state: str,
    previous_state: str,
    now: datetime,
    reopen_event_at: datetime | None = None,
) -> None:
    if state == EngineeringIssue.State.CLOSED and previous_state != EngineeringIssue.State.CLOSED:
        changed: list[str] = []
        if not problem.needs_review:
            problem.needs_review = True
            changed.append("needs_review")
        if changed:
            finish_mutation(row=problem, now=now, update_fields=changed)
        write_system_activity(
            workspace_id=problem.workspace_id,
            actor_system=SYSTEM_ACTOR,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"fields": changed or ["needs_review"], "reason": "issue_closed"},
            now=now,
        )
    if reopen_event_at is None:
        return
    if issue.last_applied_reopen_event_at and reopen_event_at <= issue.last_applied_reopen_event_at:
        return
    if problem.fix_confirmed_at and reopen_event_at <= problem.fix_confirmed_at:
        return
    issue.last_applied_reopen_event_at = reopen_event_at
    issue.save(update_fields=["last_applied_reopen_event_at"])
    changed = []
    if not problem.needs_review:
        problem.needs_review = True
        changed.append("needs_review")
    reopened_a_fix = problem.state == Problem.State.FIX_AVAILABLE
    if reopened_a_fix:
        problem.state = Problem.State.IN_PROGRESS
        changed.append("state")
    if changed:
        finish_mutation(row=problem, now=now, update_fields=changed)
    for report in Report.objects.select_for_update().filter(problem=problem).order_by("id"):
        invalidate_pending_notifications(
            report=report, reason=Operation.InvalidationReason.ISSUE_REOPENED, now=now
        )
    write_system_activity(
        workspace_id=problem.workspace_id,
        actor_system=SYSTEM_ACTOR,
        action=Activity.Action.PROBLEM_STATE_CHANGED
        if reopened_a_fix
        else Activity.Action.PROBLEM_UPDATED,
        record_type=Activity.RecordType.PROBLEM,
        record_id=problem.pk,
        metadata={
            "fields": changed or ["needs_review"],
            "reason": "issue_reopened",
            "provider_event_at": reopen_event_at.isoformat(),
        },
        now=now,
    )


def apply_installation_webhook(
    *, installation_id: str, event: InstallationEvent, now: datetime | None = None
) -> None:
    """Fan out lifecycle events only to connections bound to this installation."""
    current = now or timezone.now()
    connection_ids = (
        Connection.objects.filter(provider=Connection.Provider.GITHUB, external_id=installation_id)
        .order_by("workspace_id", "id")
        .values_list("pk", flat=True)
    )
    revalidate: list[str] = []
    for connection_id in connection_ids:
        hint = Connection.objects.filter(pk=connection_id).values("workspace_id").first()
        if hint is None:
            continue
        with transaction.atomic():
            Workspace.objects.select_for_update().get(pk=hint["workspace_id"])
            connection = Connection.objects.select_for_update().get(pk=connection_id)
            if event.action in {"unsuspend", "new_permissions_accepted"}:
                revalidate.append(str(connection.pk))
                continue
            if event.action == "added":
                if connection.repository_id in event.repositories_added_ids:
                    revalidate.append(str(connection.pk))
                continue
            issue_access: str | None = None
            if event.action == "deleted":
                connection.status = Connection.Status.ERROR
                connection.error_code = "access_lost"
                issue_access = EngineeringIssue.Access.ACCESS_LOST
            elif event.action == "suspend":
                connection.status = Connection.Status.ERROR
                connection.error_code = "installation_suspended"
                issue_access = EngineeringIssue.Access.SUSPENDED
            elif (
                event.action == "removed"
                and connection.repository_id in event.repositories_removed_ids
            ):
                connection.status = Connection.Status.ERROR
                connection.error_code = "repository_removed"
                issue_access = EngineeringIssue.Access.INACCESSIBLE
            if issue_access is None:
                continue
            connection.version += 1
            connection.save(update_fields=["status", "error_code", "version"])
            issue_hints = (
                EngineeringIssue.objects.filter(connection=connection, active=True)
                .order_by("problem_id", "pk")
                .values("pk", "problem_id")
            )
            for issue_hint in issue_hints:
                Problem.objects.select_for_update().get(pk=issue_hint["problem_id"])
                issue = EngineeringIssue.objects.select_for_update().get(pk=issue_hint["pk"])
                issue.access = issue_access
                issue.sync_error = connection.error_code
                issue.last_synced_at = current
                issue.save(update_fields=["access", "sync_error", "last_synced_at"])
    for revalidate_id in revalidate:
        try:
            from operations.tasks import revalidate_github_connection

            revalidate_github_connection.delay(revalidate_id)
        except Exception:
            # The next periodic reconciliation and manual refresh remain available.
            continue
