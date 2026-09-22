from dataclasses import replace

import pytest
from builders import make_membership, make_report, make_user, make_workspace
from django.utils import timezone

from feedback.models import Activity, Problem
from feedback.problems import (
    ProblemChanges,
    ReasonRequired,
    change_problem_state,
    confirm_fix,
    create_problem,
    update_problem,
)
from feedback.reports import (
    AlreadyLinked,
    ReportChanges,
    assign_report,
    dismiss_report,
    link_report,
    restore_report,
    submit_report,
    unlink_report,
    update_report,
)
from feedback.services import InvalidReference, VersionConflict
from feedback.submissions import ReportSubmission, SourceSnapshot

pytestmark = pytest.mark.django_db


def submission(
    *, title: str = "Captured report", source: SourceSnapshot | None = None
) -> ReportSubmission:
    return ReportSubmission(title, "Description", "Customer", "Contact", "1.0", source)


def slack_source(message: str = "171234.1") -> SourceSnapshot:
    return SourceSnapshot(
        "slack", "T1", "C1", message, "https://example.test/msg", "U1", "Author", "snapshot-marker"
    )


def test_submit_manual_creates_provenance_and_content_free_activity() -> None:
    actor = make_membership()
    now = timezone.now()
    result = submit_report(actor=actor, submission=submission(title=" title-marker "), now=now)
    assert result.created and result.report.title == "title-marker"
    assert result.report.source.kind == "manual"
    activity = Activity.objects.get(record_id=result.report.pk)
    assert activity.action == Activity.Action.REPORT_CREATED
    assert activity.created_at == now and activity.metadata == {}


def test_duplicate_source_returns_existing_without_changes_or_activity() -> None:
    actor = make_membership()
    first = submit_report(actor=actor, submission=submission(source=slack_source()))
    assign_report(actor=actor, report_id=first.report.pk, expected_version=1, assignee_id=actor.pk)
    count = Activity.objects.count()
    duplicate = submit_report(
        actor=actor, submission=submission(title="Changed title", source=slack_source())
    )
    first.report.refresh_from_db()
    assert duplicate.created is False and duplicate.report.pk == first.report.pk
    assert first.report.title == "Captured report" and first.report.assignee_id == actor.pk
    assert Activity.objects.count() == count


def test_report_use_cases_versions_and_activity() -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    report = update_report(
        actor=actor, report_id=report.pk, expected_version=1, changes=ReportChanges(title="Changed")
    )
    assert report.version == 2
    assert Activity.objects.latest("created_at").action == Activity.Action.REPORT_UPDATED
    report = assign_report(
        actor=actor, report_id=report.pk, expected_version=2, assignee_id=actor.pk
    )
    problem = create_problem(actor=actor, title="A problem")
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=3, problem_id=problem.pk
    )
    with pytest.raises(AlreadyLinked):
        link_report(actor=actor, report_id=report.pk, expected_version=4, problem_id=problem.pk)
    source_values = {
        field.name: getattr(report.source, field.attname)
        for field in report.source._meta.concrete_fields
    }
    report = unlink_report(actor=actor, report_id=report.pk, expected_version=4)
    report.source.refresh_from_db()
    assert source_values == {
        field.name: getattr(report.source, field.attname)
        for field in report.source._meta.concrete_fields
    }
    report = dismiss_report(actor=actor, report_id=report.pk, expected_version=5)
    report = restore_report(actor=actor, report_id=report.pk, expected_version=6)
    assert report.version == 7


def test_problem_updates_state_and_fix_revision() -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    problem = update_problem(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        changes=ProblemChanges(summary="Summary"),
    )
    with pytest.raises(ReasonRequired) as error:
        change_problem_state(
            actor=actor, problem_id=problem.pk, expected_version=2, action="decline"
        )
    assert error.value.reason == "reason_required"
    problem = change_problem_state(
        actor=actor, problem_id=problem.pk, expected_version=2, action="decline", reason="No plan"
    )
    problem = change_problem_state(
        actor=actor, problem_id=problem.pk, expected_version=3, action="reopen"
    )
    problem = confirm_fix(actor=actor, problem_id=problem.pk, expected_version=4, fix_note="First")
    assert problem.resolution_revision == 1 and problem.fix_confirmed_by_id == actor.pk
    Problem.objects.filter(pk=problem.pk).update(state="in_progress")
    problem = confirm_fix(actor=actor, problem_id=problem.pk, expected_version=5, fix_note="Second")
    assert problem.resolution_revision == 2


def test_stale_version_returns_current_row_without_mutation() -> None:
    actor = make_membership()
    report = make_report(actor=actor)
    update_report(
        actor=actor, report_id=report.pk, expected_version=1, changes=ReportChanges(title="Latest")
    )
    with pytest.raises(VersionConflict) as error:
        update_report(
            actor=actor,
            report_id=report.pk,
            expected_version=1,
            changes=ReportChanges(description="lost"),
        )
    assert error.value.reason == "version_conflict"
    assert error.value.current.title == "Latest"
    report.refresh_from_db()
    assert report.description == ""


def test_cross_workspace_rows_and_references_are_hidden() -> None:
    actor_a = make_membership()
    actor_b = make_membership(
        user=make_user(email="other@example.test"),
        workspace=make_workspace(name="Other", slug="other"),
    )
    foreign_report = make_report(actor=actor_b)
    foreign_problem = create_problem(actor=actor_b, title="Foreign")
    for operation in (
        lambda: update_report(
            actor=actor_a,
            report_id=foreign_report.pk,
            expected_version=1,
            changes=ReportChanges(title="x"),
        ),
        lambda: assign_report(
            actor=actor_a, report_id=foreign_report.pk, expected_version=1, assignee_id=None
        ),
        lambda: dismiss_report(actor=actor_a, report_id=foreign_report.pk, expected_version=1),
        lambda: update_problem(
            actor=actor_a,
            problem_id=foreign_problem.pk,
            expected_version=1,
            changes=ProblemChanges(title="x"),
        ),
        lambda: change_problem_state(
            actor=actor_a, problem_id=foreign_problem.pk, expected_version=1, action="start"
        ),
    ):
        with pytest.raises(LookupError):
            operation()
    own_report = make_report(actor=actor_a)
    with pytest.raises(InvalidReference) as assignee_error:
        assign_report(
            actor=actor_a, report_id=own_report.pk, expected_version=1, assignee_id=actor_b.pk
        )
    assert (
        assignee_error.value.reason == "invalid_reference"
        and assignee_error.value.field == "assignee"
    )
    with pytest.raises(InvalidReference):
        link_report(
            actor=actor_a,
            report_id=own_report.pk,
            expected_version=1,
            problem_id=foreign_problem.pk,
        )
    with pytest.raises(InvalidReference):
        create_problem(actor=actor_a, title="Bad owner", owner_id=actor_b.pk)
    actor_b.is_active = False
    actor_b.revoked_at = timezone.now()
    actor_b.save(update_fields=["is_active", "revoked_at"])
    with pytest.raises(InvalidReference):
        assign_report(
            actor=actor_a, report_id=own_report.pk, expected_version=1, assignee_id=actor_b.pk
        )

    revoked_member = make_membership(
        user=make_user(email="revoked@example.test"), workspace=actor_a.workspace
    )
    revoked_member.is_active = False
    revoked_member.revoked_at = timezone.now()
    revoked_member.save(update_fields=["is_active", "revoked_at"])
    with pytest.raises(InvalidReference):
        assign_report(
            actor=actor_a,
            report_id=own_report.pk,
            expected_version=1,
            assignee_id=revoked_member.pk,
        )
    with pytest.raises(InvalidReference):
        create_problem(actor=actor_a, title="Revoked owner", owner_id=revoked_member.pk)


def test_activity_never_stores_report_content() -> None:
    actor = make_membership()
    marker = "unique-sensitive-marker"
    report = submit_report(
        actor=actor,
        submission=submission(title=marker, source=replace(slack_source(), snapshot_text=marker)),
    ).report
    update_report(
        actor=actor,
        report_id=report.pk,
        expected_version=1,
        changes=ReportChanges(description=marker),
    )
    activities = Activity.objects.filter(record_id=report.pk)
    assert all(marker not in str(item.metadata) for item in activities)
