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
from feedback.transitions import check_fix_confirmation_transition, check_problem_transition


class ReasonRequired(ValueError):
    reason = "reason_required"


@dataclass(frozen=True)
class ProblemChanges:
    title: str | None = None
    summary: str | None = None


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
            record_type=Activity.RecordType.PROBLEM,
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
            if value is not None:
                if item.name == "title":
                    value = value.strip()
                    if not value:
                        raise ValueError("title_required")
                if getattr(problem, item.name) != value:
                    setattr(problem, item.name, value)
                    changed.append(item.name)
        if not changed:
            raise ValueError("no_changes")
        finish_mutation(row=problem, now=current, update_fields=changed)
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"fields": changed},
            now=current,
        )
        return problem


def assign_problem_owner(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    owner_id: UUID | None,
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        owner = validate_reference(
            actor=actor, model=Membership, reference_id=owner_id, field="owner"
        )
        if problem.owner_id == (owner.pk if owner else None):
            raise ValueError("no_changes")
        problem.owner = owner
        finish_mutation(row=problem, now=current, update_fields=["owner"])
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"fields": ["owner"]},
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
        next_state = check_problem_transition(action=action, from_state=problem.state)
        if action == "decline" and not reason.strip():
            raise ReasonRequired("reason_required")
        problem.state = next_state
        update_fields = ["state"]
        if action == "decline":
            problem.not_planned_reason = reason.strip()
            update_fields.append("not_planned_reason")
        elif action == "reopen":
            problem.not_planned_reason = ""
            update_fields.append("not_planned_reason")
        finish_mutation(row=problem, now=current, update_fields=update_fields)
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_STATE_CHANGED,
            record_type=Activity.RecordType.PROBLEM,
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
        problem.state = check_fix_confirmation_transition(from_state=problem.state)
        problem.resolution_revision += 1
        problem.fix_note = fix_note
        problem.fix_confirmed_at = current
        problem.fix_confirmed_by = actor
        problem.needs_review = False
        finish_mutation(
            row=problem,
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
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"resolution_revision": problem.resolution_revision},
            now=current,
        )
        return problem
