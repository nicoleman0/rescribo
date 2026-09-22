"""Problem editing and resolution use cases."""

from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from feedback.models import Activity, Problem
from feedback.services import (
    finish_mutation,
    locked_problem,
    require_version,
    validate_reference,
    write_activity,
)
from feedback.transitions import check_problem_transition


class ReasonRequired(ValueError):
    reason = "reason_required"


@dataclass(frozen=True)
class ProblemChanges:
    title: str | None = None
    summary: str | None = None
    owner_id: UUID | None = None


def create_problem(
    *,
    actor: Membership,
    title: str,
    summary: str = "",
    owner_id: UUID | None = None,
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("title_required")
    with transaction.atomic():
        owner = validate_reference(
            actor=actor, model=Membership, reference_id=owner_id, field="owner"
        )
        problem = Problem.objects.create(
            workspace_id=actor.workspace_id,
            title=clean_title,
            summary=summary,
            owner=owner,
            created_at=current,
            updated_at=current,
        )
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_CREATED,
            record_type="problem",
            record_id=problem.pk,
            now=current,
        )
        return problem


def update_problem(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    changes: ProblemChanges,
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        changed: list[str] = []
        for item in fields(changes):
            value = getattr(changes, item.name)
            field_name = "owner" if item.name == "owner_id" else item.name
            if value is not None:
                if item.name == "owner_id":
                    value = validate_reference(
                        actor=actor, model=Membership, reference_id=value, field="owner"
                    )
                existing = getattr(problem, field_name)
                existing_value = existing.pk if field_name == "owner" and existing else existing
                new_value = value.pk if field_name == "owner" and value else value
                if existing_value != new_value:
                    if item.name == "title" and not value.strip():
                        raise ValueError("title_required")
                    setattr(problem, field_name, value.strip() if item.name == "title" else value)
                    changed.append(field_name)
        if not changed:
            raise ValueError("no_changes")
        finish_mutation(row=problem, actor=actor, now=current, update_fields=changed)
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type="problem",
            record_id=problem.pk,
            metadata={"fields": changed},
            now=current,
        )
        return problem


def change_problem_state(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    action: str,
    reason: str = "",
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        if action == "decline" and not reason.strip():
            raise ReasonRequired("reason_required")
        problem.state = check_problem_transition(action=action, from_state=problem.state)
        update_fields = ["state"]
        if action == "decline":
            problem.not_planned_reason = reason.strip()
            update_fields.append("not_planned_reason")
        elif action == "reopen":
            problem.not_planned_reason = ""
            update_fields.append("not_planned_reason")
        finish_mutation(row=problem, actor=actor, now=current, update_fields=update_fields)
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_STATE_CHANGED,
            record_type="problem",
            record_id=problem.pk,
            metadata={"action": action, "state": problem.state},
            now=current,
        )
        return problem


def confirm_fix(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    fix_note: str,
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        problem.state = check_problem_transition(action="confirm_fix", from_state=problem.state)
        problem.resolution_revision += 1
        problem.fix_note = fix_note
        problem.fix_confirmed_at = current
        problem.fix_confirmed_by = actor
        problem.needs_review = False
        finish_mutation(
            row=problem,
            actor=actor,
            now=current,
            update_fields=[
                "state",
                "resolution_revision",
                "fix_note",
                "fix_confirmed_at",
                "fix_confirmed_by",
                "needs_review",
            ],
        )
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_FIX_CONFIRMED,
            record_type="problem",
            record_id=problem.pk,
            metadata={"resolution_revision": problem.resolution_revision},
            now=current,
        )
        return problem
