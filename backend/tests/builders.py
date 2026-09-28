"""Small explicit builders for account and feedback tests."""

from typing import Any
from uuid import uuid4

from django.utils import timezone

from accounts.models import Membership, User, Workspace
from connections.models import Connection
from feedback.models import EngineeringIssue, Problem, Report, ReportNotificationOperation


def make_user(**overrides: Any) -> User:
    values = {"email": "member@example.test", "full_name": "Test Member"}
    values.update(overrides)
    return User.objects.create_user(**values)


def make_workspace(**overrides: Any) -> Workspace:
    values = {"name": "Example", "slug": "example"}
    values.update(overrides)
    return Workspace.objects.create(**values)


def make_membership(**overrides: Any) -> Membership:
    user = overrides.pop("user", None) or make_user()
    workspace = overrides.pop("workspace", None) or make_workspace()
    values = {"user": user, "workspace": workspace}
    values.update(overrides)
    return Membership.objects.create(**values)


def make_problem(*, actor: Membership | None = None, **overrides: Any) -> Problem:
    from feedback.problems import create_problem

    actor = actor or make_membership()
    title = overrides.pop("title", "Example problem")
    summary = overrides.pop("summary", "")
    owner_id = overrides.pop("owner_id", None)
    if overrides:
        raise ValueError(f"Unsupported problem overrides: {', '.join(overrides)}")
    return create_problem(actor=actor, title=title, summary=summary, owner_id=owner_id)


def make_report(*, actor: Membership | None = None, source: Any = None, **overrides: Any) -> Report:
    from feedback.reports import submit_report
    from feedback.submissions import ReportSubmission

    actor = actor or make_membership()
    submission = ReportSubmission(
        title=overrides.pop("title", "Example report"),
        description=overrides.pop("description", ""),
        customer_label=overrides.pop("customer_label", ""),
        customer_contact_reference=overrides.pop("customer_contact_reference", ""),
        affected_version=overrides.pop("affected_version", ""),
        source=source,
        submission_key=overrides.pop("submission_key", uuid4() if source is None else None),
    )
    if overrides:
        raise ValueError(f"Unsupported report overrides: {', '.join(overrides)}")
    return submit_report(actor=actor, submission=submission).report


def make_notification(
    *, report: Report, state: str = "draft", **overrides: Any
) -> ReportNotificationOperation:
    """Persist a prepared notification directly; no production path creates one yet."""
    if report.problem is None:
        raise ValueError("A notification needs a linked report.")
    values: dict[str, Any] = {
        "workspace_id": report.workspace_id,
        "report": report,
        "problem": report.problem,
        "recipient": report.assignee or report.submitted_by,
        "resolution_revision": report.problem.resolution_revision,
        "report_version": report.version,
        "state": state,
    }
    if state == "sent":
        values.update(
            sent_at=report.updated_at, remote_conversation_id="D123", remote_message_id="171.1"
        )
    values.update(overrides)
    return ReportNotificationOperation.objects.create(**values)


def make_connection(*, workspace: Workspace | None = None, **overrides: Any) -> Connection:
    values: dict[str, Any] = {
        "workspace": workspace or make_workspace(),
        "provider": Connection.Provider.GITHUB,
        "external_id": "42",
        "identity": "acme",
        "status": Connection.Status.ACTIVE,
        "repository": "acme/widgets",
        "repository_id": "999",
        "visibility": "private",
    }
    values.update(overrides)
    return Connection.objects.create(**values)


def make_engineering_issue(
    *,
    problem: Problem,
    connection: Connection | None = None,
    created_by: Membership | None = None,
    **overrides: Any,
) -> EngineeringIssue:
    connection = connection or make_connection(workspace=problem.workspace)
    created_by = created_by or make_membership(
        workspace=problem.workspace, user=make_user(email=f"{uuid4()}@example.test")
    )
    values: dict[str, Any] = {
        "workspace": problem.workspace,
        "problem": problem,
        "connection": connection,
        "repository_id": connection.repository_id,
        "connection_installation_id": connection.external_id,
        "issue_id": "555",
        "number": 7,
        "url": "https://github.com/acme/widgets/issues/7",
        "title": "Example issue",
        "state": EngineeringIssue.State.OPEN,
        "provider_updated_at": timezone.now(),
        "created_by": created_by,
    }
    values.update(overrides)
    return EngineeringIssue.objects.create(**values)
