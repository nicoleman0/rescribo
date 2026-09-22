"""Report submission and triage use cases."""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import AlreadyLinked, NoChanges, TitleRequired
from feedback.models import Activity, Problem, Report, ReportSource
from feedback.services import (
    finish_mutation,
    locked_report,
    require_version,
    validate_reference,
    write_activity,
)
from feedback.submissions import ReportSubmission
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
        raise ValueError("invalid_source_kind")
    with transaction.atomic():
        if source is not None:
            existing = _existing_source(actor=actor, source=source)
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
            if source is None:
                raise
            existing = _existing_source(actor=actor, source=source)
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


def _existing_source(*, actor: Membership, source: Any) -> Report | None:
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
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_ASSIGNED,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            metadata={
                "from_assignee_id": str(previous) if previous else None,
                "to_assignee_id": str(assignee.pk) if assignee else None,
            },
            now=current,
        )
        return report


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
        to_state = check_report_transition(action="link", from_state=report.triage_state)
        previous = report.problem_id
        report.problem = problem
        report.triage_state = to_state
        finish_mutation(row=report, now=current, update_fields=["problem", "triage_state"])
        write_activity(
            actor=actor,
            action=Activity.Action.REPORT_LINKED,
            record_type=Activity.RecordType.REPORT,
            record_id=report.pk,
            metadata={
                "from_problem_id": str(previous) if previous else None,
                "to_problem_id": str(problem.pk),
            },
            now=current,
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
        report.triage_state = state
        update_fields = ["triage_state"]
        if action == "unlink":
            report.problem = None
            update_fields.append("problem")
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
            now=current,
        )
        return report
