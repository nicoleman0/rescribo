"""Fictitious demo workspace, seeded through domain use cases and reset nightly."""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from accounts.models import Membership, Workspace
from connections.models import Connection, ExternalIdentity
from connections.slack_delivery import send_follow_up_notification
from feedback.deletion import purge_workspace_content
from feedback.follow_ups import approve_notification, draft_notification, record_outcome
from feedback.models import Activity, EngineeringIssue, FixRelease, FollowUp, Problem, Report
from feedback.models import ReportNotificationOperation as Notification
from feedback.problems import change_problem_state, confirm_fix, create_problem
from feedback.reports import assign_report, dismiss_report, link_report, submit_report
from feedback.services import write_activity, write_system_activity
from feedback.submissions import ReportSubmission, SourceSnapshot
from operations.models import ExternalOperation

DEMO_SLUG = "demo"
VISITOR_EMAIL = "demo@example.com"
OWNER_EMAIL = "demo-owner@example.com"
SLACK_TEAM = "TDEMO"
# Non-numeric, so a missed guard fails before any GitHub request.
GITHUB_INSTALLATION = "demo"
GITHUB_REPOSITORY = "northwind-demo/web-app"
# Not a Fernet token, so a missed guard cannot decrypt it into a Slack call.
SLACK_CREDENTIAL = "demo-not-a-credential"
# The reserved .invalid domain never resolves, so seeded links reach no real repository.
ISSUE_URL = "https://github.invalid/northwind-demo/web-app/issues/{number}"

COLLEAGUES = (
    ("sam.rivera@example.com", "Sam Rivera"),
    ("priya.nair@example.com", "Priya Nair"),
    ("jordan.lee@example.com", "Jordan Lee"),
)


class DemoSeedError(Exception):
    pass


@dataclass(frozen=True)
class SeedResult:
    workspace_id: str
    visitor_email: str
    # Set only when this run chose or replaced the visitor password.
    visitor_password: str | None


@dataclass(frozen=True)
class Team:
    owner: Membership
    visitor: Membership
    sam: Membership
    priya: Membership
    jordan: Membership


def seed_demo(*, visitor_password: str | None = None) -> SeedResult:
    """Create the demo workspace, or reset its content, and return the visitor sign-in."""
    with transaction.atomic():
        workspace = _demo_workspace()
        team, password = _team(workspace, visitor_password)
        _connections(workspace, team)
        purge_workspace_content(workspace)
        _seed_records(team, now=timezone.now())
    return SeedResult(
        workspace_id=str(workspace.pk), visitor_email=VISITOR_EMAIL, visitor_password=password
    )


def reset_demo(*, visitor_password: str | None = None) -> bool:
    """Reset an existing demo. Never creates one, so the nightly task is safe everywhere."""
    if not Workspace.objects.filter(slug=DEMO_SLUG, is_demo=True).exists():
        return False
    seed_demo(visitor_password=visitor_password)
    return True


def _demo_workspace() -> Workspace:
    workspace = Workspace.objects.select_for_update().filter(slug=DEMO_SLUG).first()
    if workspace is None:
        return Workspace.objects.create(name="Northwind (demo)", slug=DEMO_SLUG, is_demo=True)
    if not workspace.is_demo:
        raise DemoSeedError(f'Workspace "{DEMO_SLUG}" exists and is not a demo; refusing to reset.')
    return workspace


def _team(workspace: Workspace, visitor_password: str | None) -> tuple[Team, str | None]:
    emails = [OWNER_EMAIL, VISITOR_EMAIL, *(email for email, _ in COLLEAGUES)]
    elsewhere = (
        Membership.objects.filter(user__email__in=emails)
        .exclude(workspace=workspace)
        .values_list("user__email", flat=True)
    )
    if elsewhere:
        raise DemoSeedError(
            "Demo accounts must belong only to the demo workspace: " + ", ".join(sorted(elsewhere))
        )
    owner = _member(workspace, OWNER_EMAIL, "Demo Owner", Membership.Role.OWNER)
    visitor = _member(workspace, VISITOR_EMAIL, "Demo Visitor", Membership.Role.MEMBER)
    password = visitor_password
    if password is None and not visitor.user.has_usable_password():
        password = secrets.token_urlsafe(12)
    if password is not None:
        visitor.user.set_password(password)
        visitor.user.save(update_fields=["password"])
    sam, priya, jordan = (
        _member(workspace, email, name, Membership.Role.MEMBER) for email, name in COLLEAGUES
    )
    return Team(owner=owner, visitor=visitor, sam=sam, priya=priya, jordan=jordan), password


def _member(workspace: Workspace, email: str, full_name: str, role: str) -> Membership:
    user = get_user_model().objects.filter(email=email).first()
    if user is None:
        user = get_user_model().objects.create_user(email=email, full_name=full_name)
        # No password exists for anyone except the visitor, whose password is set separately.
        user.set_unusable_password()
        user.save(update_fields=["password"])
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    membership, _ = Membership.objects.update_or_create(
        workspace=workspace, user=user, defaults={"role": role, "is_active": True}
    )
    return membership


def _connections(workspace: Workspace, team: Team) -> None:
    Connection.objects.update_or_create(
        workspace=workspace,
        provider=Connection.Provider.SLACK,
        defaults={
            "external_id": SLACK_TEAM,
            "identity": "Northwind Slack (demo)",
            "credential": SLACK_CREDENTIAL,
            "status": Connection.Status.ACTIVE,
            "error_code": "",
        },
    )
    Connection.objects.update_or_create(
        workspace=workspace,
        provider=Connection.Provider.GITHUB,
        defaults={
            "external_id": GITHUB_INSTALLATION,
            "identity": "northwind-demo",
            "repository": GITHUB_REPOSITORY,
            "repository_id": "demo",
            "visibility": "private",
            "status": Connection.Status.ACTIVE,
            "error_code": "",
        },
    )
    for index, membership in enumerate(
        (team.owner, team.visitor, team.sam, team.priya, team.jordan)
    ):
        ExternalIdentity.objects.update_or_create(
            membership=membership,
            provider=Connection.Provider.SLACK,
            defaults={
                "workspace_id": workspace.pk,
                "provider_team_id": SLACK_TEAM,
                "provider_user_id": f"UDEMO{index}",
            },
        )


def _report(
    actor: Membership,
    *,
    title: str,
    customer: str,
    description: str,
    at: datetime,
    slack_text: str = "",
) -> Report:
    source = None
    if slack_text:
        source = SourceSnapshot(
            kind="slack",
            external_workspace_id=SLACK_TEAM,
            external_channel_id="CDEMOSUPPORT",
            external_message_id=f"{int(at.timestamp())}.{uuid4().int % 1000000:06d}",
            permalink="",
            author_external_id="UDEMOAUTHOR",
            author_display_name=actor.user.full_name,
            snapshot_text=slack_text,
        )
    submission = ReportSubmission(
        title=title,
        description=description,
        customer_label=customer,
        customer_contact_reference="",
        affected_version="4.12",
        source=source,
        submission_key=None if source else uuid4(),
    )
    return submit_report(actor=actor, submission=submission, now=at).report


def _issue(
    *,
    problem: Problem,
    actor: Membership,
    number: int,
    title: str,
    state: str,
    at: datetime,
    access: str = EngineeringIssue.Access.OK,
) -> EngineeringIssue:
    connection = Connection.objects.get(
        workspace_id=problem.workspace_id, provider=Connection.Provider.GITHUB
    )
    issue = EngineeringIssue.objects.create(
        workspace_id=problem.workspace_id,
        problem=problem,
        connection=connection,
        repository_id=connection.repository_id,
        connection_installation_id=connection.external_id,
        issue_id=f"demo-{number}",
        number=number,
        url=ISSUE_URL.format(number=number),
        title=title,
        state=state,
        state_reason="completed" if state == EngineeringIssue.State.CLOSED else "",
        provider_updated_at=at,
        last_successful_sync_at=at,
        access=access,
        sync_error="" if access == EngineeringIssue.Access.OK else "inaccessible",
        created_by=actor,
    )
    write_activity(
        actor=actor,
        action=Activity.Action.ENGINEERING_ISSUE_LINKED,
        record_type=Activity.RecordType.PROBLEM,
        record_id=problem.pk,
        metadata={"issue_url": issue.url, "issue_number": number},
        now=at,
    )
    return issue


def _link(actor: Membership, report: Report, problem: Problem, at: datetime) -> Report:
    return link_report(
        actor=actor,
        report_id=report.pk,
        expected_version=report.version,
        problem_id=problem.pk,
        now=at,
    )


def _seed_records(team: Team, *, now: datetime) -> None:
    owner, sam, priya, jordan = team.owner, team.sam, team.priya, team.jordan

    def ago(days: float) -> datetime:
        return now - timedelta(days=days)

    # Export timeouts: open, with a linked issue and a report first filed under the wrong problem.
    export = create_problem(
        actor=owner,
        title="CSV export times out for accounts with over 50,000 rows",
        summary="Large exports stop after 30 seconds and the download never starts.",
        owner_id=jordan.pk,
        now=ago(12),
    )
    invoice = create_problem(
        actor=owner,
        title="Invoice PDF shows the previous VAT rate",
        summary="Invoices generated since 1 July print 20% instead of the updated rate.",
        owner_id=jordan.pk,
        now=ago(11),
    )
    for title, customer, slack_text, problem, days in (
        (
            "Export spins forever on the yearly ledger",
            "Bluefin Logistics",
            "Bluefin can't export their yearly ledger, it just spins and never downloads.",
            export,
            12,
        ),
        ("Month-end export fails", "Quarry Analytics", "", export, 10),
    ):
        report = _report(
            sam,
            title=title,
            customer=customer,
            description="Customer reports the export never finishes.",
            at=ago(days),
            slack_text=slack_text,
        )
        _link(owner, report, problem, ago(days - 0.2))
    # Mistake: filed under the invoice problem, then moved to the export problem.
    misfiled = _report(
        priya,
        title="Download button greyed out after export starts",
        customer="Harbor & Pine Legal",
        description="Export of 80k matters never completes; button stays disabled.",
        at=ago(9),
    )
    misfiled = _link(owner, misfiled, invoice, ago(8.9))
    _link(owner, misfiled, export, ago(8.5))
    _issue(
        problem=export,
        actor=jordan,
        number=412,
        title="Stream large CSV exports instead of buffering",
        state=EngineeringIssue.State.OPEN,
        at=ago(11.5),
    )

    # Invoice VAT: in progress with an open issue.
    vat = _report(
        priya,
        title="Invoices show 20% VAT",
        customer="Maple Street Clinic",
        description="Accountant spotted the wrong VAT rate on three invoices.",
        at=ago(11),
        slack_text="Maple Street's accountant says our invoices still show 20% VAT.",
    )
    _link(owner, vat, invoice, ago(10.8))
    invoice.refresh_from_db()
    change_problem_state(
        actor=jordan,
        problem_id=invoice.pk,
        expected_version=invoice.version,
        action="start",
        now=ago(7),
    )
    _issue(
        problem=invoice,
        actor=jordan,
        number=398,
        title="Use the effective-dated VAT rate when rendering invoices",
        state=EngineeringIssue.State.OPEN,
        at=ago(10),
    )

    # Password reset emails: fixed, with follow-ups in every delivery and contact state.
    resets = create_problem(
        actor=owner,
        title="Password reset emails arrive after the link expires",
        summary="Reset emails are delayed by up to two hours; links expire after one.",
        owner_id=jordan.pk,
        now=ago(20),
    )
    reset_reports = []
    for title, customer, author in (
        ("Reset link already expired", "Copperleaf Studio", sam),
        ("Locked out after password reset", "Northwind Bakery", priya),
        ("Reset email took two hours", "Bluefin Logistics", sam),
        ("Can't reset password", "Quarry Analytics", priya),
        ("Reset email never arrived", "Harbor & Pine Legal", sam),
        ("Password reset loop", "Maple Street Clinic", team.visitor),
    ):
        report = _report(
            author,
            title=title,
            customer=customer,
            description="Customer could not sign in after requesting a password reset.",
            at=ago(19),
        )
        report = assign_report(
            actor=owner,
            report_id=report.pk,
            expected_version=report.version,
            assignee_id=author.pk,
            now=ago(18.9),
        )
        reset_reports.append(_link(owner, report, resets, ago(18.8)))
    _issue(
        problem=resets,
        actor=jordan,
        number=377,
        title="Send password reset emails from the priority queue",
        state=EngineeringIssue.State.CLOSED,
        at=ago(3),
    )
    resets.refresh_from_db()
    confirmed = confirm_fix(
        actor=jordan,
        problem_id=resets.pk,
        expected_version=resets.version,
        fix_note="Reset emails now go out within a minute. Released in 4.13.",
        fix_version="4.13",
        now=ago(2),
    )
    github_connection = Connection.objects.get(
        workspace_id=team.owner.workspace_id, provider=Connection.Provider.GITHUB
    )
    FixRelease.objects.create(
        problem=confirmed,
        workspace_id=team.owner.workspace_id,
        provider="github",
        external_id="413",
        repository_id=github_connection.repository_id,
        tag_name="v4.13",
        name="4.13",
        url=f"https://github.com/{GITHUB_REPOSITORY}/releases/tag/v4.13",
        published_at=ago(2) - timedelta(hours=1),
        linked_by=jordan,
        linked_at=ago(2),
    )
    _follow_ups(team, reset_reports)

    # Dark mode: declined with a reason.
    dark = create_problem(
        actor=owner,
        title="Add dark mode to the customer portal",
        summary="Requested by several customers who work night shifts.",
        now=ago(30),
    )
    request = _report(
        priya,
        title="Dark mode request",
        customer="Northwind Bakery",
        description="Night-shift staff find the portal too bright.",
        at=ago(30),
    )
    _link(owner, request, dark, ago(29.8))
    dark.refresh_from_db()
    change_problem_state(
        actor=owner,
        problem_id=dark.pk,
        expected_version=dark.version,
        action="decline",
        reason="Not on this year's roadmap. Browser extensions cover most cases.",
        now=ago(25),
    )

    # Calendar sync: issue creation whose result GitHub never confirmed.
    calendar = create_problem(
        actor=owner,
        title="Calendar sync creates duplicate events",
        summary="Recurring bookings appear twice in Google Calendar after a reschedule.",
        owner_id=jordan.pk,
        now=ago(4),
    )
    duplicate = _report(
        sam,
        title="Every rescheduled booking shows twice",
        customer="Copperleaf Studio",
        description="Duplicates appear after moving a recurring booking.",
        at=ago(4),
        slack_text="Copperleaf: every rescheduled booking is showing up twice in their calendar.",
    )
    _link(owner, duplicate, calendar, ago(3.9))
    _uncertain_issue_creation(calendar, jordan, at=ago(1))

    # Mobile sign-out: the linked issue was moved somewhere Rescribo cannot read.
    mobile = create_problem(
        actor=owner,
        title="Mobile app signs users out after an update",
        summary="Users must sign in again after every app store update.",
        owner_id=jordan.pk,
        now=ago(6),
    )
    signed_out = _report(
        priya,
        title="Signed out after updating the app",
        customer="Harbor & Pine Legal",
        description="Partners are signed out after each update.",
        at=ago(6),
    )
    _link(owner, signed_out, mobile, ago(5.8))
    _issue(
        problem=mobile,
        actor=jordan,
        number=455,
        title="Keep refresh tokens across app updates",
        state=EngineeringIssue.State.OPEN,
        at=ago(5),
        access=EngineeringIssue.Access.INACCESSIBLE,
    )

    # Inbox: untriaged reports and a dismissed duplicate.
    _report(
        sam,
        title="Search ignores accented names",
        customer="Maple Street Clinic",
        description="Searching for José returns no results.",
        at=ago(0.3),
        slack_text="Maple Street: searching for José finds nothing, but Jose works.",
    )
    _report(
        priya,
        title="Dashboard totals differ from the export",
        customer="Quarry Analytics",
        description="Revenue on the dashboard is 2% lower than in the CSV export.",
        at=ago(0.8),
    )
    duplicate_request = _report(
        sam,
        title="Dark mode please",
        customer="Copperleaf Studio",
        description="Same request as Northwind's.",
        at=ago(1.5),
    )
    # Mistake: a duplicate that should have been linked, dismissed instead.
    dismiss_report(
        actor=owner,
        report_id=duplicate_request.pk,
        expected_version=duplicate_request.version,
        now=ago(1.4),
    )


def _follow_ups(team: Team, reports: list[Report]) -> None:
    """Drive real follow-up use cases; demo sends go through the simulated Slack client."""
    follow_ups = {
        follow_up.report_id: follow_up
        for follow_up in FollowUp.objects.filter(report__in=[report.pk for report in reports])
    }
    contacted, no_answer, still_affected, failed, uncertain, waiting = (
        follow_ups[report.pk] for report in reports
    )
    for follow_up in (contacted, no_answer, still_affected, failed, uncertain):
        notification = draft_notification(actor=team.owner, follow_up_id=follow_up.pk)
        approve_notification(
            actor=team.owner,
            follow_up_id=follow_up.pk,
            notification_id=notification.pk,
            draft_version=notification.draft_version,
        )
    for follow_up in (contacted, no_answer, still_affected):
        send_follow_up_notification(_current_notification(follow_up).pk)
    _mark_unsent(failed, state=Notification.State.FAILED, error="provider_unavailable")
    _mark_unsent(uncertain, state=Notification.State.UNCERTAIN, error="write_outcome_unknown")
    draft_notification(actor=team.owner, follow_up_id=waiting.pk)
    for follow_up, state, note in (
        (contacted, FollowUp.ContactState.CONTACTED, "Called the office manager."),
        (contacted, FollowUp.ContactState.CONFIRMED, "Confirmed by phone; resets arrive at once."),
        (no_answer, FollowUp.ContactState.NO_RESPONSE, "Two messages, no reply after a week."),
        (still_affected, FollowUp.ContactState.STILL_AFFECTED, "Still delayed for SSO users."),
    ):
        follow_up.refresh_from_db()
        record_outcome(
            actor=team.owner,
            follow_up_id=follow_up.pk,
            state=state,
            note=note,
            expected_version=follow_up.version,
        )


def _current_notification(follow_up: FollowUp) -> Notification:
    return Notification.objects.exclude(state=Notification.State.CANCELLED).get(follow_up=follow_up)


def _mark_unsent(follow_up: FollowUp, *, state: str, error: str) -> None:
    """Failure states need a provider failure, which the demo never makes, so set them here."""
    notification = _current_notification(follow_up)
    if notification.state != Notification.State.QUEUED:
        raise ImproperlyConfigured("Demo notifications must be queued before marking a failure.")
    now = timezone.now()
    notification.state = state
    notification.safe_error = error
    notification.updated_at = now
    notification.save(update_fields=["state", "safe_error", "updated_at"])
    if state == Notification.State.FAILED:
        write_system_activity(
            workspace_id=follow_up.workspace_id,
            actor_system="slack_delivery",
            action=Activity.Action.NOTIFICATION_FAILED,
            record_type=Activity.RecordType.FOLLOW_UP,
            record_id=follow_up.pk,
            metadata={"safe_error": error},
            now=now,
        )


def _uncertain_issue_creation(problem: Problem, actor: Membership, *, at: datetime) -> None:
    problem.refresh_from_db()
    connection = Connection.objects.get(
        workspace_id=problem.workspace_id, provider=Connection.Provider.GITHUB
    )
    ExternalOperation.objects.create(
        kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
        workspace_id=problem.workspace_id,
        connection=connection,
        problem=problem,
        requester=actor,
        action_key=uuid4(),
        state=ExternalOperation.State.UNCERTAIN,
        title=problem.title,
        body=problem.summary,
        destination=connection.repository,
        repository_id=connection.repository_id,
        problem_version=problem.version,
        binding_revision=connection.binding_revision,
        attempts=1,
        due_at=at,
        started_at=at,
        completed_at=at,
        safe_error="write_outcome_unknown",
    )
