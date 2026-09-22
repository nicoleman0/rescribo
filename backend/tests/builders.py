"""Small explicit builders for account and feedback tests."""

from typing import Any

from accounts.models import Membership, User, Workspace
from feedback.models import Problem, Report


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
    )
    if overrides:
        raise ValueError(f"Unsupported report overrides: {', '.join(overrides)}")
    return submit_report(actor=actor, submission=submission).report
