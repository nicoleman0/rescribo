"""Workspace-scoped report reads for the inbox."""

from dataclasses import dataclass
from uuid import UUID

from django.db.models import Q, QuerySet

from accounts.models import Membership
from feedback.errors import NotFound
from feedback.models import Report


@dataclass(frozen=True)
class InboxFilters:
    text: str = ""
    customer: str = ""
    triage_state: str | None = None
    assignee_id: UUID | None = None
    unassigned: bool = False
    source_kind: str | None = None


def _workspace_reports(*, actor: Membership) -> QuerySet[Report]:
    # The workspace filter is applied before any search or filter condition.
    return Report.objects.filter(workspace_id=actor.workspace_id).select_related(
        "source", "submitted_by__user", "assignee__user", "problem"
    )


def search_reports(*, actor: Membership, filters: InboxFilters) -> QuerySet[Report]:
    reports = _workspace_reports(actor=actor)
    text = filters.text.strip()
    if text:
        reports = reports.filter(
            Q(title__icontains=text)
            | Q(description__icontains=text)
            | Q(source__snapshot_text__icontains=text)
        )
    customer = filters.customer.strip()
    if customer:
        reports = reports.filter(
            Q(customer_label__icontains=customer)
            | Q(customer_contact_reference__icontains=customer)
        )
    if filters.triage_state:
        reports = reports.filter(triage_state=filters.triage_state)
    if filters.unassigned:
        reports = reports.filter(assignee__isnull=True)
    elif filters.assignee_id is not None:
        reports = reports.filter(assignee_id=filters.assignee_id)
    if filters.source_kind:
        reports = reports.filter(source__kind=filters.source_kind)
    return reports.order_by("-created_at", "-id")


def get_report(*, actor: Membership, report_id: UUID) -> Report:
    try:
        return _workspace_reports(actor=actor).get(pk=report_id)
    except Report.DoesNotExist as error:
        raise NotFound(record="report") from error


def workspace_directory(*, actor: Membership) -> QuerySet[Membership]:
    return (
        Membership.objects.filter(workspace_id=actor.workspace_id, is_active=True)
        .select_related("user")
        .order_by("user__full_name", "user__email")
    )
