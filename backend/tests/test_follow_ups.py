"""Follow-up reads, drafts, and approval over real PostgreSQL; Slack stays mocked."""

from typing import Any
from unittest.mock import patch

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections.models import Connection, ExternalIdentity
from feedback.errors import (
    DeliveryNotReady,
    InvalidTransition,
    MessageRequired,
    NotFound,
    ReasonRequired,
    VersionConflict,
)
from feedback.follow_ups import (
    approve_notification,
    change_recipient,
    correct_outcome,
    current_notification,
    draft_notification,
    edit_notification,
    recipient_for_report,
    record_outcome,
    search_follow_ups,
)
from feedback.models import Activity, FollowUp, Problem, Report
from feedback.problems import confirm_fix
from feedback.reports import assign_report, link_report
from feedback.submissions import SourceSnapshot

pytestmark = pytest.mark.django_db


def _notification_id(follow_up: FollowUp) -> Any:
    operation = current_notification(follow_up)
    assert operation is not None
    return operation.pk


TEAM = "T0TEAM"
ACTOR = "U0ACTOR"


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def api(membership: Membership, path: str) -> str:
    return f"/api/workspaces/{membership.workspace_id}/{path}"


def post_json(client: Client, url: str, body: dict[str, Any] | None) -> Any:
    return client.post(url, body if body is not None else {}, content_type="application/json")


def slack_source() -> SourceSnapshot:
    return SourceSnapshot(
        "slack", "T1", "C1", "171.1", "https://example.test/msg", "U1", "Author", "snapshot"
    )


@pytest.fixture
def owner(client: Client) -> Membership:
    membership = make_membership(role=Membership.Role.OWNER)
    sign_in(client, membership)
    return membership


@pytest.fixture
def connection(owner: Membership) -> Connection:
    return Connection.objects.create(
        workspace=owner.workspace,
        provider="slack",
        external_id=TEAM,
        identity="Acme Slack",
        status="active",
        credential="encrypted",
    )


def link_slack(member: Membership, user_id: str = ACTOR) -> None:
    ExternalIdentity.objects.create(
        workspace=member.workspace,
        membership=member,
        provider="slack",
        provider_team_id=TEAM,
        provider_user_id=user_id,
    )


def fixed_report(actor: Membership, *, source: SourceSnapshot | None = None) -> Report:
    """A linked report with a confirmed fix, so its follow-up is ready for drafting."""
    problem = make_problem(actor=actor, title="Broken export")
    report = make_report(actor=actor, title="Export fails", source=source)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed in the export service.",
        fix_version="1.2.0",
    )
    return Report.objects.select_related("problem", "source", "assignee", "submitted_by").get(
        pk=report.pk
    )


# The recipient rule, extracted from confirm_fix


def test_manual_reports_follow_the_assignee(owner: Membership) -> None:
    assignee = make_membership(workspace=owner.workspace, user=make_user(email="a@example.test"))
    problem = make_problem(actor=owner, title="Broken export")
    report = make_report(actor=owner, title="Manual export fails")
    report = assign_report(
        actor=owner, report_id=report.pk, expected_version=1, assignee_id=assignee.pk
    )
    link_report(
        actor=owner, report_id=report.pk, expected_version=report.version, problem_id=problem.pk
    )
    confirm_fix(
        actor=owner,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed.",
        fix_version="1.0.0",
    )
    follow_up = report.follow_ups.get()
    assert (follow_up.recipient_id, follow_up.created_by_id) == (assignee.pk, owner.pk)
    assert (
        recipient_for_report(
            Report.objects.select_related("source", "assignee", "submitted_by").get(pk=report.pk)
        )
        == assignee
    )


def test_captured_reports_follow_the_submitter(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    assert recipient_for_report(report) == report.submitted_by
    assert search_follow_ups(actor=owner, bucket="needs_approval").get().pk == follow_up.pk


# Buckets


def test_sent_rows_move_buckets_by_contact_state(owner: Membership, connection: Connection) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    make_notification(report=report, state="sent")
    assert list(search_follow_ups(actor=owner, bucket="awaiting_contact")) == [follow_up]
    assert not search_follow_ups(actor=owner, bucket="needs_approval").exists()

    FollowUp.objects.filter(pk=follow_up.pk).update(
        contact_state=FollowUp.ContactState.CONTACTED,
        outcome_at=timezone.now(),
        outcome_by=owner,
    )
    assert list(search_follow_ups(actor=owner, bucket="awaiting_confirmation")) == [follow_up]
    assert not search_follow_ups(actor=owner, bucket="awaiting_contact").exists()

    FollowUp.objects.filter(pk=follow_up.pk).update(contact_state=FollowUp.ContactState.CONFIRMED)
    completed = [row for row in search_follow_ups(actor=owner, bucket="completed")]
    assert [row.pk for row in completed] == [follow_up.pk]


def test_failed_and_uncertain_rows_are_delivery_problems(
    owner: Membership, connection: Connection
) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    operation = make_notification(report=report, state="failed")
    assert list(search_follow_ups(actor=owner, bucket="delivery_problem")) == [follow_up]
    assert not search_follow_ups(actor=owner, bucket="needs_approval").exists()

    type(operation).objects.filter(pk=operation.pk).update(state=type(operation).State.UNCERTAIN)
    assert list(search_follow_ups(actor=owner, bucket="delivery_problem")) == [follow_up]


# Draft content


def test_default_draft_content(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    assert draft.message.startswith('The fix for "Export fails" is available (1.2.0).')
    assert "Fixed in the export service." in draft.message
    assert f"/inbox/{report.pk}" in draft.message
    assert draft.recipient_id == follow_up.recipient_id


def test_draft_is_created_once(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    first = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    second = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    assert second.pk == first.pk


def test_changes_that_invalidate_the_draft(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    drafted = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    other_problem = make_problem(actor=owner, title="Other")
    link_report(
        actor=owner,
        report_id=report.pk,
        expected_version=report.version,
        problem_id=other_problem.pk,
    )
    row = FollowUp.objects.get(report=report, resolution_revision=1).notifications.first()
    assert row is not None
    assert (row.state, row.invalidation_reason) in (
        ("cancelled", "moved"),
        ("cancelled", "unlinked"),
    )
    # Follow-up history is never moved; the cancelled row keeps its own problem.
    assert row.problem_id == drafted.problem_id


# Edit


def test_edits_bump_the_draft_version(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    edited = edit_notification(
        actor=owner,
        follow_up_id=follow_up.pk,
        notification_id=_notification_id(follow_up),
        message="Updated message.",
        draft_version=1,
    )
    assert (edited.message, edited.draft_version) == ("Updated message.", 2)


def test_conflicting_edits_return_the_current_row(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    edit_notification(
        actor=owner,
        follow_up_id=follow_up.pk,
        notification_id=_notification_id(follow_up),
        message="One",
        draft_version=1,
    )
    with pytest.raises(VersionConflict) as conflict:
        edit_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            message="Two",
            draft_version=1,
        )
    assert conflict.value.current.message == "One"


def test_empty_messages_are_rejected(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    with pytest.raises(ValueError):
        edit_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            message="   ",
            draft_version=1,
        )


def test_failed_rows_stay_editable(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    drafted = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    type(drafted).objects.filter(pk=drafted.pk).update(
        state=type(drafted).State.FAILED,
    )
    edited = edit_notification(
        actor=owner,
        follow_up_id=follow_up.pk,
        notification_id=_notification_id(follow_up),
        message="Try again.",
        draft_version=1,
    )
    assert (edited.state, edited.draft_version) == ("failed", 2)


def test_sent_and_queued_rows_cannot_be_edited(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    drafted = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    with patch("feedback.follow_ups.dispatch_task"):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )
    assert drafted.draft_version == 1
    with pytest.raises(InvalidTransition):
        edit_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            message="Edit",
            draft_version=2,
        )


# Approve


def test_approval_queues_one_send(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)

    with TestCase.captureOnCommitCallbacks(execute=True):
        operation = approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )

    assert (operation.state, operation.approved_by_id) == ("queued", owner.pk)
    assert operation.due_at is not None
    assert operation.due_at <= timezone.now()
    approval = Activity.objects.filter(record_type="follow_up", record_id=follow_up.pk).get()
    assert approval.action == "follow_up.notification_approved"


def test_approval_without_an_identity_never_queues(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    with pytest.raises(DeliveryNotReady):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )
    current = current_notification(report.follow_ups.get())
    assert current is not None and current.state == "draft"


def test_approval_needs_an_active_connection(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    Connection.objects.filter(pk=connection.pk).update(status=Connection.Status.ERROR)
    with pytest.raises(DeliveryNotReady):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )


def test_stale_approvals_are_rejected(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    Report.objects.filter(pk=report.pk).update(version=report.version + 1)
    with pytest.raises(DeliveryNotReady):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )


def test_wrong_draft_versions_do_not_queue(owner: Membership, connection: Connection) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    with pytest.raises(VersionConflict):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=9,
        )


def test_old_notification_identity_cannot_mutate_reassigned_replacement(
    owner: Membership,
) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    old = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    recipient = make_membership(
        workspace=owner.workspace, user=make_user(email="replacement-stale@example.test")
    )
    ExternalIdentity.objects.create(
        workspace=owner.workspace,
        membership=recipient,
        provider=Connection.Provider.SLACK,
        provider_team_id=TEAM,
        provider_user_id="U_REPLACEMENT",
    )
    change_recipient(actor=owner, follow_up_id=follow_up.pk, new_recipient_id=recipient.pk)
    replacement = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    assert replacement.pk != old.pk
    assert replacement.draft_version == old.draft_version
    with pytest.raises(VersionConflict) as conflict:
        edit_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=old.pk,
            message="stale edit",
            draft_version=old.draft_version,
        )
    assert conflict.value.current.pk == replacement.pk
    with patch("feedback.follow_ups.dispatch_task") as dispatch:
        with pytest.raises(VersionConflict):
            approve_notification(
                actor=owner,
                follow_up_id=follow_up.pk,
                notification_id=old.pk,
                draft_version=old.draft_version,
            )
    dispatch.assert_not_called()
    replacement.refresh_from_db()
    assert replacement.state == "draft"
    assert replacement.message != "stale edit"


# HTTP contracts


def test_list_buckets_and_detail_over_http(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)

    listed = client.get(api(owner, "follow-ups/?bucket=needs_approval"))
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] == 1
    assert body["results"][0]["report_title"] == "Export fails"

    detail = client.get(api(owner, f"follow-ups/{follow_up.pk}/"))
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["problem"]["fix_version"] == "1.2.0"
    assert payload["notification"]["state"] == "draft"
    assert payload["outcome"]["state"] == "pending"


def test_edit_and_approve_conflicts_over_http(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    post_json(client, api(owner, f"follow-ups/{follow_up.pk}/notification/"), None)
    response = post_json(
        client,
        api(owner, f"follow-ups/{follow_up.pk}/notification/edit/"),
        {
            "message": "Edited",
            "notification_id": str(_notification_id(follow_up)),
            "draft_version": 1,
        },
    )
    assert response.status_code == 200
    stale = post_json(
        client,
        api(owner, f"follow-ups/{follow_up.pk}/notification/edit/"),
        {
            "message": "Again",
            "notification_id": str(_notification_id(follow_up)),
            "draft_version": 1,
        },
    )
    assert stale.status_code == 409
    current = stale.json()["current"]
    assert current["notification"]["message"] == "Edited"
    assert current["notification"]["draft_version"] == 2

    wrong = post_json(
        client,
        api(owner, f"follow-ups/{follow_up.pk}/notification/approve/"),
        {"notification_id": str(_notification_id(follow_up)), "draft_version": 1},
    )
    assert wrong.status_code == 409


def test_approve_without_identity_reports_the_copy_path(
    client: Client, owner: Membership, connection: Connection
) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    post_json(client, api(owner, f"follow-ups/{follow_up.pk}/notification/"), None)
    response = post_json(
        client,
        api(owner, f"follow-ups/{follow_up.pk}/notification/approve/"),
        {"notification_id": str(_notification_id(follow_up)), "draft_version": 1},
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "no_slack_identity"


def test_foreign_members_find_nothing(client: Client, owner: Membership) -> None:
    outsider = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    report = fixed_report(owner, source=slack_source())
    sign_in(client, outsider)
    assert client.get(api(outsider, "follow-ups/")).json()["count"] == 0
    detail = client.get(api(outsider, f"follow-ups/{report.follow_ups.get().pk}/"))
    assert detail.status_code == 404


# Outcomes (A5)


def _outcome_url(membership: Membership, follow_up_id: Any, suffix: str = "") -> str:
    base = f"/api/workspaces/{membership.workspace_id}/follow-ups/{follow_up_id}/outcome/"
    return f"{base}{suffix}" if suffix else base


def _record(
    membership: Membership,
    follow_up_id: Any,
    state: str,
    *,
    note: str = "",
    expected_version: int = 1,
) -> FollowUp:
    return record_outcome(
        actor=membership,
        follow_up_id=follow_up_id,
        state=state,
        note=note,
        expected_version=expected_version,
    )


def test_recorded_contacted_moves_row_to_contacted_bucket(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    outcome = _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    assert outcome.contact_state == FollowUp.ContactState.CONTACTED
    assert outcome.outcome_at is not None
    assert outcome.outcome_by_id == owner.pk
    assert list(search_follow_ups(actor=owner, bucket="awaiting_confirmation")) == [outcome]


def test_then_confirmed_from_contacted(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    final = _record(owner, follow_up.pk, FollowUp.ContactState.CONFIRMED, expected_version=2)
    assert final.contact_state == FollowUp.ContactState.CONFIRMED
    assert list(search_follow_ups(actor=owner, bucket="completed")) == [final]


def test_still_affected_from_pending_sets_problem_review(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    assert report.problem_id is not None
    problem = Problem.objects.get(pk=report.problem_id)
    problem.needs_review = False
    problem.save(update_fields=["needs_review"])
    outcome = _record(owner, follow_up.pk, FollowUp.ContactState.STILL_AFFECTED)
    assert outcome.contact_state == FollowUp.ContactState.STILL_AFFECTED
    problem.refresh_from_db()
    assert problem.needs_review is True


def test_no_response_requires_a_note(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    with pytest.raises(MessageRequired):
        _record(owner, follow_up.pk, FollowUp.ContactState.NO_RESPONSE, note="   ")
    with pytest.raises(MessageRequired):
        _record(owner, follow_up.pk, FollowUp.ContactState.NO_RESPONSE, note="")


def test_recorded_outcome_is_a_history_entry(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED, note="Spoke with Acme.")
    activity = Activity.objects.get(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.OUTCOME_RECORDED,
    )
    assert activity.metadata == {
        "from_state": FollowUp.ContactState.PENDING,
        "to_state": FollowUp.ContactState.CONTACTED,
    }


def test_terminal_states_cannot_be_recorded_again(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    _record(owner, follow_up.pk, FollowUp.ContactState.CONFIRMED, expected_version=2)
    with pytest.raises(InvalidTransition):
        _record(owner, follow_up.pk, FollowUp.ContactState.STILL_AFFECTED, expected_version=3)


def test_pending_cannot_go_straight_to_confirmed(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    with pytest.raises(InvalidTransition):
        _record(owner, follow_up.pk, FollowUp.ContactState.CONFIRMED)


def test_version_mismatch_returns_conflict(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    with pytest.raises(VersionConflict) as conflict:
        _record(owner, follow_up.pk, FollowUp.ContactState.STILL_AFFECTED, expected_version=1)
    assert conflict.value.current.contact_state == FollowUp.ContactState.CONTACTED


def test_submitter_and_assignee_can_record_outcome(owner: Membership) -> None:
    submitter = owner
    assignee = make_membership(workspace=owner.workspace, user=make_user(email="a@example.test"))
    problem = make_problem(actor=owner, title="Manual")
    report = make_report(actor=submitter, title="Manual case")
    report = assign_report(
        actor=owner, report_id=report.pk, expected_version=1, assignee_id=assignee.pk
    )
    report = link_report(
        actor=owner, report_id=report.pk, expected_version=2, problem_id=problem.pk
    )
    confirm_fix(
        actor=owner, problem_id=problem.pk, expected_version=1, fix_note="Fixed.", fix_version="1.0"
    )
    follow_up = report.follow_ups.get()
    _record(submitter, follow_up.pk, FollowUp.ContactState.CONTACTED)
    _record(
        assignee,
        follow_up.pk,
        FollowUp.ContactState.CONFIRMED,
        expected_version=2,
    )


def test_unrelated_member_cannot_record_outcome(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    outsider = make_membership(
        workspace=owner.workspace, user=make_user(email="other@example.test")
    )
    with pytest.raises(InvalidTransition):
        _record(outsider, follow_up.pk, FollowUp.ContactState.CONTACTED)
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING


def test_owner_can_correct_outcome_with_reason(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    _record(owner, follow_up.pk, FollowUp.ContactState.CONFIRMED, expected_version=2)
    corrected = correct_outcome(
        actor=owner,
        follow_up_id=follow_up.pk,
        state=FollowUp.ContactState.STILL_AFFECTED,
        note="Customer reported new symptoms.",
        reason="Spoke to support and corrected.",
        expected_version=3,
    )
    assert corrected.contact_state == FollowUp.ContactState.STILL_AFFECTED
    activity = Activity.objects.get(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.OUTCOME_CORRECTED,
    )
    assert activity.metadata["reason"] == "Spoke to support and corrected."
    assert activity.metadata["from_state"] == FollowUp.ContactState.CONFIRMED
    assert activity.metadata["to_state"] == FollowUp.ContactState.STILL_AFFECTED


def test_owner_correction_requires_reason(owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    with pytest.raises(ReasonRequired):
        correct_outcome(
            actor=owner,
            follow_up_id=follow_up.pk,
            state=FollowUp.ContactState.STILL_AFFECTED,
            note="",
            reason="   ",
            expected_version=2,
        )


def test_non_owner_cannot_correct_outcome(owner: Membership) -> None:
    member = make_membership(workspace=owner.workspace, user=make_user(email="m@example.test"))
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    with pytest.raises(InvalidTransition):
        correct_outcome(
            actor=member,
            follow_up_id=follow_up.pk,
            state=FollowUp.ContactState.STILL_AFFECTED,
            note="",
            reason="Reason",
            expected_version=2,
        )


def test_outcome_endpoint_round_trip(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk),
        {"state": FollowUp.ContactState.CONTACTED, "expected_version": 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"]["state"] == FollowUp.ContactState.CONTACTED


def test_outcome_endpoint_returns_409_on_version_mismatch(
    client: Client, owner: Membership
) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    post_json(
        client,
        _outcome_url(owner, follow_up.pk),
        {"state": FollowUp.ContactState.CONTACTED, "expected_version": 1},
    )
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk),
        {"state": FollowUp.ContactState.STILL_AFFECTED, "expected_version": 1},
    )
    assert response.status_code == 409
    assert response.json()["current"]["outcome"]["state"] == FollowUp.ContactState.CONTACTED


def test_outcome_endpoint_returns_400_without_note_for_no_response(
    client: Client, owner: Membership
) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk),
        {"state": FollowUp.ContactState.NO_RESPONSE, "expected_version": 1},
    )
    assert response.status_code == 400


def test_correct_endpoint_returns_400_without_reason(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk, "correct/"),
        {
            "state": FollowUp.ContactState.STILL_AFFECTED,
            "note": "x",
            "reason": "   ",
            "expected_version": 2,
        },
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "reason_required"


def test_correct_endpoint_requires_owner(client: Client, owner: Membership) -> None:
    member = make_membership(workspace=owner.workspace, user=make_user(email="m@example.test"))
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    sign_in(client, member)
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk, "correct/"),
        {
            "state": FollowUp.ContactState.STILL_AFFECTED,
            "note": "x",
            "reason": "R",
            "expected_version": 2,
        },
    )
    assert response.status_code == 409


def test_correct_endpoint_cross_workspace(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    _record(owner, follow_up.pk, FollowUp.ContactState.CONTACTED)
    outsider = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    sign_in(client, outsider)
    response = post_json(
        client,
        _outcome_url(owner, follow_up.pk, "correct/"),
        {
            "state": FollowUp.ContactState.STILL_AFFECTED,
            "note": "x",
            "reason": "R",
            "expected_version": 2,
        },
    )
    assert response.status_code == 404


def test_outcome_endpoint_cross_workspace(client: Client, owner: Membership) -> None:
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    outsider = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    sign_in(client, outsider)
    response = post_json(
        client,
        _outcome_url(outsider, follow_up.pk),
        {"state": FollowUp.ContactState.CONTACTED, "expected_version": 1},
    )
    assert response.status_code == 404


def test_delivery_state_never_changes_contact_state(
    client: Client, owner: Membership, connection: Connection
) -> None:
    link_slack(owner)
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft = draft_notification(actor=owner, follow_up_id=follow_up.pk)
    with TestCase.captureOnCommitCallbacks(execute=True):
        approve_notification(
            actor=owner,
            follow_up_id=follow_up.pk,
            notification_id=_notification_id(follow_up),
            draft_version=1,
        )
    type(draft).objects.filter(pk=draft.pk).update(
        state=type(draft).State.SENT,
        sent_at=timezone.now(),
        remote_conversation_id="D1",
        remote_message_id="171.1",
    )
    follow_up.refresh_from_db()
    assert follow_up.contact_state == FollowUp.ContactState.PENDING


# Recipient changes (A7)


def _recipient_url(membership: Membership, follow_up_id: Any) -> str:
    return f"/api/workspaces/{membership.workspace_id}/follow-ups/{follow_up_id}/recipient/"


def _setup_recipient_change(
    owner: Membership,
) -> tuple[Report, FollowUp, Membership, Membership]:
    link_slack(owner)
    other = make_membership(workspace=owner.workspace, user=make_user(email="o@example.test"))
    link_slack(other, user_id="U0OTHER")
    report = fixed_report(owner, source=slack_source())
    follow_up = report.follow_ups.get()
    draft_notification(actor=owner, follow_up_id=follow_up.pk)
    return report, follow_up, owner, other


def test_owner_can_reassign_follow_up_recipient(owner: Membership) -> None:
    report, follow_up, _, other = _setup_recipient_change(owner)
    updated = change_recipient(actor=owner, follow_up_id=follow_up.pk, new_recipient_id=other.pk)
    assert updated.recipient_id == other.pk
    activity = Activity.objects.get(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.RECIPIENT_CHANGED,
    )
    assert activity.metadata == {
        "from_recipient_id": str(owner.pk),
        "to_recipient_id": str(other.pk),
    }


def test_recipient_change_cancels_unset_notification(owner: Membership) -> None:
    _, follow_up, _, other = _setup_recipient_change(owner)
    operation = current_notification(follow_up)
    assert operation is not None and operation.state == "draft"
    change_recipient(actor=owner, follow_up_id=follow_up.pk, new_recipient_id=other.pk)
    operation.refresh_from_db()
    assert operation.state == "cancelled"
    assert operation.invalidation_reason == "reassigned"


def test_recipient_change_requires_slack_link_for_new_recipient(
    owner: Membership,
) -> None:
    _, follow_up, _, _ = _setup_recipient_change(owner)
    unlinked = make_membership(
        workspace=owner.workspace, user=make_user(email="unlinked@example.test")
    )
    with pytest.raises(InvalidTransition):
        change_recipient(actor=owner, follow_up_id=follow_up.pk, new_recipient_id=unlinked.pk)


def test_recipient_change_requires_active_member(owner: Membership) -> None:
    _, follow_up, _, _ = _setup_recipient_change(owner)
    revoked = make_membership(workspace=owner.workspace, user=make_user(email="r@example.test"))
    Membership.objects.filter(pk=revoked.pk).update(is_active=False, revoked_at=timezone.now())
    with pytest.raises(NotFound):
        change_recipient(actor=owner, follow_up_id=follow_up.pk, new_recipient_id=revoked.pk)


def test_recipient_change_rejects_non_owner(owner: Membership) -> None:
    _, follow_up, _, other = _setup_recipient_change(owner)
    member = make_membership(workspace=owner.workspace, user=make_user(email="m@example.test"))
    with pytest.raises(InvalidTransition):
        change_recipient(actor=member, follow_up_id=follow_up.pk, new_recipient_id=other.pk)


def test_recipient_change_endpoint_owner_only(client: Client, owner: Membership) -> None:
    _, follow_up, _, other = _setup_recipient_change(owner)
    member = make_membership(workspace=owner.workspace, user=make_user(email="m@example.test"))
    sign_in(client, member)
    response = post_json(
        client,
        _recipient_url(owner, follow_up.pk),
        {"new_recipient_id": str(other.pk)},
    )
    assert response.status_code == 403


def test_recipient_change_endpoint_round_trip(client: Client, owner: Membership) -> None:
    _, follow_up, _, other = _setup_recipient_change(owner)
    response = post_json(
        client,
        _recipient_url(owner, follow_up.pk),
        {"new_recipient_id": str(other.pk)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recipient"]["member"]["id"] == str(other.pk)


def test_recipient_change_endpoint_cross_workspace(client: Client, owner: Membership) -> None:
    _, follow_up, _, _ = _setup_recipient_change(owner)
    outsider = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    sign_in(client, outsider)
    response = post_json(
        client,
        _recipient_url(owner, follow_up.pk),
        {"new_recipient_id": str(outsider.pk)},
    )
    assert response.status_code == 404


def test_manual_report_reassignment_retargets_pending_follow_up(
    owner: Membership,
) -> None:
    submitter = owner
    assignee = make_membership(workspace=owner.workspace, user=make_user(email="a@example.test"))
    other = make_membership(workspace=owner.workspace, user=make_user(email="o@example.test"))
    link_slack(submitter)
    link_slack(assignee, user_id="U0ASSIGN")
    link_slack(other, user_id="U0OTHER")
    problem = make_problem(actor=owner, title="Manual")
    report = make_report(actor=submitter, title="Manual case")
    report = assign_report(
        actor=owner, report_id=report.pk, expected_version=1, assignee_id=assignee.pk
    )
    report = link_report(
        actor=owner, report_id=report.pk, expected_version=2, problem_id=problem.pk
    )
    confirm_fix(
        actor=owner, problem_id=problem.pk, expected_version=1, fix_note="Fixed.", fix_version="1.0"
    )
    follow_up = report.follow_ups.get()
    assert follow_up.recipient_id == assignee.pk
    new_version = report.version
    report = assign_report(
        actor=owner, report_id=report.pk, expected_version=new_version, assignee_id=other.pk
    )
    follow_up.refresh_from_db()
    assert follow_up.recipient_id == other.pk
    activity = Activity.objects.get(
        record_type=Activity.RecordType.FOLLOW_UP,
        record_id=follow_up.pk,
        action=Activity.Action.RECIPIENT_CHANGED,
    )
    assert activity.metadata["report_reassigned"] is True


def test_manual_report_reassignment_leaves_recorded_follow_up_alone(
    owner: Membership,
) -> None:
    submitter = owner
    assignee = make_membership(workspace=owner.workspace, user=make_user(email="a@example.test"))
    other = make_membership(workspace=owner.workspace, user=make_user(email="o@example.test"))
    link_slack(submitter)
    link_slack(assignee, user_id="U0ASSIGN")
    link_slack(other, user_id="U0OTHER")
    problem = make_problem(actor=owner, title="Manual")
    report = make_report(actor=submitter, title="Manual case")
    report = assign_report(
        actor=owner, report_id=report.pk, expected_version=1, assignee_id=assignee.pk
    )
    report = link_report(
        actor=owner, report_id=report.pk, expected_version=2, problem_id=problem.pk
    )
    confirm_fix(
        actor=owner, problem_id=problem.pk, expected_version=1, fix_note="Fixed.", fix_version="1.0"
    )
    follow_up = report.follow_ups.get()
    record_outcome(
        actor=assignee,
        follow_up_id=follow_up.pk,
        state=FollowUp.ContactState.CONTACTED,
        note="Spoke.",
        expected_version=follow_up.version,
    )
    new_version = report.version
    assign_report(
        actor=owner, report_id=report.pk, expected_version=new_version, assignee_id=other.pk
    )
    follow_up.refresh_from_db()
    assert follow_up.recipient_id == assignee.pk
