from dataclasses import replace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

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
from feedback.models import (
    Activity,
    FollowUp,
    Problem,
    Report,
    ReportSource,
)
from feedback.problems import (
    ProblemChanges,
    assign_problem_owner,
    change_problem_state,
    confirm_fix,
    confirm_linked_report_fix,
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
    return ReportSubmission(
        title,
        "Description",
        "Customer",
        "Contact",
        "1.0",
        source,
        uuid4() if source is None else None,
    )


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
    first_report = make_report(actor=actor)
    second_report = make_report(actor=actor)
    unlinked_report = make_report(actor=actor)
    link_report(actor=actor, report_id=first_report.pk, expected_version=1, problem_id=problem.pk)
    link_report(actor=actor, report_id=second_report.pk, expected_version=1, problem_id=problem.pk)
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
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=4,
        fix_note="First",
        fix_version="3.5.0",
    )
    assert problem.resolution_revision == 1 and problem.fix_confirmed_by_id == actor.pk
    created = list(FollowUp.objects.filter(problem=problem).order_by("report_id"))
    assert {follow_up.report_id for follow_up in created} == {first_report.pk, second_report.pk}
    assert all(follow_up.resolution_revision == 1 for follow_up in created)
    assert all(follow_up.report_version == 2 for follow_up in created)
    assert all(follow_up.recipient_id == actor.pk for follow_up in created)
    assert not FollowUp.objects.filter(report=unlinked_report).exists()
    Problem.objects.filter(pk=problem.pk).update(state="in_progress", version=problem.version + 1)
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version + 1,
        fix_note="Second",
        fix_version="3.6.0",
    )
    assert problem.resolution_revision == 2
    assert FollowUp.objects.filter(problem=problem).count() == 4


def test_linking_fixed_problem_requires_explicit_applicability_confirmation() -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed",
        fix_version="1.0.0",
    )
    report = make_report(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    assert not FollowUp.objects.filter(report=report).exists()
    follow_up = confirm_linked_report_fix(
        actor=actor,
        report_id=report.pk,
        expected_version=report.version,
        expected_resolution_revision=1,
    )
    assert follow_up.report_id == report.pk
    assert follow_up.problem_id == problem.pk
    assert follow_up.resolution_revision == problem.resolution_revision
    assert FollowUp.objects.filter(report=report).count() == 1


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
    revoked_owner = make_membership(
        user=make_user(email="revoked-owner@example.test"), workspace=actor.workspace
    )
    revoked_owner.is_active = False
    revoked_owner.revoked_at = timezone.now()
    revoked_owner.save(update_fields=["is_active", "revoked_at"])
    with pytest.raises(InvalidReference):
        assign_problem_owner(
            actor=actor,
            problem_id=problem.pk,
            expected_version=2,
            owner_id=revoked_owner.pk,
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


def test_manual_replay_preserves_current_report_and_source() -> None:
    actor = make_membership()
    draft = submission()
    first = submit_report(actor=actor, submission=draft)
    report = update_report(
        actor=actor,
        report_id=first.report.pk,
        expected_version=1,
        changes=ReportChanges(title="Edited", description="Current description"),
    )
    assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=actor.pk)
    problem = create_problem(actor=actor, title="Linked problem")
    link_report(actor=actor, report_id=report.pk, expected_version=3, problem_id=problem.pk)
    before = Report.objects.values().get(pk=report.pk)
    source_before = dict(ReportSource.objects.values().get(report_id=report.pk))
    activity_count = Activity.objects.count()
    replay = submit_report(actor=actor, submission=replace(draft, title="Retry edits"))
    assert not replay.created and replay.report.pk == report.pk
    assert replay.report.title == "Edited" and replay.report.version == 4
    assert Report.objects.values().get(pk=report.pk) == before
    assert ReportSource.objects.values().get(report_id=report.pk) == source_before
    assert Activity.objects.count() == activity_count
    assert Report.objects.count() == ReportSource.objects.count() == 1


def test_manual_identity_is_key_and_workspace_not_content() -> None:
    actor = make_membership()
    draft = submission()
    first = submit_report(actor=actor, submission=draft)
    replay = submit_report(actor=actor, submission=draft)
    distinct = submit_report(actor=actor, submission=replace(draft, submission_key=uuid4()))
    other = make_membership(user=actor.user, workspace=make_workspace(slug="other", name="Other"))
    independent = submit_report(actor=other, submission=draft)
    assert first.created and distinct.created and independent.created
    assert not replay.created and replay.report.pk == first.report.pk
    assert len({first.report.pk, distinct.report.pk, independent.report.pk}) == 3
    assert Report.objects.count() == ReportSource.objects.count() == Activity.objects.count() == 3


@pytest.mark.parametrize("key", [None, "malformed"])
def test_manual_submission_requires_uuid(key: Any) -> None:
    actor = make_membership()
    with pytest.raises(ValueError, match="submission_key"):
        submit_report(actor=actor, submission=replace(submission(), submission_key=key))
    assert not Report.objects.exists()


def test_unrelated_submission_integrity_failure_is_not_hidden() -> None:
    from django.db import IntegrityError

    actor = make_membership()
    with patch("feedback.reports.ReportSource.objects.create", side_effect=IntegrityError("other")):
        with pytest.raises(IntegrityError, match="other"):
            submit_report(actor=actor, submission=submission())
    assert not Report.objects.exists()
    assert not Activity.objects.exists()


@pytest.mark.parametrize("confirm_before_move", [True, False])
def test_follow_up_revisions_are_scoped_to_the_problem(confirm_before_move: bool) -> None:
    from feedback.problem_reads import problem_reports
    from feedback.serializers import ReportDetailSerializer

    actor = make_membership()
    report = make_report(actor=actor)
    first = create_problem(actor=actor, title="First")
    second = create_problem(actor=actor, title="Second")
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=first.pk
    )
    confirm_fix(
        actor=actor, problem_id=first.pk, expected_version=1, fix_note="First fix", fix_version="1"
    )
    if confirm_before_move:
        second = confirm_fix(
            actor=actor,
            problem_id=second.pk,
            expected_version=1,
            fix_note="Second fix",
            fix_version="1",
        )
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=second.pk
    )
    assert ReportDetailSerializer(report).data["follow_up_revision"] is None
    listed = problem_reports(actor=actor, problem_id=second.pk).get(pk=report.pk)
    assert ReportDetailSerializer(listed).data["follow_up_revision"] is None
    if confirm_before_move:
        confirm_linked_report_fix(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            expected_resolution_revision=1,
        )
    else:
        confirm_fix(
            actor=actor,
            problem_id=second.pk,
            expected_version=1,
            fix_note="Second fix",
            fix_version="1",
        )
    assert set(FollowUp.objects.filter(report=report).values_list("problem_id", flat=True)) == {
        first.pk,
        second.pk,
    }


@pytest.mark.parametrize("late", [True, False])
@pytest.mark.parametrize("slack", [True, False])
def test_follow_up_recipient_respects_report_source(late: bool, slack: bool) -> None:
    actor = make_membership()
    assignee = make_membership(
        workspace=actor.workspace, user=make_user(email="assignee@example.test")
    )
    problem = create_problem(actor=actor, title="Problem")
    report = make_report(actor=actor, source=slack_source() if slack else None)
    report = assign_report(
        actor=actor, report_id=report.pk, expected_version=report.version, assignee_id=assignee.pk
    )
    if late:
        problem = confirm_fix(
            actor=actor,
            problem_id=problem.pk,
            expected_version=1,
            fix_note="Fixed",
            fix_version="1",
        )
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=problem.pk
    )
    if late:
        confirm_linked_report_fix(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            expected_resolution_revision=1,
        )
    else:
        confirm_fix(
            actor=actor,
            problem_id=problem.pk,
            expected_version=1,
            fix_note="Fixed",
            fix_version="1",
        )
    assert FollowUp.objects.get(report=report).recipient_id == (actor.pk if slack else assignee.pk)


def test_late_confirmation_rejects_a_revision_the_member_did_not_review() -> None:
    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    problem = confirm_fix(
        actor=actor, problem_id=problem.pk, expected_version=1, fix_note="First", fix_version="1"
    )
    Problem.objects.filter(pk=problem.pk).update(state="in_progress")
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        fix_note="Second",
        fix_version="2",
    )
    report = make_report(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    with pytest.raises(VersionConflict):
        confirm_linked_report_fix(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            expected_resolution_revision=1,
        )
    assert not FollowUp.objects.filter(report=report).exists()
    first = confirm_linked_report_fix(
        actor=actor,
        report_id=report.pk,
        expected_version=report.version,
        expected_resolution_revision=2,
    )
    retry = confirm_linked_report_fix(
        actor=actor,
        report_id=report.pk,
        expected_version=report.version,
        expected_resolution_revision=2,
    )
    assert first.pk == retry.pk


@pytest.mark.django_db(transaction=True)
def test_late_confirmation_does_not_lock_report_while_waiting_for_problem() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from django.db import close_old_connections, transaction

    from feedback.services import locked_problem

    actor = make_membership()
    problem = create_problem(actor=actor, title="Problem")
    problem = confirm_fix(
        actor=actor, problem_id=problem.pk, expected_version=1, fix_note="Fixed", fix_version="1"
    )
    report = make_report(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    waiting = Event()

    def signal_problem_lock(**kwargs: Any) -> Problem:
        waiting.set()
        return locked_problem(**kwargs)

    def confirm() -> FollowUp:
        close_old_connections()
        try:
            return confirm_linked_report_fix(
                actor=actor,
                report_id=report.pk,
                expected_version=report.version,
                expected_resolution_revision=1,
            )
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with patch("feedback.problems.locked_problem", side_effect=signal_problem_lock):
            with transaction.atomic():
                Problem.objects.select_for_update().get(pk=problem.pk)
                future = executor.submit(confirm)
                assert waiting.wait(timeout=5)
                Report.objects.select_for_update(nowait=True).get(pk=report.pk)
            assert future.result(timeout=5).problem_id == problem.pk
