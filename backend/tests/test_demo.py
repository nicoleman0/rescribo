"""Demo workspace: seeding, visitor isolation, provider guards, and the nightly reset."""

import json
from collections import Counter
from collections.abc import Iterator
from io import StringIO
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from builders import make_membership, make_report, make_user, make_workspace
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import Client, override_settings

from accounts.demo import DEMO_DETAIL, is_demo_workspace
from accounts.models import Invitation, Membership, Workspace
from accounts.session import SESSION_GENERATION_KEY
from connections import services
from connections.errors import SetupError
from connections.models import Connection
from connections.slack_delivery import send_follow_up_notification
from connections.slack_inbound import resolve_permalink
from feedback.deletion import delete_workspace
from feedback.demo import (
    DEMO_SLUG,
    OWNER_EMAIL,
    VISITOR_EMAIL,
    DemoSeedError,
    seed_demo,
)
from feedback.engineering_issues import link_issue, refresh_issue
from feedback.errors import IssueOperationError
from feedback.follow_ups import approve_notification
from feedback.models import (
    EngineeringIssue,
    FollowUp,
    IssueReconciliation,
    Problem,
    Report,
    ReportSource,
)
from feedback.models import ReportNotificationOperation as Notification
from feedback.tasks import reconcile_github_issues, reset_demo_workspace, sync_github_issue
from operations.github_issue_create import approve_draft, create_draft, request_recovery
from operations.models import ExternalOperation
from operations.tasks import (
    dispatch_due_operations,
    process_github_issue_create,
    reconcile_github_issue_create,
    revalidate_github_connection,
)

pytestmark = pytest.mark.django_db

PASSWORD = "Demo-visitor-2026!"


def demo() -> Workspace:
    return Workspace.objects.get(slug=DEMO_SLUG)


def signed_in(membership: Membership) -> Client:
    # Session login avoids the shared, Redis-backed login throttle across tests.
    client = Client()
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()
    return client


def visitor_client() -> Client:
    return signed_in(Membership.objects.get(workspace=demo(), user__email=VISITOR_EMAIL))


def visitor_password_is(password: str) -> bool:
    return get_user_model().objects.get(email=VISITOR_EMAIL).check_password(password)


def states(workspace: Workspace) -> dict[str, Counter[str]]:
    return {
        "reports": Counter(
            Report.objects.filter(workspace=workspace).values_list("triage_state", flat=True)
        ),
        "problems": Counter(
            Problem.objects.filter(workspace=workspace).values_list("state", flat=True)
        ),
        "contact": Counter(
            FollowUp.objects.filter(workspace=workspace).values_list("contact_state", flat=True)
        ),
        "delivery": Counter(
            Notification.objects.filter(workspace=workspace).values_list("state", flat=True)
        ),
        "issues": Counter(
            EngineeringIssue.objects.filter(workspace=workspace).values_list("access", flat=True)
        ),
        "issue_states": Counter(
            EngineeringIssue.objects.filter(workspace=workspace).values_list("state", flat=True)
        ),
        "operations": Counter(
            ExternalOperation.objects.filter(workspace=workspace).values_list("state", flat=True)
        ),
    }


def test_workspaces_are_not_demos_by_default() -> None:
    workspace = make_workspace()
    assert workspace.is_demo is False
    assert is_demo_workspace(workspace.pk) is False
    assert is_demo_workspace(make_workspace(slug="demo", is_demo=True).pk) is True


def test_seed_covers_every_main_workflow_state_and_resets_to_the_same_data() -> None:
    private = make_membership()
    private_report = make_report(actor=private, title="Private report")

    seed_demo(visitor_password=PASSWORD)
    first = states(demo())
    seed_demo()
    second = states(demo())

    assert first == second
    assert set(first["reports"]) == {"new", "linked", "dismissed"}
    assert set(first["problems"]) == {"open", "in_progress", "fix_available", "not_planned"}
    assert set(first["contact"]) == {"pending", "confirmed", "no_response", "still_affected"}
    assert set(first["delivery"]) == {"draft", "sent", "failed", "uncertain"}
    assert set(first["issues"]) == {"ok", "inaccessible"}
    assert set(first["issue_states"]) == {"open", "closed"}
    assert set(first["operations"]) == {"uncertain"}
    assert Problem.objects.filter(workspace=demo(), needs_review=True).exists()
    assert Report.objects.filter(workspace=private.workspace).get() == private_report
    assert not Membership.objects.filter(workspace=private.workspace).exclude(pk=private.pk)


def test_reset_keeps_the_visitor_password_unless_one_is_given() -> None:
    first = seed_demo()
    assert first.visitor_password
    assert seed_demo().visitor_password is None
    assert visitor_password_is(first.visitor_password)
    assert seed_demo(visitor_password=PASSWORD).visitor_password == PASSWORD
    assert visitor_password_is(PASSWORD)


def test_seed_refuses_a_real_workspace_with_the_demo_slug() -> None:
    real = make_workspace(slug=DEMO_SLUG)
    make_report(actor=make_membership(workspace=real))
    with pytest.raises(DemoSeedError):
        seed_demo()
    assert Report.objects.filter(workspace=real).count() == 1


def test_seed_refuses_demo_accounts_that_belong_to_another_workspace() -> None:
    make_membership(user=make_user(email=VISITOR_EMAIL))
    with pytest.raises(DemoSeedError):
        seed_demo()
    assert not Workspace.objects.filter(slug=DEMO_SLUG).exists()


def test_owner_has_no_password_and_the_command_prints_only_the_visitor() -> None:
    other = make_workspace(name="Acme Private", slug="acme-private")
    out = StringIO()
    with override_settings(RESCRIBO_DEMO_PASSWORD=PASSWORD):
        call_command("seed_demo", "--json", stdout=out)
    printed = json.loads(out.getvalue())
    assert printed == {
        "workspace_id": str(demo().pk),
        "email": VISITOR_EMAIL,
        "password": PASSWORD,
    }
    assert OWNER_EMAIL not in out.getvalue()
    assert other.name not in out.getvalue()
    owner = get_user_model().objects.get(email=OWNER_EMAIL)
    assert not owner.has_usable_password()
    visitor = Membership.objects.get(workspace=demo(), user__email=VISITOR_EMAIL)
    assert visitor.role == Membership.Role.MEMBER
    assert Membership.objects.filter(user__email=VISITOR_EMAIL).count() == 1


def test_command_reports_a_refused_seed() -> None:
    make_workspace(slug=DEMO_SLUG)
    with pytest.raises(CommandError):
        call_command("seed_demo", stdout=StringIO())


def test_visitor_cannot_reach_private_workspaces_or_owner_actions() -> None:
    private = make_membership()
    seed_demo(visitor_password=PASSWORD)
    client = visitor_client()
    workspace = demo()
    owner = Membership.objects.get(workspace=workspace, user__email=OWNER_EMAIL)
    base = f"/api/workspaces/{workspace.pk}"

    assert client.get(f"/api/workspaces/{private.workspace_id}/reports/").status_code == 404
    session = client.get("/api/auth/session/").json()
    assert [item["workspace"]["id"] for item in session["memberships"]] == [str(workspace.pk)]
    assert client.get(f"{base}/reports/").status_code == 200

    refused = [
        client.post(
            f"{base}/invitations/",
            {"email": "friend@example.com", "role": "member"},
            content_type="application/json",
        ),
        client.post(
            f"{base}/memberships/{owner.pk}/role/",
            {"role": "member"},
            content_type="application/json",
        ),
        client.post(
            f"{base}/memberships/{owner.pk}/password-reset/", {}, content_type="application/json"
        ),
        client.post(f"{base}/memberships/{owner.pk}/revoke/", {}, content_type="application/json"),
        client.post(
            f"{base}/delete/", {"confirmation": DEMO_SLUG}, content_type="application/json"
        ),
    ]
    assert [response.status_code for response in refused] == [403] * len(refused)
    owner.refresh_from_db()
    assert (owner.role, owner.is_active) == (Membership.Role.OWNER, True)
    assert not Invitation.objects.filter(workspace=workspace).exists()
    assert Workspace.objects.filter(pk=workspace.pk).exists()


def test_nightly_reset_restores_the_seed_and_never_creates_a_demo() -> None:
    reset_demo_workspace()
    assert not Workspace.objects.filter(slug=DEMO_SLUG).exists()

    private = make_membership()
    private_report = make_report(actor=private, title="Private report")
    seed_demo(visitor_password=PASSWORD)
    seeded = states(demo())
    titles = set(Report.objects.filter(workspace=demo()).values_list("title", flat=True))
    Report.objects.filter(workspace=demo()).update(title="Vandalised")

    reset_demo_workspace()

    assert set(Report.objects.filter(workspace=demo()).values_list("title", flat=True)) == titles
    assert states(demo()) == seeded
    private_report.refresh_from_db()
    assert private_report.title == "Private report"
    assert visitor_password_is(PASSWORD)


@pytest.fixture
def seeded() -> Workspace:
    seed_demo(visitor_password=PASSWORD)
    return demo()


def demo_owner() -> Membership:
    return Membership.objects.get(workspace=demo(), user__email=OWNER_EMAIL)


@pytest.fixture
def no_providers() -> Iterator[dict[str, MagicMock]]:
    """Fail the test if anything builds a real Slack or GitHub client."""
    with (
        patch("integrations.slack.client.WebClient") as slack,
        patch("feedback.engineering_issues.github_client") as issues_github,
        patch("operations.tasks.github_client") as operations_github,
    ):
        yield {"slack": slack, "issues": issues_github, "operations": operations_github}
    for client in (slack, issues_github, operations_github):
        client.assert_not_called()


def test_seed_and_demo_sends_never_build_a_slack_client(no_providers: Any) -> None:
    seed_demo(visitor_password=PASSWORD)
    waiting = FollowUp.objects.get(
        workspace=demo(), contact_state="pending", notifications__state="draft"
    )
    notification = waiting.notifications.get(state="draft")
    approve_notification(
        actor=demo_owner(),
        follow_up_id=waiting.pk,
        notification_id=notification.pk,
        draft_version=notification.draft_version,
    )
    send_follow_up_notification(notification.pk)
    notification.refresh_from_db()
    assert notification.state == Notification.State.SENT
    assert notification.remote_message_id


def test_github_actions_are_refused(seeded: Workspace, no_providers: Any) -> None:
    owner = demo_owner()
    linked = EngineeringIssue.objects.filter(workspace=seeded, state="open").first()
    assert linked is not None
    unlinked = Problem.objects.get(workspace=seeded, title__startswith="Add dark mode")
    uncertain = ExternalOperation.objects.get(workspace=seeded)
    actions = [
        lambda: link_issue(
            actor=owner,
            problem_id=unlinked.pk,
            expected_version=unlinked.version,
            reference="12",
        ),
        lambda: refresh_issue(
            actor=owner, problem_id=linked.problem_id, expected_issue_id=linked.pk
        ),
        lambda: create_draft(
            actor=owner, problem_id=unlinked.pk, expected_version=unlinked.version
        ),
        lambda: approve_draft(
            actor=owner,
            problem_id=unlinked.pk,
            draft_id=uncertain.pk,
            draft_version=1,
            approved=True,
        ),
        lambda: request_recovery(
            actor=owner, problem_id=uncertain.problem_id, operation_id=uncertain.pk
        ),
    ]
    for action in actions:
        with pytest.raises(IssueOperationError) as refused:
            action()
        assert refused.value.reason == "demo_workspace"

    response = visitor_client().post(
        f"/api/workspaces/{seeded.pk}/problems/{unlinked.pk}/issue/link/",
        {"expected_version": unlinked.version, "reference": "12"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "demo_workspace"
    assert response.json()["detail"] == DEMO_DETAIL


def test_github_workers_skip_the_demo(seeded: Workspace, no_providers: Any) -> None:
    issue = EngineeringIssue.objects.filter(workspace=seeded, state="open").first()
    assert issue is not None
    EngineeringIssue.objects.filter(pk=issue.pk).update(sync_requested_generation=1)
    uncertain = ExternalOperation.objects.get(workspace=seeded)
    ExternalOperation.objects.filter(pk=uncertain.pk).update(recovery_requested=True)
    queued = ExternalOperation.objects.create(
        kind=uncertain.kind,
        workspace=seeded,
        connection=uncertain.connection,
        problem=Problem.objects.get(workspace=seeded, title__startswith="Add dark mode"),
        requester=uncertain.requester,
        action_key=uuid4(),
        state=ExternalOperation.State.QUEUED,
        title="Queued by mistake",
        body="",
        destination=uncertain.destination,
        problem_version=1,
        binding_revision=uncertain.binding_revision,
    )
    github = Connection.objects.get(workspace=seeded, provider=Connection.Provider.GITHUB)

    with patch("operations.tasks.dispatch_task") as dispatch:
        sync_github_issue(str(issue.pk))
        reconcile_github_issues()
        dispatch_due_operations()
        revalidate_github_connection(str(github.pk))
        reconcile_github_issue_create(str(uncertain.pk))
        process_github_issue_create(str(queued.pk))

    issue.refresh_from_db()
    queued.refresh_from_db()
    assert issue.sync_lease_token is None
    assert not IssueReconciliation.objects.filter(connection=github).exists()
    dispatched = {call.args for call in dispatch.call_args_list}
    assert ("feedback.tasks.sync_github_issue", str(issue.pk)) not in dispatched
    assert (queued.state, queued.safe_error) == ("cancelled", "demo_workspace")
    github.refresh_from_db()
    assert github.status == Connection.Status.ACTIVE


def test_connection_settings_are_refused(seeded: Workspace, no_providers: Any) -> None:
    owner = demo_owner()
    slack = Connection.objects.get(workspace=seeded, provider=Connection.Provider.SLACK)
    actions = [
        lambda: services.start_setup(owner, "github", "session", "northwind-demo/web-app"),
        lambda: services.finish_setup(owner, "slack", "session", "state", "code"),
        lambda: services.disconnect(owner, "slack", slack.version),
        lambda: services.update_channel(owner, slack.version, "CDEMO", False),
        lambda: services.refresh_connection(owner, "slack", slack.version),
    ]
    for action in actions:
        with pytest.raises(SetupError) as refused:
            action()
        assert refused.value.code == "demo_workspace"

    response = signed_in(owner).post(
        f"/api/workspaces/{seeded.pk}/connections/slack/refresh/",
        {"version": slack.version},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "demo_workspace"
    slack.refresh_from_db()
    assert slack.status == Connection.Status.ACTIVE


def test_permalink_and_deletion_never_call_slack(seeded: Workspace, no_providers: Any) -> None:
    source = ReportSource.objects.filter(workspace=seeded, kind="slack").first()
    assert source is not None
    resolve_permalink(source.pk)
    source.refresh_from_db()
    assert (source.permalink, source.permalink_error) == ("", "")

    with patch("integrations.slack.client.revoke_token") as revoke:
        delete_workspace(demo_owner(), DEMO_SLUG)
    revoke.assert_not_called()
    assert not Workspace.objects.filter(slug=DEMO_SLUG).exists()


def test_demo_inbox_shows_no_match_suggestions(seeded: Workspace) -> None:
    report = Report.objects.filter(workspace=seeded, triage_state="new").first()
    assert report is not None
    response = visitor_client().get(f"/api/workspaces/{seeded.pk}/reports/{report.pk}/match/")
    assert response.status_code == 200
    assert response.json()["suggestions_enabled"] is False
    assert response.json()["run"] is None
