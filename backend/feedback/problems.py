"""Problem editing and resolution use cases."""

from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import (
    FixDetailsRequired,
    InvalidTransition,
    NoChanges,
    ReasonRequired,
    TitleRequired,
)
from feedback.models import Activity, FollowUp, Problem, Report, ReportSource
from feedback.services import (
    finish_mutation,
    locked_problem,
    locked_report,
    require_version,
    validate_reference,
    write_activity,
)
from feedback.transitions import check_fix_confirmation_transition, check_problem_transition


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
        raise TitleRequired()
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
                        raise TitleRequired()
                if getattr(problem, item.name) != value:
                    setattr(problem, item.name, value)
                    changed.append(item.name)
        if not changed:
            raise NoChanges()
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
            raise NoChanges()
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
            raise ReasonRequired()
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
    fix_version: str,
    evidence_url: str = "",
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    clean_note = fix_note.strip()
    clean_version = fix_version.strip()
    if not clean_note or not clean_version:
        raise FixDetailsRequired()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        problem.state = check_fix_confirmation_transition(from_state=problem.state)
        problem.resolution_revision += 1
        problem.fix_note = clean_note
        problem.fix_version = clean_version
        problem.fix_evidence_url = evidence_url.strip()
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
                "fix_version",
                "fix_evidence_url",
                "fix_confirmed_at",
                "fix_confirmed_by",
                "needs_review",
            ],
        )
        _create_follow_ups(actor=actor, problem=problem, now=current)
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_FIX_CONFIRMED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"resolution_revision": problem.resolution_revision},
            now=current,
        )
        return problem


def confirm_linked_report_fix(
    *, actor: Membership, report_id: UUID, expected_version: int, now: datetime | None = None
) -> FollowUp:
    """Record a member's explicit verification that an existing fix applies to a new report."""
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        if report.triage_state != Report.TriageState.LINKED or report.problem_id is None:
            raise InvalidTransition(action="confirm_fix_applies", from_state=report.triage_state)
        problem = Problem.objects.select_for_update().get(
            pk=report.problem_id, workspace_id=actor.workspace_id
        )
        if problem.state != Problem.State.FIX_AVAILABLE or problem.resolution_revision < 1:
            raise InvalidTransition(action="confirm_fix_applies", from_state=problem.state)
        recipient = report.assignee or report.submitted_by
        follow_up, _ = FollowUp.objects.get_or_create(
            report=report,
            resolution_revision=problem.resolution_revision,
            defaults={
                "workspace_id": actor.workspace_id,
                "problem": problem,
                "recipient": recipient,
                "report_version": report.version,
                "created_by": actor,
                "created_at": current,
                "updated_at": current,
            },
        )
        return follow_up


def _create_follow_ups(*, actor: Membership, problem: Problem, now: datetime) -> list[FollowUp]:
    reports = (
        Report.objects.select_for_update(of=("self",))
        .select_related("source", "assignee", "submitted_by")
        .filter(
            workspace_id=actor.workspace_id,
            problem_id=problem.pk,
            triage_state=Report.TriageState.LINKED,
        )
        .order_by("id")
    )
    created: list[FollowUp] = []
    for report in reports:
        recipient = (
            report.assignee or report.submitted_by
            if report.source.kind == ReportSource.Kind.MANUAL
            else report.submitted_by
        )
        follow_up, was_created = FollowUp.objects.get_or_create(
            report=report,
            resolution_revision=problem.resolution_revision,
            defaults={
                "workspace_id": actor.workspace_id,
                "problem": problem,
                "recipient": recipient,
                "report_version": report.version,
                "created_by": actor,
                "created_at": now,
                "updated_at": now,
            },
        )
        if was_created:
            created.append(follow_up)
    return created
