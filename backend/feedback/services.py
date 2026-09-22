"""Shared helpers for transactional feedback use cases."""

from datetime import datetime
from typing import Any
from uuid import UUID

from django.utils import timezone

from accounts.models import Membership
from feedback.errors import InvalidReference, NotFound, VersionConflict
from feedback.models import Activity, Problem, Report


def validate_reference(
    *, actor: Membership, model: type[Any], reference_id: UUID | None, field: str
) -> Any:
    if reference_id is None:
        return None
    filters: dict[str, Any] = {"pk": reference_id, "workspace_id": actor.workspace_id}
    if model is Membership:
        filters["is_active"] = True
    result = model.objects.filter(**filters).first()
    if result is None:
        raise InvalidReference(field=field)
    return result


def write_activity(
    *,
    actor: Membership,
    action: str,
    record_type: str,
    record_id: UUID,
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> Activity:
    return Activity.objects.create(
        workspace_id=actor.workspace_id,
        actor_membership=actor,
        action=action,
        record_type=record_type,
        record_id=record_id,
        metadata=metadata or {},
        created_at=now or timezone.now(),
    )


def locked_report(*, actor: Membership, report_id: UUID) -> Report:
    try:
        return Report.objects.select_for_update(of=("self",)).get(
            pk=report_id, workspace_id=actor.workspace_id
        )
    except Report.DoesNotExist as error:
        raise NotFound(record="report") from error


def locked_problem(*, actor: Membership, problem_id: UUID) -> Problem:
    try:
        return Problem.objects.select_for_update(of=("self",)).get(
            pk=problem_id, workspace_id=actor.workspace_id
        )
    except Problem.DoesNotExist as error:
        raise NotFound(record="problem") from error


def require_version(*, row: Report | Problem, expected_version: int) -> None:
    if row.version != expected_version:
        raise VersionConflict(current=row)


def finish_mutation(*, row: Report | Problem, now: datetime, update_fields: list[str]) -> None:
    row.version += 1
    row.updated_at = now
    row.save(update_fields=[*update_fields, "version", "updated_at"])
