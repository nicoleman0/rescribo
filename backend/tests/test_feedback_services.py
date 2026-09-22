from dataclasses import replace
from unittest.mock import patch

import pytest
from builders import make_membership, make_report, make_user, make_workspace
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import (
    AlreadyLinked,
    InvalidReference,
    InvalidSourceKind,
    InvalidTransition,
    NoChanges,
    NotFound,
    ReasonRequired,
    TitleRequired,
    VersionConflict,
)
from feedback.models import Activity, Problem, Report
from feedback.problems import (
    ProblemChanges,
    assign_problem_owner,
    change_problem_state,
    confirm_fix,
    create_problem,
    update_problem,
)
from feedback.reports import (
    ReportChanges,
    assign_report,
    dismiss_report,
    link_report,
    restore_report,
    submit_report,
    unlink_report,
    update_report,
)
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


def test_missing_title_raises_title_required() -> None:
    actor = make_membership()
    with pytest.raises(TitleRequired) as report_error:
        submit_report(actor=actor, submission=submission(title="   "))
    assert report_error.value.reason == "title_required"
    with pytest.raises(TitleRequired) as problem_error:
        create_problem(actor=actor, title="   ")
    assert problem_error.value.reason == "title_required"


def test_manual_source_snapshot_is_rejected() -> None:
    actor = make_membership()
    with pytest.raises(InvalidSourceKind) as error:
        submit_report(
            actor=actor, submission=submission(source=replace(slack_source(), kind="manual"))
        )
    assert error.value.reason == "invalid_source_kind"
    assert not Report.objects.exists()


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


def test_duplicate_source_recovers_after_concurrent_insert() -> None:
    actor = make_membership()
    original = submit_report(actor=actor, submission=submission(source=slack_source()))
    count = Activity.objects.count()
    from feedback import reports

    existing_source = reports._existing_source
    calls = 0

    def miss_once(*, actor: Membership, source: SourceSnapshot) -> Report | None:
        nonlocal calls
        calls += 1
        if calls == 1:
            return None
        return existing_source(actor=actor, source=source)

    with patch("feedback.reports._existing_source", side_effect=miss_once):
        result = submit_report(actor=actor, submission=submission(source=slack_source()))
    assert calls == 2
    assert result.created is False and result.report.pk == original.report.pk
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
    with pytest.raises(AlreadyLinked) as linked_error:
        link_report(actor=actor, report_id=report.pk, expected_version=4, problem_id=problem.pk)
    assert str(linked_error.value) == "already_linked"
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


@pytest.mark.parametrize("initial_state", ["open", "in_progress"])
def test_generic_problem_state_change_cannot_confirm_fix(initial_state: str) -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    if initial_state == "in_progress":
        problem = change_problem_state(
            actor=actor, problem_id=problem.pk, expected_version=1, action="start"
        )
    before = Activity.objects.count()
    prior = {
        "state": problem.state,
        "version": problem.version,
        "resolution_revision": problem.resolution_revision,
        "fix_note": problem.fix_note,
        "fix_confirmed_at": problem.fix_confirmed_at,
        "fix_confirmed_by_id": problem.fix_confirmed_by_id,
        "needs_review": problem.needs_review,
    }
    with pytest.raises(InvalidTransition):
        change_problem_state(
            actor=actor,
            problem_id=problem.pk,
            expected_version=problem.version,
            action="confirm_fix",
        )
    problem.refresh_from_db()
    assert {key: getattr(problem, key) for key in prior} == prior
    assert Activity.objects.count() == before


def test_declining_not_planned_problem_checks_transition_before_reason() -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    problem = change_problem_state(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        action="decline",
        reason="No plan",
    )
    with pytest.raises(InvalidTransition):
        change_problem_state(
            actor=actor,
            problem_id=problem.pk,
            expected_version=2,
            action="decline",
        )


def test_problem_title_whitespace_only_update_is_no_changes() -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Same")
    with pytest.raises(NoChanges) as error:
        update_problem(
            actor=actor,
            problem_id=problem.pk,
            expected_version=1,
            changes=ProblemChanges(title="  Same  "),
        )
    problem.refresh_from_db()
    assert problem.version == 1
    assert error.value.reason == "no_changes"


def test_report_title_whitespace_only_update_is_no_changes() -> None:
    actor = make_membership()
    report = make_report(actor=actor, title="Same")
    with pytest.raises(NoChanges) as error:
        update_report(
            actor=actor,
            report_id=report.pk,
            expected_version=1,
            changes=ReportChanges(title="  Same  "),
        )
    report.refresh_from_db()
    assert report.version == 1
    assert error.value.reason == "no_changes"


def test_problem_owner_can_be_cleared_and_cross_workspace_owner_is_rejected() -> None:
    actor = make_membership()
    foreign_owner = make_membership(
        user=make_user(email="foreign-owner@example.test"),
        workspace=make_workspace(name="Other", slug="other"),
    )
    problem = create_problem(actor=actor, title="Problem", owner_id=actor.pk)
    problem = assign_problem_owner(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        owner_id=None,
    )
    assert problem.owner_id is None and problem.version == 2
    activity = Activity.objects.latest("created_at")
    assert activity.action == Activity.Action.PROBLEM_UPDATED
    assert activity.metadata == {"fields": ["owner"]}
    with pytest.raises(InvalidReference):
        assign_problem_owner(
            actor=actor,
            problem_id=problem.pk,
            expected_version=2,
            owner_id=foreign_owner.pk,
        )


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
        with pytest.raises(NotFound):
            operation()
    with pytest.raises(NotFound) as report_error:
        update_report(
            actor=actor_a,
            report_id=foreign_report.pk,
            expected_version=1,
            changes=ReportChanges(title="Hidden"),
        )
    assert report_error.value.record == "report"
    with pytest.raises(NotFound) as problem_error:
        change_problem_state(
            actor=actor_a, problem_id=foreign_problem.pk, expected_version=1, action="start"
        )
    assert problem_error.value.record == "problem"
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
