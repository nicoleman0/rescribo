"""Report submission and triage use cases."""

from dataclasses import dataclass, fields
from datetime import datetime
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import AlreadyLinked, InvalidSourceKind, NoChanges, TitleRequired
from feedback.follow_ups import recipient_for_report
from feedback.models import Activity, FollowUp, Problem, Report, ReportSource
from feedback.models import ReportNotificationOperation as Operation
from feedback.notifications import invalidate_pending_notifications
from feedback.problems import create_problem
from feedback.services import (
    finish_mutation,
    locked_report,
    require_version,
    validate_reference,
    write_activity,
)
from feedback.submissions import ReportSubmission, SourceSnapshot
from feedback.transitions import check_report_transition


@dataclass(frozen=True)
class SubmitResult:
    report: Report
    created: bool


@dataclass(frozen=True)
class ReportChanges:
    title: str | None = None
    description: str | None = None
    customer_label: str | None = None
    customer_contact_reference: str | None = None
    affected_version: str | None = None


def submit_report(
    *, actor: Membership, submission: ReportSubmission, now: datetime | None = None
) -> SubmitResult:
    current = now or timezone.now()
    title = submission.title.strip()
    if not title:
        raise TitleRequired()
    source = submission.source
    if source is not None and source.kind != ReportSource.Kind.SLACK:
        raise InvalidSourceKind()
    if source is None and not isinstance(submission.submission_key, UUID):
        raise ValueError("Manual submission_key must be a UUID.")
    if source is not None and submission.submission_key is not None:
        raise ValueError("Only manual sources may have a submission_key.")
    with transaction.atomic():
        existing = _existing_submission(actor=actor, submission=submission)
        if existing is not None:
            return SubmitResult(report=existing, created=False)
        try:
            with transaction.atomic():
                report = Report.objects.create(
                    workspace_id=actor.workspace_id,
                    title=title,
                    description=submission.description,
                    customer_label=submission.customer_label,
                    customer_contact_reference=submission.customer_contact_reference,
                    affected_version=submission.affected_version,
                    submitted_by=actor,
                    created_at=current,
                    updated_at=current,
                )
                ReportSource.objects.create(
                    report=report,
                    workspace_id=actor.workspace_id,
                    kind=source.kind if source else ReportSource.Kind.MANUAL,
                    submission_key=submission.submission_key,
                    external_workspace_id=source.external_workspace_id if source else "",
                    external_channel_id=source.external_channel_id if source else "",
                    external_message_id=source.external_message_id if source else "",
                    permalink=source.permalink if source else "",
                    author_external_id=source.author_external_id if source else "",
                    author_display_name=source.author_display_name if source else "",
                    snapshot_text=source.snapshot_text if source else "",
                    captured_at=current,
                )
        except IntegrityError:
            existing = _existing_submission(actor=actor, submission=submission)
            if existing is None:
                raise
            return SubmitResult(report=existing, created=False)
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_CREATED,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            now=current,
        )
        return SubmitResult(report=report, created=True)


def _existing_submission(*, actor: Membership, submission: ReportSubmission) -> Report | None:
    if submission.source is not None:
        return _existing_source(actor=actor, source=submission.source)
    return Report.objects.filter(
        workspace_id=actor.workspace_id,
        source__workspace_id=actor.workspace_id,
        source__kind=ReportSource.Kind.MANUAL,
        source__submission_key=submission.submission_key,
    ).first()


def _existing_source(*, actor: Membership, source: SourceSnapshot) -> Report | None:
    return Report.objects.filter(
        workspace_id=actor.workspace_id,
        source__kind=source.kind,
        source__external_workspace_id=source.external_workspace_id,
        source__external_channel_id=source.external_channel_id,
        source__external_message_id=source.external_message_id,
    ).first()


def update_report(
    *,
    actor: Membership,
    report_id: UUID,
    expected_version: int,
    changes: ReportChanges,
    now: datetime | None = None,
) -> Report:
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        changed: list[str] = []
        for item in fields(changes):
            value = getattr(changes, item.name)
            if value is not None:
                if item.name == "title":
                    value = value.strip()
                    if not value:
                        raise TitleRequired()
                if getattr(report, item.name) != value:
                    setattr(report, item.name, value)
                    changed.append(item.name)
        if not changed:
            raise NoChanges()
        finish_mutation(row=report, now=current, update_fields=changed)
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_UPDATED,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            metadata={"fields": changed},
            now=current,
        )
        return report


def assign_report(
    *,
    actor: Membership,
    report_id: UUID,
    expected_version: int,
    assignee_id: UUID | None,
    now: datetime | None = None,
) -> Report:
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        assignee = validate_reference(
            actor=actor, model=Membership, reference_id=assignee_id, field="assignee"
        )
        if report.assignee_id == (assignee.pk if assignee else None):
            raise NoChanges()
        previous = report.assignee_id
        report.assignee = assignee
        finish_mutation(row=report, now=current, update_fields=["assignee"])
        invalidate_pending_notifications(
            report=report, reason=Operation.InvalidationReason.REASSIGNED, now=current
        )
        change = {
            "from_assignee_id": _id(previous),
            "to_assignee_id": _id(assignee.pk if assignee else None),
        }
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_ASSIGNED,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            metadata=change,
            now=current,
        )
        if report.problem_id is not None:
            _write_problem_activity(
                actor=actor,
                action=Activity.Action.REPORT_ASSIGNED,
                problem_id=report.problem_id,
                report=report,
                metadata=change,
                now=current,
            )
        source_kind = (
            ReportSource.objects.filter(report=report).values_list("kind", flat=True).first()
        )
        if source_kind == ReportSource.Kind.MANUAL:
            _retarget_pending_follow_ups(actor=actor, report=report, now=current)
        return report


def _retarget_pending_follow_ups(*, actor: Membership, report: Report, now: datetime) -> None:
    """Move a manual report's pending follow-ups to the new assignee.

    The notification cancel above already retargets the unsent send. Once an
    outcome is recorded the recipient is historical, so we only touch the
    rows that are still waiting on contact.
    """
    new_recipient = recipient_for_report(report)
    pending = list(
        FollowUp.objects.select_for_update()
        .filter(
            workspace_id=report.workspace_id,
            report_id=report.pk,
            contact_state=FollowUp.ContactState.PENDING,
        )
        .exclude(recipient_id=new_recipient.pk)
        .order_by("created_at", "id")
    )
    for follow_up in pending:
        previous = follow_up.recipient_id
        follow_up.recipient = new_recipient
        follow_up.report_version = report.version
        finish_mutation(
            row=follow_up,
            now=now,
            update_fields=["recipient", "report_version"],
        )
        write_activity(
            actor=actor,
            action=Activity.Action.RECIPIENT_CHANGED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={
                "from_recipient_id": str(previous),
                "to_recipient_id": str(new_recipient.pk),
                "report_reassigned": True,
            },
            now=now,
        )


def link_report(
    *,
    actor: Membership,
    report_id: UUID,
    expected_version: int,
    problem_id: UUID,
    now: datetime | None = None,
) -> Report:
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        problem = validate_reference(
            actor=actor, model=Problem, reference_id=problem_id, field="problem"
        )
        if report.problem_id == problem.pk:
            raise AlreadyLinked()
        return _link_locked_report(actor=actor, report=report, problem=problem, now=current)


def create_problem_and_link_report(
    *,
    actor: Membership,
    report_id: UUID,
    expected_version: int,
    title: str,
    summary: str = "",
    owner_id: UUID | None = None,
    now: datetime | None = None,
) -> Report:
    """Create a problem and link the report to it, or change nothing."""
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        # Reject an illegal link before the problem exists.
        check_report_transition(action="link", from_state=report.triage_state)
        problem = create_problem(
            actor=actor, title=title, summary=summary, owner_id=owner_id, now=current
        )
        return _link_locked_report(actor=actor, report=report, problem=problem, now=current)


def _link_locked_report(
    *, actor: Membership, report: Report, problem: Problem, now: datetime
) -> Report:
    to_state = check_report_transition(action="link", from_state=report.triage_state)
    previous = report.problem_id
    report.problem = problem
    report.triage_state = to_state
    finish_mutation(row=report, now=now, update_fields=["problem", "triage_state"])
    if previous is not None:
        invalidate_pending_notifications(
            report=report, reason=Operation.InvalidationReason.MOVED, now=now
        )
        _write_problem_activity(
            actor=actor,
            action=Activity.Action.REPORT_UNLINKED,
            problem_id=previous,
            report=report,
            metadata={"to_problem_id": str(problem.pk)},
            now=now,
        )
    write_activity(
        actor=actor,
        action=Activity.Action.REPORT_LINKED,
        record_type=Activity.RecordType.REPORT,
        record_id=report.pk,
        metadata={"from_problem_id": _id(previous), "to_problem_id": str(problem.pk)},
        now=now,
    )
    _write_problem_activity(
        actor=actor,
        action=Activity.Action.REPORT_LINKED,
        problem_id=problem.pk,
        report=report,
        metadata={"from_problem_id": _id(previous)},
        now=now,
    )
    return report


def unlink_report(
    *, actor: Membership, report_id: UUID, expected_version: int, now: datetime | None = None
) -> Report:
    return _report_transition(
        actor=actor,
        report_id=report_id,
        expected_version=expected_version,
        action="unlink",
        now=now,
    )


def dismiss_report(
    *, actor: Membership, report_id: UUID, expected_version: int, now: datetime | None = None
) -> Report:
    return _report_transition(
        actor=actor,
        report_id=report_id,
        expected_version=expected_version,
        action="dismiss",
        now=now,
    )


def restore_report(
    *, actor: Membership, report_id: UUID, expected_version: int, now: datetime | None = None
) -> Report:
    return _report_transition(
        actor=actor,
        report_id=report_id,
        expected_version=expected_version,
        action="restore",
        now=now,
    )


def _report_transition(
    *, actor: Membership, report_id: UUID, expected_version: int, action: str, now: datetime | None
) -> Report:
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        require_version(row=report, expected_version=expected_version)
        state = check_report_transition(action=action, from_state=report.triage_state)
        previous_problem = report.problem_id
        report.triage_state = state
        update_fields = ["triage_state"]
        metadata: dict[str, str | None] = {}
        if action == "unlink":
            if previous_problem is None:
                raise AssertionError("A linked report must reference a problem.")
            report.problem = None
            update_fields.append("problem")
            metadata = {"from_problem_id": _id(previous_problem)}
        finish_mutation(row=report, now=current, update_fields=update_fields)
        activity_action = {
            "unlink": Activity.Action.REPORT_UNLINKED,
            "dismiss": Activity.Action.REPORT_DISMISSED,
            "restore": Activity.Action.REPORT_RESTORED,
        }[action]
        write_activity(
            actor=actor,
            action=activity_action,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            metadata=metadata,
            now=current,
        )
        if previous_problem is not None and action == "unlink":
            invalidate_pending_notifications(
                report=report, reason=Operation.InvalidationReason.UNLINKED, now=current
            )
            _write_problem_activity(
                actor=actor,
                action=Activity.Action.REPORT_UNLINKED,
                problem_id=previous_problem,
                report=report,
                metadata={"to_problem_id": None},
                now=current,
            )
        return report


def _write_problem_activity(
    *,
    actor: Membership,
    action: str,
    problem_id: UUID,
    report: Report,
    metadata: dict[str, str | None],
    now: datetime,
) -> None:
    write_activity(
        actor=actor,
        action=action,
        record_type=Activity.RecordType.PROBLEM,
        record_id=problem_id,
        metadata={"report_id": str(report.pk), **metadata},
        now=now,
    )


def _id(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
