"""Match run lifecycle: queue with the report change, rank in a worker, save only fresh results.

Matching never links, dismisses, or changes a report or problem.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from django.db import DatabaseError, transaction
from django.utils import timezone

from feedback.models import Report
from matching.adapter import MatcherResult, run_matcher
from matching.contract import CONTRACT_VERSION, ContractError, ErrorCategory, MatchRequest
from matching.models import MatchRun, MatchSuggestion
from matching.registry import active_config, configs, supported_algorithms
from matching.retrieval import Retrieved, load_candidates, retrieve_candidate_ids
from operations.dispatch import dispatch_task
from operations.retries import next_retry_at

logger = logging.getLogger(__name__)

RUN_TASK = "matching.tasks.run_match"
LEASE = timedelta(minutes=2)
MAX_ATTEMPTS = 3
# Failures another attempt can fix. Contract and version failures never retry.
TRANSIENT = frozenset(
    {ErrorCategory.RETRIEVAL_FAILED, ErrorCategory.PROCESS_FAILED, ErrorCategory.TIMEOUT}
)
# The on-commit dispatch normally runs first; recovery waits so it does not race it.
RECOVERY_GRACE = timedelta(seconds=30)


class StaleInput(Exception):
    """The report or a candidate changed after the run's snapshot."""


def request_match(*, report: Report, now: datetime) -> MatchRun | None:
    """Queue a run for the report's current version, superseding any active run.

    Call inside the transaction that changed the report, after locking it. Dispatch happens
    after commit, so capture never waits on or fails with matching.
    """
    if report.triage_state != Report.TriageState.NEW:
        return None
    MatchRun.objects.filter(report=report, state__in=MatchRun.ACTIVE_STATES).update(
        state=MatchRun.State.STALE,
        failure=ErrorCategory.STALE_SNAPSHOT,
        completed_at=now,
        lease_token=None,
        lease_expires_at=None,
    )
    config = active_config()
    run = MatchRun.objects.create(
        workspace_id=report.workspace_id,
        report=report,
        report_version=report.version,
        contract_version=CONTRACT_VERSION,
        algorithm_version=config.algorithm_version,
        config_version=config.config_version,
        due_at=now,
        created_at=now,
    )
    transaction.on_commit(lambda: dispatch_task(RUN_TASK, str(run.pk)))
    return run


def execute_run(run_id: UUID, *, now: datetime | None = None) -> None:
    run = _claim(run_id, now=now or timezone.now())
    if run is None:
        return
    assert run.lease_token is not None
    try:
        _rank_and_save(run)
    except StaleInput:
        _mark_stale(run.pk, run.lease_token)
    except ContractError as error:
        _fail(run.pk, run.lease_token, error.category, now=timezone.now())


def recover_runs(*, now: datetime | None = None) -> None:
    """Expire abandoned leases and dispatch due runs. Claiming makes duplicates harmless."""
    current = now or timezone.now()
    expired = MatchRun.objects.filter(
        state=MatchRun.State.RUNNING, lease_expires_at__lt=current
    ).values_list("pk", "lease_token")
    for run_id, token in expired:
        _fail(run_id, token, ErrorCategory.PROCESS_FAILED, now=current)
    due = MatchRun.objects.filter(
        state=MatchRun.State.PENDING, due_at__lte=current - RECOVERY_GRACE
    ).values_list("pk", flat=True)
    for run_id in due:
        dispatch_task(RUN_TASK, str(run_id))


def _claim(run_id: UUID, *, now: datetime) -> MatchRun | None:
    with transaction.atomic():
        run = MatchRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None or run.state != MatchRun.State.PENDING or run.due_at > now:
            return None
        run.state = MatchRun.State.RUNNING
        run.attempts += 1
        run.lease_token = uuid4()
        run.lease_expires_at = now + LEASE
        run.save(update_fields=["state", "attempts", "lease_token", "lease_expires_at"])
        return run


def _current_report(run: MatchRun) -> Report:
    report = Report.objects.filter(pk=run.report_id, workspace_id=run.workspace_id).first()
    if (
        report is None
        or report.version != run.report_version
        or report.triage_state != Report.TriageState.NEW
    ):
        raise StaleInput()
    return report


def _rank_and_save(run: MatchRun) -> None:
    report = _current_report(run)
    config = configs().get(run.config_version)
    if config is None:
        raise ContractError(ErrorCategory.UNSUPPORTED_VERSION, "config file removed")
    started = time.monotonic()
    if run.candidates is None:
        try:
            problem_ids = retrieve_candidate_ids(report=report)
        except DatabaseError:
            raise ContractError(ErrorCategory.RETRIEVAL_FAILED, "retrieval query failed") from None
    else:
        # A retry ranks the same snapshot; any change since then makes the run stale.
        problem_ids = [UUID(candidate["id"]) for candidate in run.candidates]
    retrieved = load_candidates(
        workspace_id=run.workspace_id,
        problem_ids=problem_ids,
        max_linked_reports=config.max_linked_reports,
    )
    if retrieved is None or (run.candidates is not None and retrieved.snapshot != run.candidates):
        raise StaleInput()
    if run.candidates is None:
        retrieval_ms = round((time.monotonic() - started) * 1000)
        _record_snapshot(run, retrieved, retrieval_ms)
    _current_report(run)
    request: MatchRequest = {
        "contract_version": run.contract_version,
        "algorithm_version": run.algorithm_version,
        "config_version": run.config_version,
        "report": {
            "id": str(report.pk),
            "version": report.version,
            "title": report.title,
            "description": report.description,
        },
        "candidates": retrieved.candidates,
    }
    result = run_matcher(request, supported=supported_algorithms())
    _save(run, result, max_linked_reports=config.max_linked_reports)


def _record_snapshot(run: MatchRun, retrieved: Retrieved, retrieval_ms: int) -> None:
    updated = MatchRun.objects.filter(
        pk=run.pk, state=MatchRun.State.RUNNING, lease_token=run.lease_token
    ).update(candidates=retrieved.snapshot, retrieval_ms=retrieval_ms)
    if not updated:
        raise StaleInput()
    run.candidates = retrieved.snapshot


def _save(run: MatchRun, result: MatcherResult, *, max_linked_reports: int) -> None:
    now = timezone.now()
    with transaction.atomic():
        report = (
            Report.objects.select_for_update(of=("self",))
            .filter(pk=run.report_id, workspace_id=run.workspace_id)
            .first()
        )
        locked = _locked_run(run.pk, run.lease_token)
        if locked is None:
            return
        assert run.candidates is not None
        current = load_candidates(
            workspace_id=run.workspace_id,
            problem_ids=[UUID(candidate["id"]) for candidate in run.candidates],
            max_linked_reports=max_linked_reports,
        )
        if (
            report is None
            or report.version != run.report_version
            or report.triage_state != Report.TriageState.NEW
            or current is None
            or current.snapshot != run.candidates
        ):
            raise StaleInput()
        response = result.response
        if response["status"] == "ranked":
            locked.state = MatchRun.State.RANKED
            for rank, suggestion in enumerate(response["suggestions"], start=1):
                MatchSuggestion.objects.create(
                    workspace_id=run.workspace_id,
                    run=locked,
                    problem_id=UUID(suggestion["problem_id"]),
                    rank=rank,
                    score=suggestion["score"],
                    features=suggestion["features"],
                    evidence=suggestion["evidence"],
                )
        else:
            locked.state = MatchRun.State.ABSTAINED
            locked.abstain_reason = response["abstain_reason"]
        locked.matcher_build = result.build
        locked.ranking_ms = result.duration_ms
        _finish(locked, now=now)
        locked.save()
    _log(locked)


def _locked_run(run_id: UUID, token: UUID | None) -> MatchRun | None:
    """The run, locked, if this worker still holds its lease."""
    run = MatchRun.objects.select_for_update().filter(pk=run_id).first()
    if run is None or run.state != MatchRun.State.RUNNING or run.lease_token != token:
        return None
    return run


def _finish(run: MatchRun, *, now: datetime) -> None:
    run.completed_at = now
    run.lease_token = None
    run.lease_expires_at = None


def _mark_stale(run_id: UUID, token: UUID) -> None:
    """Discard the result, then queue a replacement if the report still awaits triage."""
    now = timezone.now()
    with transaction.atomic():
        hint = MatchRun.objects.filter(pk=run_id).values("report_id", "workspace_id").first()
        if hint is None:
            return
        report = (
            Report.objects.select_for_update(of=("self",))
            .filter(pk=hint["report_id"], workspace_id=hint["workspace_id"])
            .first()
        )
        run = _locked_run(run_id, token)
        if run is None:
            return
        run.state = MatchRun.State.STALE
        run.failure = ErrorCategory.STALE_SNAPSHOT
        _finish(run, now=now)
        run.save()
        if report is not None:
            request_match(report=report, now=now)
    _log(run)


def _fail(run_id: UUID, token: UUID | None, category: ErrorCategory, *, now: datetime) -> None:
    with transaction.atomic():
        run = _locked_run(run_id, token)
        if run is None:
            return
        if category in TRANSIENT and run.attempts < MAX_ATTEMPTS:
            run.state = MatchRun.State.PENDING
            run.due_at = next_retry_at(now=now, attempts=run.attempts)
            run.lease_token = None
            run.lease_expires_at = None
        else:
            run.state = MatchRun.State.FAILED
            run.failure = category
            _finish(run, now=now)
        run.save()
    _log(run, category=category)


def _log(run: MatchRun, *, category: ErrorCategory | None = None) -> None:
    # IDs, versions, outcome, and timings only; never report or problem text.
    fields: dict[str, Any] = {
        "run_id": str(run.pk),
        "state": run.state,
        "category": category or run.failure or None,
        "algorithm_version": run.algorithm_version,
        "config_version": run.config_version,
        "attempts": run.attempts,
        "retrieval_ms": run.retrieval_ms,
        "ranking_ms": run.ranking_ms,
    }
    logger.info("match run %s", " ".join(f"{key}={value}" for key, value in fields.items()))
