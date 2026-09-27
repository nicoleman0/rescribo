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
from feedback.models import Activity, EngineeringIssue, Problem
from feedback.problem_reads import get_problem
from feedback.services import locked_problem, require_version, write_activity
from integrations.github_app.client import GitHubAppClient
from integrations.github_app.issues import (
    EngineeringIssueSnapshot,
    IssueLinkError,
    parse_issue_payload,
    provider_time,
    resolve_issue_link,
)
from integrations.github_app.settings import github_client


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
