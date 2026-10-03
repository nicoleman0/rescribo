"""Follow-up delivery tasks use PostgreSQL and mocked Slack API boundaries."""

from datetime import timedelta
from http.client import RemoteDisconnected
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.test import Client, override_settings
from django.utils import timezone
from slack_sdk.errors import SlackApiError
from slack_sdk.web import SlackResponse

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from connections import slack_delivery
from connections.errors import SetupError
from connections.models import Connection, ExternalIdentity
from feedback.errors import (
    ConfirmationRequired,
    DeliveryNotReady,
    InvalidTransition,
    VersionConflict,
)
from feedback.follow_ups import (
    cancel_notification,
    draft_notification,
    mark_notification_delivered,
    send_notification_again,
)
from feedback.models import Activity, Report
from feedback.models import ReportNotificationOperation as Operation
from feedback.problems import confirm_fix
from feedback.reports import assign_report, link_report

pytestmark = pytest.mark.django_db


TEAM = "T0TEAM"
SLACK_USER = "U0ACTOR"


def setup_delivery(
    *, state: str = "queued", team_id: str = TEAM
) -> tuple[Membership, Report, Operation, Connection]:
    actor = make_membership(
        role="owner",
        user=make_user(email=f"{uuid4()}@example.test"),
        workspace=make_workspace(slug=str(uuid4())),
    )
    problem = make_problem(actor=actor, title="Delivery test")
    report = make_report(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Confirmed fix.",
        fix_version="1.0",
    )
    report = Report.objects.select_related("problem", "source").get(pk=report.pk)
    now = timezone.now()
    operation = make_notification(
        report=report,
        state=state,
        due_at=now,
        message="The fix is available.",
        approved_by=actor,
        approved_at=now,
    )
    connection = Connection.objects.create(
        workspace=actor.workspace,
        provider=Connection.Provider.SLACK,
        external_id=team_id,
        identity="Example Slack",
        status=Connection.Status.ACTIVE,
        credential="encrypted",
    )
    ExternalIdentity.objects.create(
        workspace=actor.workspace,
        membership=operation.recipient,
        provider=Connection.Provider.SLACK,
        provider_team_id=team_id,
        provider_user_id=SLACK_USER,
    )
    return actor, report, operation, connection


def slack_error(code: str, *, status_code: int = 200) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/test",
        req_args={},
        data={"ok": False, "error": code},
        headers={},
        status_code=status_code,
    )
    return SlackApiError(code, response)


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def notification_url(membership: Membership, follow_up_id: Any, action: str) -> str:
    return (
        f"/api/workspaces/{membership.workspace_id}/follow-ups/{follow_up_id}/"
        f"notification/{action}/"
    )


def test_stale_approval_is_cancelled_before_any_slack_write() -> None:
    actor, report, operation, _ = setup_delivery()
    Report.objects.filter(pk=report.pk).update(version=report.version + 1)

    with (
        patch("integrations.slack.client.conversations_open") as open_dm,
        patch("integrations.slack.client.chat_post_message") as post_message,
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert operation.state == "cancelled"
    assert operation.invalidation_reason == "stale"
    assert operation.lease_token is None
    open_dm.assert_not_called()
    post_message.assert_not_called()


def test_reassignment_during_post_preserves_uncertain_remote_result() -> None:
    actor, report, operation, _ = setup_delivery()
    recipient = make_membership(
        workspace=actor.workspace, user=make_user(email="replacement@example.test")
    )

    def post_then_reassign(*args: Any, **kwargs: Any) -> dict[str, str]:
        assign_report(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            assignee_id=recipient.pk,
        )
        draft_notification(actor=actor, follow_up_id=operation.follow_up_id)
        return {"ts": "171.9"}

    with (
        patch(
            "integrations.slack.client.conversations_open",
            return_value={"channel": {"id": "D1"}},
        ),
        patch("integrations.slack.client.chat_post_message", side_effect=post_then_reassign),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)
    operation.refresh_from_db()
    assert operation.state == "uncertain"
    assert operation.invalidated_at is not None
    assert (operation.remote_conversation_id, operation.remote_message_id) == ("D1", "171.9")
    assert Operation.objects.filter(follow_up=operation.follow_up).count() == 1
    with patch("connections.slack_delivery.dispatch_task") as dispatch:
        slack_delivery.sweep()
    dispatch.assert_not_called()


def test_ambiguous_post_failure_after_reassignment_stays_uncertain() -> None:
    actor, report, operation, _ = setup_delivery()
    recipient = make_membership(workspace=actor.workspace, user=make_user())

    def reassign_then_lose_response(*args: Any, **kwargs: Any) -> Any:
        assign_report(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            assignee_id=recipient.pk,
        )
        raise TimeoutError("response lost after write")

    with (
        patch(
            "integrations.slack.client.conversations_open",
            return_value={"channel": {"id": "D1"}},
        ),
        patch(
            "integrations.slack.client.chat_post_message",
            side_effect=reassign_then_lose_response,
        ),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)
    operation.refresh_from_db()
    assert operation.state == "uncertain"
    assert operation.invalidated_at is not None
    with patch("connections.slack_delivery.dispatch_task") as dispatch:
        slack_delivery.sweep()
    dispatch.assert_not_called()


def test_worker_loss_after_reassignment_expires_to_uncertain() -> None:
    actor, report, operation, _ = setup_delivery()
    recipient = make_membership(workspace=actor.workspace, user=make_user())

    def reassign_then_die(*args: Any, **kwargs: Any) -> Any:
        assign_report(
            actor=actor,
            report_id=report.pk,
            expected_version=report.version,
            assignee_id=recipient.pk,
        )
        raise SystemExit("worker lost during post")

    with (
        patch(
            "integrations.slack.client.conversations_open",
            return_value={"channel": {"id": "D1"}},
        ),
        patch("integrations.slack.client.chat_post_message", side_effect=reassign_then_die),
        pytest.raises(SystemExit),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)
    operation.refresh_from_db()
    assert operation.state == "uncertain" and operation.lease_token is not None
    with pytest.raises(DeliveryNotReady):
        cancel_notification(
            actor=actor,
            follow_up_id=operation.follow_up_id,
            notification_id=operation.pk,
            draft_version=operation.draft_version,
        )
    Operation.objects.filter(pk=operation.pk).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    with patch("connections.slack_delivery.dispatch_task") as dispatch:
        slack_delivery.sweep()
    operation.refresh_from_db()
    assert operation.state == "uncertain" and operation.lease_token is None
    dispatch.assert_not_called()


def test_success_stores_remote_ids_and_activity() -> None:
    actor, _, operation, _ = setup_delivery()
    with (
        patch(
            "integrations.slack.client.conversations_open", return_value={"channel": {"id": "D1"}}
        ),
        patch("integrations.slack.client.chat_post_message", return_value={"ts": "171.2"}) as post,
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert (operation.state, operation.remote_conversation_id, operation.remote_message_id) == (
        "sent",
        "D1",
        "171.2",
    )
    assert operation.sent_at is not None
    post.assert_called_once()
    assert post.call_args.kwargs["blocks"][1]["elements"][0]["action_id"] == "follow_up_contacted"
    activity = Activity.objects.get(action=Activity.Action.NOTIFICATION_SENT)
    assert (activity.workspace_id, activity.record_id, activity.actor_system) == (
        actor.workspace_id,
        operation.follow_up_id,
        "slack_delivery",
    )


def test_conversations_open_failure_is_failed_and_does_not_post() -> None:
    _, _, operation, _ = setup_delivery()
    with (
        patch(
            "integrations.slack.client.conversations_open",
            side_effect=slack_error("channel_not_found"),
        ),
        patch("integrations.slack.client.chat_post_message") as post,
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert operation.state == "failed"
    post.assert_not_called()


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (slack_error("channel_not_found", status_code=400), "failed"),
        (slack_error("internal_error", status_code=500), "uncertain"),
        (TimeoutError("request timed out"), "uncertain"),
        (SetupError("credential_unavailable", "Restore credentials."), "failed"),
    ],
    ids=["4xx", "5xx", "timeout", "pre-request-setup-error"],
)
def test_post_error_classification(error: Exception, expected_state: str) -> None:
    _, _, operation, _ = setup_delivery()
    with (
        patch(
            "integrations.slack.client.conversations_open", return_value={"channel": {"id": "D1"}}
        ),
        patch("integrations.slack.client.chat_post_message", side_effect=error),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert operation.state == expected_state


def test_post_without_ts_is_uncertain() -> None:
    _, _, operation, _ = setup_delivery()
    with (
        patch(
            "integrations.slack.client.conversations_open", return_value={"channel": {"id": "D1"}}
        ),
        patch("integrations.slack.client.chat_post_message", return_value={"ok": True}),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert operation.state == "uncertain"
    assert operation.safe_error == "write_outcome_unknown"


@override_settings(RESCRIBO_SLACK_FAKE_DELIVERY=False)
def test_real_sdk_does_not_retry_after_post_write_disconnect() -> None:
    _, _, operation, _ = setup_delivery()
    response = {
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": '{"ok":true,"ts":"171.1","channel":"D1"}',
    }
    with (
        patch("integrations.slack.client.decrypt", return_value="synthetic-token"),
        patch(
            "integrations.slack.client.conversations_open", return_value={"channel": {"id": "D1"}}
        ),
        patch(
            "slack_sdk.web.base_client.BaseClient._perform_urllib_http_request_internal",
            side_effect=[RemoteDisconnected("response lost after write"), response],
        ) as transport,
        patch("slack_sdk.http_retry.handler.time.sleep"),
    ):
        slack_delivery.send_follow_up_notification(operation.pk)
    operation.refresh_from_db()
    assert transport.call_count == 1
    assert operation.state == "uncertain"


def test_sweep_dispatch_and_sender_ignore_failed_and_uncertain_rows() -> None:
    actor, report, failed, _ = setup_delivery(state="failed")
    other_report = make_report(actor=actor)
    assert report.problem_id is not None
    other_report = link_report(
        actor=actor,
        report_id=other_report.pk,
        expected_version=1,
        problem_id=report.problem_id,
    )
    uncertain = make_notification(
        report=other_report,
        state="uncertain",
        due_at=timezone.now(),
        invalidated_at=timezone.now(),
        invalidation_reason=Operation.InvalidationReason.STALE,
    )
    with (
        patch("connections.slack_delivery.dispatch_task") as dispatch,
        patch("integrations.slack.client.conversations_open") as open_dm,
    ):
        slack_delivery.sweep()
        slack_delivery.send_follow_up_notification(failed.pk)
        slack_delivery.send_follow_up_notification(uncertain.pk)

    assert not dispatch.called
    open_dm.assert_not_called()
    failed.refresh_from_db()
    uncertain.refresh_from_db()
    assert (failed.state, uncertain.state) == ("failed", "uncertain")


def test_expired_lease_becomes_uncertain_and_live_lease_is_not_claimed_twice() -> None:
    _, _, expired, _ = setup_delivery()
    expired.lease_token = "00000000-0000-0000-0000-000000000001"
    expired.lease_expires_at = timezone.now() - timedelta(seconds=1)
    expired.save(update_fields=["lease_token", "lease_expires_at"])
    with patch("connections.slack_delivery.dispatch_task") as dispatch:
        slack_delivery.sweep()
    expired.refresh_from_db()
    assert expired.state == "uncertain"
    assert expired.safe_error == "worker_lease_expired"
    dispatch.assert_not_called()

    _, _, live, _ = setup_delivery(team_id=f"T0TEAM_{uuid4().hex}")
    live.lease_token = "00000000-0000-0000-0000-000000000002"
    live.lease_expires_at = timezone.now() + timedelta(minutes=1)
    live.save(update_fields=["lease_token", "lease_expires_at"])
    with (
        patch("integrations.slack.client.conversations_open") as open_dm,
        patch("integrations.slack.client.chat_post_message") as post,
    ):
        slack_delivery.send_follow_up_notification(live.pk)
    live.refresh_from_db()
    assert live.state == "queued"
    assert live.attempts == 0
    open_dm.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("problem", ["revoked", "unlinked", "inactive_connection"])
def test_recipient_or_connection_problems_fail_before_slack(problem: str) -> None:
    _, _, operation, connection = setup_delivery()
    if problem == "revoked":
        Membership.objects.filter(pk=operation.recipient_id).update(
            is_active=False, revoked_at=timezone.now()
        )
    elif problem == "unlinked":
        ExternalIdentity.objects.filter(membership_id=operation.recipient_id).delete()
    else:
        Connection.objects.filter(pk=connection.pk).update(status=Connection.Status.ERROR)

    with (
        patch("integrations.slack.client.conversations_open") as open_dm,
        patch("integrations.slack.client.chat_post_message") as post,
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    operation.refresh_from_db()
    assert operation.state == "failed"
    open_dm.assert_not_called()
    post.assert_not_called()


def test_revoked_token_disables_connection() -> None:
    _, _, operation, connection = setup_delivery()
    with (
        patch(
            "integrations.slack.client.conversations_open",
            side_effect=slack_error("token_revoked"),
        ),
        patch("integrations.slack.client.chat_post_message") as post,
    ):
        slack_delivery.send_follow_up_notification(operation.pk)

    connection.refresh_from_db()
    operation.refresh_from_db()
    assert (connection.status, connection.error_code) == ("error", "credentials_revoked")
    # Revocation cancels pending sends (spec §4); the attempt is not left retryable.
    assert (operation.state, operation.invalidation_reason) == ("cancelled", "disconnected")
    assert operation.lease_token is None
    post.assert_not_called()


def test_mark_delivered_only_accepts_uncertain_and_records_member_confirmation() -> None:
    actor, _, operation, _ = setup_delivery(state="uncertain")
    with pytest.raises(VersionConflict):
        mark_notification_delivered(
            actor=actor,
            follow_up_id=operation.follow_up_id,
            notification_id=operation.pk,
            draft_version=2,
        )
    marked = mark_notification_delivered(
        actor=actor,
        follow_up_id=operation.follow_up_id,
        notification_id=operation.pk,
        draft_version=1,
    )
    assert (marked.state, marked.delivery_confirmed_by_id) == ("sent", actor.pk)
    assert marked.delivery_confirmed_at is not None
    assert marked.remote_conversation_id == ""
    assert Activity.objects.filter(
        action=Activity.Action.NOTIFICATION_SENT,
        record_id=operation.follow_up_id,
        actor_membership=actor,
    ).exists()


def test_mark_delivered_keeps_a_later_report_change_on_the_record() -> None:
    # invalidate_pending_notifications flags an uncertain row this way after triage changes.
    actor, _, operation, _ = setup_delivery(state="uncertain")
    Operation.objects.filter(pk=operation.pk).update(
        invalidated_at=timezone.now(), invalidation_reason="reassigned"
    )
    marked = mark_notification_delivered(
        actor=actor,
        follow_up_id=operation.follow_up_id,
        notification_id=operation.pk,
        draft_version=1,
    )
    marked.refresh_from_db()
    assert (marked.state, marked.invalidation_reason) == ("sent", "reassigned")
    assert marked.delivery_confirmed_by_id == actor.pk


def test_mark_delivered_rejects_non_uncertain_state() -> None:
    actor, _, operation, _ = setup_delivery(state="failed")
    with pytest.raises(InvalidTransition):
        mark_notification_delivered(
            actor=actor,
            follow_up_id=operation.follow_up_id,
            notification_id=operation.pk,
            draft_version=1,
        )


def test_send_again_requires_confirmation_and_requeues_uncertain() -> None:
    actor, _, operation, _ = setup_delivery(state="uncertain")
    with pytest.raises(ConfirmationRequired):
        send_notification_again(
            actor=actor,
            follow_up_id=operation.follow_up_id,
            notification_id=operation.pk,
            draft_version=1,
            checked_slack=False,
        )
    with patch("feedback.follow_ups.dispatch_task"):
        queued = send_notification_again(
            actor=actor,
            follow_up_id=operation.follow_up_id,
            notification_id=operation.pk,
            draft_version=1,
            checked_slack=True,
        )
    assert queued.state == "queued"
    assert queued.approved_by_id == actor.pk


def test_cancel_uncertain_marks_cancelled_and_other_states_are_rejected() -> None:
    actor, _, operation, _ = setup_delivery(state="uncertain")
    cancelled = cancel_notification(
        actor=actor,
        follow_up_id=operation.follow_up_id,
        notification_id=operation.pk,
        draft_version=1,
    )
    assert (cancelled.state, cancelled.invalidation_reason) == (
        "cancelled",
        Operation.InvalidationReason.MEMBER_CANCELLED,
    )
    assert cancelled.invalidated_at is not None
    assert Activity.objects.filter(
        action=Activity.Action.NOTIFICATION_CANCELLED,
        record_id=operation.follow_up_id,
        actor_membership=actor,
    ).exists()


def test_notification_routes_cross_workspace_member_cannot_reach(client: Client) -> None:
    actor, _, operation, _ = setup_delivery(state="uncertain")
    sign_in(client, actor)

    url = notification_url(actor, operation.follow_up_id, "mark-delivered")
    response = client.post(
        url,
        {"notification_id": str(operation.pk), "draft_version": 1},
        content_type="application/json",
    )
    assert response.status_code == 200

    outsider = make_membership(
        workspace=make_workspace(slug=f"other-{uuid4()}"),
        user=make_user(email=f"outsider-{uuid4()}@example.test"),
    )
    sign_in(client, outsider)
    response = client.post(
        url,
        {"notification_id": str(operation.pk), "draft_version": 1},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_send_again_route_requires_checked_slack(client: Client) -> None:
    actor, _, operation, _ = setup_delivery(state="uncertain")
    sign_in(client, actor)
    url = notification_url(actor, operation.follow_up_id, "send-again")
    rejected = client.post(
        url,
        {"notification_id": str(operation.pk), "draft_version": 1, "checked_slack": False},
        content_type="application/json",
    )
    assert rejected.status_code == 400
    with patch("feedback.follow_ups.dispatch_task"):
        ok = client.post(
            url,
            {"notification_id": str(operation.pk), "draft_version": 1, "checked_slack": True},
            content_type="application/json",
        )
    assert ok.status_code == 202


def test_cancel_route_rejects_non_uncertain(client: Client) -> None:
    actor, _, operation, _ = setup_delivery(state="queued")
    sign_in(client, actor)
    url = notification_url(actor, operation.follow_up_id, "cancel")
    response = client.post(
        url,
        {"notification_id": str(operation.pk), "draft_version": 1},
        content_type="application/json",
    )
    assert response.status_code == 409


@override_settings(RESCRIBO_SLACK_FAKE_DELIVERY=True)
def test_fake_delivery_is_only_used_when_enabled() -> None:
    from integrations.slack.client import _delivery_client
    from integrations.slack.fake_delivery import FakeDeliveryClient

    assert isinstance(_delivery_client("ignored"), FakeDeliveryClient)


def test_real_delivery_client_is_used_by_default() -> None:
    from cryptography.fernet import Fernet
    from slack_sdk import WebClient

    from integrations.slack.client import _delivery_client
    from integrations.slack.fake_delivery import FakeDeliveryClient

    key = Fernet.generate_key().decode()
    fernet = Fernet(key.encode())
    credential = fernet.encrypt(b"xoxb-token").decode()
    with override_settings(RESCRIBO_CREDENTIAL_KEY=key):
        client_obj = _delivery_client(credential)
    assert isinstance(client_obj, WebClient)
    assert not isinstance(client_obj, FakeDeliveryClient)
