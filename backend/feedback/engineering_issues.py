"""Linking, creating, and syncing the GitHub issue for a problem."""

from datetime import datetime
from uuid import UUID, uuid4

import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Membership
from connections.errors import PROVIDER_ERRORS
from connections.models import Connection
from feedback.errors import (
    ConnectionNotReady,
    IssueAlreadyLinked,
    IssueAlreadyLinkedElsewhere,
    IssueCreationUncertain,
    IssueProviderUnavailable,
    IssueReferenceRejected,
    TitleRequired,
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
from integrations.github_app.client import GitHubAppClient
from integrations.github_app.issues import (
    EngineeringIssueSnapshot,
    IssueLinkError,
    parse_issue_payload,
    provider_time,
    resolve_issue_link,
)
from integrations.github_app.settings import github_client
from integrations.github_app.webhooks import InstallationEvent, IssueEvent, IssueStateOutcome
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
        installation_id=int(connection.external_id), repository=name
    )
    return token


def link_issue(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    reference: str,
    now: datetime | None = None,
) -> EngineeringIssue:
    current = now or timezone.now()
    problem = get_problem(actor=actor, problem_id=problem_id)
    require_version(row=problem, expected_version=expected_version)
    connection = _active_github_connection(actor)
    try:
        with github_client() as client:
            token = _installation_token(client, connection)
            snapshot = resolve_issue_link(
                client,
                installation_token=token,
                expected_repository=connection.repository,
                reference=reference,
            )
    except IssueLinkError as error:
        raise IssueReferenceRejected(detail=str(error)) from error
    except PROVIDER_ERRORS as error:
        raise IssueProviderUnavailable() from error

    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        return _supersede_and_create(
            actor=actor,
            problem=problem,
            connection=connection,
            snapshot=snapshot,
            now=current,
            action=Activity.Action.ENGINEERING_ISSUE_LINKED,
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


def create_issue(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    title: str,
    body: str,
    now: datetime | None = None,
) -> EngineeringIssue:
    current = now or timezone.now()
    problem = get_problem(actor=actor, problem_id=problem_id)
    require_version(row=problem, expected_version=expected_version)
    clean_title = title.strip()
    if not clean_title:
        raise TitleRequired()
    connection = _active_github_connection(actor)
    operation_id = uuid4()
    # An opaque marker so a future reconciliation (#15/#18) can find an issue this
    # request created even if the response confirming it was lost to a timeout.
    published_body = f"{body}\n\n<!-- rescribo-operation:{operation_id} -->"
    owner, name = connection.repository.split("/", 1)
    try:
        with github_client() as client:
            token = _installation_token(client, connection)
            created = client.create_issue(
                installation_token=token,
                owner=owner,
                name=name,
                title=clean_title,
                body=published_body,
            )
    except httpx.TimeoutException as error:
        raise IssueCreationUncertain(operation_id=operation_id) from error
    except PROVIDER_ERRORS as error:
        raise IssueProviderUnavailable() from error
    snapshot = parse_issue_payload(created, error=IssueLinkError)

    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        return _supersede_and_create(
            actor=actor,
            problem=problem,
            connection=connection,
            snapshot=snapshot,
            now=current,
            action=Activity.Action.ENGINEERING_ISSUE_CREATED,
        )


def _supersede_and_create(
    *,
    actor: Membership,
    problem: Problem,
    connection: Connection,
    snapshot: EngineeringIssueSnapshot,
    now: datetime,
    action: str,
) -> EngineeringIssue:
    """Deactivate the problem's current active issue, if any, then link the new one.

    Relinking the same issue that is already active is a no-op error rather than a
    silent success, matching how the report-linking use case treats a repeat link.
    """
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
        raise IssueAlreadyLinked()
    if existing is not None:
        existing.active = False
        existing.unlinked_at = now
        existing.save(update_fields=["active", "unlinked_at"])
        write_activity(
            actor=actor,
            action=Activity.Action.ENGINEERING_ISSUE_UNLINKED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"issue_url": existing.url},
            now=now,
        )
    issue = EngineeringIssue(
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
        last_synced_at=now,
        created_by=actor,
        created_at=now,
    )
    try:
        with transaction.atomic():
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
    return issue


def _conflicting_link(
    *, actor: Membership, repository_id: str, issue_id: str
) -> IssueAlreadyLinkedElsewhere:
    other = (
        EngineeringIssue.objects.filter(
            workspace_id=actor.workspace_id,
            repository_id=repository_id,
            issue_id=issue_id,
            active=True,
        )
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
    """Apply a verified `issues` event to the matching active issue, if we track one.

    Missing connection or issue is a silent no-op: the delivery may be for an
    installation or issue this deployment never linked, which is not an error.
    """
    current = now or timezone.now()
    with transaction.atomic():
        connection = (
            Connection.objects.select_for_update()
            .filter(provider=Connection.Provider.GITHUB, external_id=installation_id)
            .first()
        )
        if connection is None:
            return
        issue = (
            EngineeringIssue.objects.select_for_update()
            .filter(
                workspace_id=connection.workspace_id,
                connection=connection,
                repository_id=connection.repository_id,
                number=event.number,
                active=True,
            )
            .first()
        )
        if issue is None:
            return
        try:
            with github_client() as client:
                token = _installation_token(client, connection)
                outcome = fetch_issue_event_outcome(
                    client,
                    installation_token=token,
                    expected_repository=connection.repository,
                    event=event,
                    stored_updated_at=issue.provider_updated_at.isoformat(),
                )
        except PROVIDER_ERRORS:
            issue.sync_error = "provider_unavailable"
            issue.last_synced_at = current
            issue.save(update_fields=["sync_error", "last_synced_at"])
            return
        _apply_issue_outcome(issue=issue, outcome=outcome, now=current)


def _apply_issue_outcome(
    *, issue: EngineeringIssue, outcome: IssueStateOutcome, now: datetime
) -> None:
    if outcome.access == "access_lost":
        issue.access = EngineeringIssue.Access.ACCESS_LOST
        issue.last_synced_at = now
        issue.sync_error = ""
        issue.save(update_fields=["access", "last_synced_at", "sync_error"])
        return
    issue.access = EngineeringIssue.Access.OK
    issue.last_synced_at = now
    issue.sync_error = ""
    update_fields = ["access", "last_synced_at", "sync_error"]
    if outcome.applied:
        assert outcome.snapshot is not None, "An applied outcome always carries a snapshot."
        issue.state = outcome.snapshot.state
        issue.state_reason = outcome.snapshot.state_reason or ""
        issue.provider_updated_at = provider_time(outcome.snapshot.updated_at)
        update_fields += ["state", "state_reason", "provider_updated_at"]
    issue.save(update_fields=update_fields)
    if outcome.applied:
        assert outcome.snapshot is not None
        _apply_problem_consequences(issue=issue, state=outcome.snapshot.state, now=now)


def _apply_problem_consequences(*, issue: EngineeringIssue, state: str, now: datetime) -> None:
    problem = Problem.objects.select_for_update().get(pk=issue.problem_id)
    if state == EngineeringIssue.State.CLOSED:
        if problem.needs_review:
            return
        problem.needs_review = True
        finish_mutation(row=problem, now=now, update_fields=["needs_review"])
        write_system_activity(
            workspace_id=problem.workspace_id,
            actor_system=SYSTEM_ACTOR,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"fields": ["needs_review"], "reason": "issue_closed"},
            now=now,
        )
        return
    if state != EngineeringIssue.State.OPEN:
        return
    changed = []
    if not problem.needs_review:
        problem.needs_review = True
        changed.append("needs_review")
    reopened_a_fix = problem.state == Problem.State.FIX_AVAILABLE
    if reopened_a_fix:
        problem.state = Problem.State.IN_PROGRESS
        changed.append("state")
    if not changed:
        return
    finish_mutation(row=problem, now=now, update_fields=changed)
    if reopened_a_fix:
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
        metadata={"fields": changed, "reason": "issue_reopened"},
        now=now,
    )


_INSTALLATION_ACCESS: dict[str, tuple[str, str, str]] = {
    # action -> (connection error_code, connection status, issue access)
    "deleted": ("access_lost", Connection.Status.ERROR, EngineeringIssue.Access.ACCESS_LOST),
    "suspend": (
        "installation_suspended",
        Connection.Status.ERROR,
        EngineeringIssue.Access.SUSPENDED,
    ),
    "removed": ("access_lost", Connection.Status.ERROR, EngineeringIssue.Access.ACCESS_LOST),
}


def apply_installation_webhook(
    *, installation_id: str, event: InstallationEvent, now: datetime | None = None
) -> None:
    """Apply an installation/installation_repositories event that signals access loss.

    `unsuspend` and `new_permissions_accepted` are not handled here: we do not
    optimistically mark a connection healthy without reconfirming it, which the
    next reconciliation pass or a manual refresh already does.
    """
    mapping = _INSTALLATION_ACCESS.get(event.action)
    if mapping is None:
        return
    error_code, status, issue_access = mapping
    current = now or timezone.now()
    with transaction.atomic():
        connection = (
            Connection.objects.select_for_update()
            .filter(provider=Connection.Provider.GITHUB, external_id=installation_id)
            .first()
        )
        if connection is None:
            return
        connection.status = status
        connection.error_code = error_code
        connection.version += 1
        connection.save(update_fields=["status", "error_code", "version"])
        EngineeringIssue.objects.filter(
            workspace_id=connection.workspace_id, connection=connection, active=True
        ).update(access=issue_access, last_synced_at=current)
