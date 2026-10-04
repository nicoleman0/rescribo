"""Member reads and decisions on match suggestions. Acceptance uses normal report linking."""

from datetime import datetime
from uuid import UUID

from django.db import transaction
from django.db.models import OuterRef, QuerySet, Subquery
from django.utils import timezone

from accounts.models import Membership
from feedback.errors import FeedbackError, NotFound
from feedback.models import Report
from feedback.reports import link_report
from feedback.services import locked_report
from matching.models import MatchRun, MatchSuggestion
from matching.runs import request_match


class SuggestionNotCurrent(FeedbackError):
    """The suggestion belongs to an older run or a run that did not rank."""

    reason = "suggestion_not_current"


class SuggestionDecided(FeedbackError):
    reason = "suggestion_decided"


class MatchNotRetryable(FeedbackError):
    """Only a failed latest run of an untriaged report can be retried."""

    reason = "match_not_retryable"


def latest_run(*, actor: Membership, report_id: UUID) -> MatchRun | None:
    if not Report.objects.filter(pk=report_id, workspace_id=actor.workspace_id).exists():
        raise NotFound(record="report")
    return _latest(workspace_id=actor.workspace_id, report_id=report_id)


def with_match_state(reports: QuerySet[Report]) -> QuerySet[Report]:
    """Annotate each report with its latest run's state, or None before the first run."""
    latest = MatchRun.objects.filter(
        workspace_id=OuterRef("workspace_id"), report_id=OuterRef("pk")
    ).order_by("-created_at", "-id")
    return reports.annotate(match_state=Subquery(latest.values("state")[:1]))


def _latest(*, workspace_id: UUID, report_id: UUID) -> MatchRun | None:
    return (
        MatchRun.objects.filter(workspace_id=workspace_id, report_id=report_id)
        .prefetch_related("suggestions__problem")
        .order_by("-created_at", "-id")
        .first()
    )


def suggestion_report_id(*, actor: Membership, suggestion_id: UUID) -> UUID:
    report_id = (
        MatchSuggestion.objects.filter(pk=suggestion_id, workspace_id=actor.workspace_id)
        .values_list("run__report_id", flat=True)
        .first()
    )
    if report_id is None:
        raise NotFound(record="suggestion")
    return report_id


def accept_suggestion(
    *,
    actor: Membership,
    suggestion_id: UUID,
    expected_version: int,
    now: datetime | None = None,
) -> MatchSuggestion:
    current = now or timezone.now()
    with transaction.atomic():
        report, suggestion = _locked_pending(actor=actor, suggestion_id=suggestion_id)
        # A triaged report is no longer what the suggestion answered.
        if report.triage_state != Report.TriageState.NEW:
            raise SuggestionNotCurrent()
        link_report(
            actor=actor,
            report_id=suggestion.run.report_id,
            expected_version=expected_version,
            problem_id=suggestion.problem_id,
            now=current,
        )
        return _decide(suggestion, MatchSuggestion.Decision.ACCEPTED, actor=actor, now=current)


def reject_suggestion(
    *, actor: Membership, suggestion_id: UUID, now: datetime | None = None
) -> MatchSuggestion:
    current = now or timezone.now()
    with transaction.atomic():
        _, suggestion = _locked_pending(actor=actor, suggestion_id=suggestion_id)
        return _decide(suggestion, MatchSuggestion.Decision.REJECTED, actor=actor, now=current)


def retry_match(*, actor: Membership, report_id: UUID, now: datetime | None = None) -> MatchRun:
    current = now or timezone.now()
    with transaction.atomic():
        report = locked_report(actor=actor, report_id=report_id)
        run = _latest(workspace_id=actor.workspace_id, report_id=report_id)
        if (
            run is None
            or run.state != MatchRun.State.FAILED
            or report.triage_state != Report.TriageState.NEW
        ):
            raise MatchNotRetryable()
        replacement = request_match(report=report, now=current)
        assert replacement is not None
        return replacement


def _locked_pending(*, actor: Membership, suggestion_id: UUID) -> tuple[Report, MatchSuggestion]:
    # Lock the report before the suggestion, the order workers use.
    report = locked_report(
        actor=actor, report_id=suggestion_report_id(actor=actor, suggestion_id=suggestion_id)
    )
    suggestion = (
        MatchSuggestion.objects.select_for_update(of=("self",))
        .select_related("run")
        .get(pk=suggestion_id, workspace_id=actor.workspace_id)
    )
    latest = _latest(workspace_id=actor.workspace_id, report_id=report.pk)
    if latest is None or latest.pk != suggestion.run_id or latest.state != MatchRun.State.RANKED:
        raise SuggestionNotCurrent()
    if suggestion.decision != MatchSuggestion.Decision.PENDING:
        raise SuggestionDecided()
    return report, suggestion


def _decide(
    suggestion: MatchSuggestion, decision: str, *, actor: Membership, now: datetime
) -> MatchSuggestion:
    suggestion.decision = decision
    suggestion.decided_by = actor
    suggestion.decided_at = now
    suggestion.save(update_fields=["decision", "decided_by", "decided_at"])
    return suggestion
