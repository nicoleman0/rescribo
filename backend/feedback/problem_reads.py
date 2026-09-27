"""Workspace-scoped problem reads for the problems list and detail."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.db.models import Count, Prefetch, Q, QuerySet

from accounts.models import Membership
from feedback.errors import NotFound
from feedback.inbox import workspace_reports
from feedback.models import Activity, EngineeringIssue, Problem, Report


def _workspace_problems(*, actor: Membership) -> QuerySet[Problem]:
    # The workspace filter is applied before search, counting, and pagination.
    return (
        Problem.objects.filter(workspace_id=actor.workspace_id)
        .select_related("owner__user")
        .annotate(report_count=Count("reports"))
        .prefetch_related(
            Prefetch(
                "engineering_issues",
                queryset=EngineeringIssue.objects.filter(active=True),
                to_attr="active_issues",
            )
        )
    )


def search_problems(*, actor: Membership, text: str = "") -> QuerySet[Problem]:
    problems = _workspace_problems(actor=actor)
    text = text.strip()
    if text:
        problems = problems.filter(Q(title__icontains=text) | Q(summary__icontains=text))
    return problems.order_by("-created_at", "-id")


def get_problem(*, actor: Membership, problem_id: UUID) -> Problem:
    try:
        return _workspace_problems(actor=actor).get(pk=problem_id)
    except Problem.DoesNotExist as error:
        raise NotFound(record="problem") from error


def problem_reports(*, actor: Membership, problem_id: UUID) -> QuerySet[Report]:
    problem = get_problem(actor=actor, problem_id=problem_id)
    return workspace_reports(actor=actor).filter(problem=problem).order_by("created_at", "id")


def problem_activity(*, actor: Membership, problem_id: UUID) -> QuerySet[Activity]:
    problem = get_problem(actor=actor, problem_id=problem_id)
    return (
        Activity.objects.filter(
            workspace_id=actor.workspace_id,
            record_type=Activity.RecordType.PROBLEM,
            record_id=problem.pk,
        )
        .select_related("actor_membership__user")
        .order_by("-created_at", "-id")
    )


@dataclass(frozen=True)
class ActivityReferences:
    """Records named by activity metadata, resolved within the actor's workspace."""

    reports: dict[str, Report] = field(default_factory=dict)
    problems: dict[str, Problem] = field(default_factory=dict)
    members: dict[str, Membership] = field(default_factory=dict)


REFERENCE_KEYS = {
    "reports": ("report_id",),
    "problems": ("from_problem_id", "to_problem_id"),
    "members": ("from_assignee_id", "to_assignee_id"),
}


def activity_references(*, actor: Membership, rows: Iterable[Activity]) -> ActivityReferences:
    wanted: dict[str, set[str]] = {kind: set() for kind in REFERENCE_KEYS}
    for row in rows:
        for kind, keys in REFERENCE_KEYS.items():
            wanted[kind].update(_ids(row.metadata, keys))
    scope: dict[str, Any] = {"workspace_id": actor.workspace_id}
    return ActivityReferences(
        reports={
            str(row.pk): row
            for row in Report.objects.filter(pk__in=wanted["reports"], **scope).only("title")
        },
        problems={
            str(row.pk): row
            for row in Problem.objects.filter(pk__in=wanted["problems"], **scope).only("title")
        },
        members={
            str(row.pk): row
            for row in Membership.objects.filter(pk__in=wanted["members"], **scope).select_related(
                "user"
            )
        },
    )


def _ids(metadata: dict[str, Any], keys: Iterable[str]) -> set[str]:
    return {str(metadata[key]) for key in keys if metadata.get(key)}
