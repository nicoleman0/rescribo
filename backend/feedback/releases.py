from datetime import datetime
from uuid import UUID

import httpx
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Membership
from accounts.services import lock_workspace
from connections.models import Connection
from feedback.engineering_issues import _active_github_connection, refuse_demo
from feedback.errors import (
    ConnectionNotReady,
    InvalidTransition,
    ReleaseAccessMissing,
    ReleaseConnectionNotReady,
    ReleaseNotFound,
    ReleaseProviderUnavailable,
)
from feedback.models import Activity, FixRelease, Problem
from feedback.problem_reads import get_problem
from feedback.services import finish_mutation, locked_problem, require_version, write_activity
from integrations.github_app.client import INSTALLATION_TOKEN_OPERATION, GitHubAPIError
from integrations.github_app.permissions import RELEASE_PERMISSIONS
from integrations.github_app.releases import (
    ReleaseAccessMissing as ProviderAccessMissing,
)
from integrations.github_app.releases import (
    ReleaseNotFound as ProviderReleaseNotFound,
)
from integrations.github_app.releases import (
    ReleaseSnapshot,
    get_release,
    list_releases,
)
from integrations.github_app.repository import selected_repository
from integrations.github_app.settings import github_client


def _provider_error(error: Exception) -> Exception:
    if isinstance(error, ProviderAccessMissing):
        return ReleaseAccessMissing()
    if isinstance(error, ProviderReleaseNotFound):
        return ReleaseNotFound()
    if (
        isinstance(error, GitHubAPIError)
        and error.operation == INSTALLATION_TOKEN_OPERATION
        and error.status_code == 422
    ):
        return ReleaseAccessMissing()
    return ReleaseProviderUnavailable()


def _read_context(actor: Membership) -> tuple[Connection, UUID, int, str, str]:
    refuse_demo(actor)
    try:
        connection = _active_github_connection(actor)
    except ConnectionNotReady as error:
        raise ReleaseConnectionNotReady() from error
    return (
        connection,
        connection.pk,
        connection.binding_revision,
        connection.repository_id,
        connection.repository,
    )


def list_repository_releases(*, actor: Membership, page: int) -> tuple[list[ReleaseSnapshot], bool]:
    connection, *_ = _read_context(actor)
    try:
        with (
            github_client() as client,
            selected_repository(
                client,
                installation_id=connection.external_id,
                repository_id=connection.repository_id,
                permissions=RELEASE_PERMISSIONS,
            ) as (token, canonical),
        ):
            return list_releases(
                client, installation_token=token, repository_name=canonical, page=page
            )
    except (ProviderAccessMissing, ProviderReleaseNotFound) as error:
        raise _provider_error(error) from error
    except (GitHubAPIError, httpx.HTTPError) as error:
        raise _provider_error(error) from error
    except ValueError as error:
        raise ReleaseProviderUnavailable() from error


def link_fix_release(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    external_id: str,
    now: datetime | None = None,
) -> Problem:
    refuse_demo(actor)
    problem = get_problem(actor=actor, problem_id=problem_id)
    require_version(row=problem, expected_version=expected_version)
    if problem.state != Problem.State.FIX_AVAILABLE:
        raise InvalidTransition(action="link_fix_release", from_state=problem.state)
    context = _read_context(actor)
    connection, binding = context[0], context[1:]
    try:
        with (
            github_client() as client,
            selected_repository(
                client,
                installation_id=connection.external_id,
                repository_id=connection.repository_id,
                permissions=RELEASE_PERMISSIONS,
            ) as (token, canonical),
        ):
            release = get_release(
                client,
                installation_token=token,
                repository_name=canonical,
                release_id=int(external_id),
            )
    except (ProviderAccessMissing, ProviderReleaseNotFound) as error:
        raise _provider_error(error) from error
    except (GitHubAPIError, httpx.HTTPError) as error:
        raise _provider_error(error) from error
    published_at = parse_datetime(release.published_at)
    if published_at is None:
        raise ReleaseProviderUnavailable()
    current = now or timezone.now()
    with transaction.atomic():
        lock_workspace(actor.workspace_id)
        locked_connection = Connection.objects.select_for_update().get(pk=connection.pk)
        if (
            binding
            != (
                locked_connection.pk,
                locked_connection.binding_revision,
                locked_connection.repository_id,
                locked_connection.repository,
            )
            or locked_connection.status != Connection.Status.ACTIVE
        ):
            raise ReleaseProviderUnavailable()
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        if problem.state != Problem.State.FIX_AVAILABLE:
            raise InvalidTransition(action="link_fix_release", from_state=problem.state)
        FixRelease.objects.update_or_create(
            problem=problem,
            defaults={
                "workspace_id": actor.workspace_id,
                "provider": "github",
                "external_id": release.external_id,
                "repository_id": connection.repository_id,
                "tag_name": release.tag_name,
                "name": release.name,
                "url": release.url,
                "published_at": published_at,
                "linked_by": actor,
                "linked_at": current,
            },
        )
        finish_mutation(row=problem, now=current, update_fields=[])
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_FIX_RELEASE_LINKED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"tag_name": release.tag_name},
            now=current,
        )
        return problem


def unlink_fix_release(
    *, actor: Membership, problem_id: UUID, expected_version: int, now: datetime | None = None
) -> Problem:
    refuse_demo(actor)
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        if not FixRelease.objects.filter(problem=problem).exists():
            from feedback.errors import NotFound

            raise NotFound(record="fix_release")
        FixRelease.objects.filter(problem=problem).delete()
        finish_mutation(row=problem, now=current, update_fields=[])
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_FIX_RELEASE_UNLINKED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            now=current,
        )
        return problem
