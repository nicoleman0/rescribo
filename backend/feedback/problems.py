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
    NotFound,
    ReasonRequired,
    TitleRequired,
    VersionConflict,
)
from feedback.follow_ups import recipient_for_report
from feedback.models import Activity, FollowUp, Problem, Report
from feedback.services import (
    finish_mutation,
    locked_problem,
    locked_report,
    require_version,
    validate_reference,
    write_activity,
)
from feedback.transitions import check_fix_confirmation_transition, check_problem_transition

# Marks the clearing entry, so activity can tell it from the flagging ones.
REVIEWED_REASON = "reviewed"


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


def mark_problem_reviewed(
    *,
    actor: Membership,
    problem_id: UUID,
    expected_version: int,
    now: datetime | None = None,
) -> Problem:
    current = now or timezone.now()
    with transaction.atomic():
        problem = locked_problem(actor=actor, problem_id=problem_id)
        require_version(row=problem, expected_version=expected_version)
        if not problem.needs_review:
            raise InvalidTransition(action="mark_reviewed", from_state=problem.state)
        problem.needs_review = False
        finish_mutation(row=problem, now=current, update_fields=["needs_review"])
        write_activity(
            actor=actor,
            action=Activity.Action.PROBLEM_UPDATED,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
            metadata={"fields": ["needs_review"], "reason": REVIEWED_REASON},
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
    *,
    actor: Membership,
    report_id: UUID,
    expected_version: int,
    expected_resolution_revision: int,
    now: datetime | None = None,
) -> FollowUp:
    """Record verification of the fix revision the member actually reviewed."""
    current = now or timezone.now()
    with transaction.atomic():
        snapshot = Report.objects.filter(pk=report_id, workspace_id=actor.workspace_id).first()
        if snapshot is None:
            raise NotFound(record="report")
        require_version(row=snapshot, expected_version=expected_version)
        if snapshot.triage_state != Report.TriageState.LINKED or snapshot.problem_id is None:
            raise InvalidTransition(action="confirm_fix_applies", from_state=snapshot.triage_state)
        # Fix confirmation locks the problem before its reports as well.
        problem = locked_problem(actor=actor, problem_id=snapshot.problem_id)
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        if problem.state != Problem.State.FIX_AVAILABLE or problem.resolution_revision < 1:
            raise InvalidTransition(action="confirm_fix_applies", from_state=problem.state)
        if problem.resolution_revision != expected_resolution_revision:
            raise VersionConflict(current=report)
        follow_up, _ = _create_follow_up(actor=actor, problem=problem, report=report, now=current)
        return follow_up


def _create_follow_up(
    *, actor: Membership, problem: Problem, report: Report, now: datetime
) -> tuple[FollowUp, bool]:
    return FollowUp.objects.get_or_create(
        report=report,
        problem=problem,
        resolution_revision=problem.resolution_revision,
        defaults={
            "workspace_id": actor.workspace_id,
            "recipient": recipient_for_report(report),
            "report_version": report.version,
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        },
    )


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
        follow_up, was_created = _create_follow_up(
            actor=actor, problem=problem, report=report, now=now
        )
        if was_created:
            created.append(follow_up)
    return created
