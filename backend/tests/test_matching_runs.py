"""Match run lifecycle against PostgreSQL and the real matcher binary."""

import stat
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace
from django.test import override_settings
from django.utils import timezone

from accounts.models import Membership
from feedback.models import Problem, Report
from feedback.problems import ProblemChanges, update_problem
from feedback.reports import ReportChanges, assign_report, link_report, update_report
from matching import runs
from matching.models import MatchRun, MatchSuggestion
from matching.runs import RUN_TASK, execute_run, recover_runs

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor() -> Membership:
    return make_membership()


@pytest.fixture(autouse=True)
def no_dispatch(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record wakeups instead of sending them to the broker."""
    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(runs, "dispatch_task", lambda name, ref: dispatched.append((name, ref)))
    return dispatched


def latest(report: Report) -> MatchRun:
    run = MatchRun.objects.filter(report=report).order_by("-created_at", "-id").first()
    assert run is not None
    return run


def run_latest(report: Report) -> MatchRun:
    run = latest(report)
    execute_run(run.pk)
    run.refresh_from_db()
    return run


def fake_matcher(tmp_path: Path, body: str) -> str:
    path = tmp_path / "matcher"
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def during_ranking(monkeypatch: pytest.MonkeyPatch, change: Callable[[], Any]) -> None:
    """Apply a change after retrieval, while the matcher runs."""
    real = runs.run_matcher

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        change()
        return real(*args, **kwargs)

    monkeypatch.setattr(runs, "run_matcher", wrapped)


def snapshot_ids(run: MatchRun) -> list[str]:
    assert run.candidates is not None
    return [candidate["id"] for candidate in run.candidates]


def test_creation_queues_a_run_dispatched_after_commit(
    actor: Membership,
    no_dispatch: list[tuple[str, str]],
    django_capture_on_commit_callbacks: Any,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        report = make_report(actor=actor, title="CSV export times out")
    run = latest(report)
    assert (run.state, run.report_version, run.config_version) == ("pending", 1, "lexical-1.0")
    assert run.candidates is None
    assert no_dispatch == [(RUN_TASK, str(run.pk))]


def test_queue_outage_keeps_the_report_and_a_pending_run(
    actor: Membership, monkeypatch: pytest.MonkeyPatch, django_capture_on_commit_callbacks: Any
) -> None:
    from operations import dispatch

    monkeypatch.setattr(runs, "dispatch_task", dispatch.dispatch_task)
    monkeypatch.setattr(dispatch.current_app.tasks, "get", lambda name: 1 / 0)
    with django_capture_on_commit_callbacks(execute=True):
        report = make_report(actor=actor)
    assert Report.objects.filter(pk=report.pk).exists()
    assert latest(report).state == "pending"


def test_matching_edit_supersedes_the_active_run(actor: Membership) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    first = latest(report)
    report = update_report(
        actor=actor,
        report_id=report.pk,
        expected_version=1,
        changes=ReportChanges(description="Only on large files"),
    )
    first.refresh_from_db()
    assert (first.state, first.failure) == ("stale", "stale_snapshot")
    assert (latest(report).state, latest(report).report_version) == ("pending", 2)

    update_report(
        actor=actor,
        report_id=report.pk,
        expected_version=2,
        changes=ReportChanges(customer_label="Acme"),
    )
    assert MatchRun.objects.filter(report=report).count() == 2


def test_triaged_reports_are_not_matched(actor: Membership) -> None:
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    update_report(
        actor=actor, report_id=report.pk, expected_version=2, changes=ReportChanges(title="New")
    )
    assert MatchRun.objects.filter(report=report).count() == 1


def test_ranks_only_same_workspace_problems(actor: Membership) -> None:
    own = make_problem(actor=actor, title="CSV export times out", summary="Large exports fail")
    make_problem(actor=actor, title="Dark mode colours are wrong")
    foreign_actor = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="o@example.test")
    )
    foreign = make_problem(actor=foreign_actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out", description="Large exports")

    run = run_latest(report)

    assert run.state == "ranked"
    assert str(foreign.pk) not in snapshot_ids(run)
    assert snapshot_ids(run)[0] == str(own.pk)
    suggestions = list(run.suggestions.order_by("rank"))
    assert [suggestion.problem_id for suggestion in suggestions][:1] == [own.pk]
    assert all(suggestion.workspace_id == actor.workspace_id for suggestion in suggestions)
    assert len(run.matcher_build) == 64
    assert run.retrieval_ms is not None and run.ranking_ms is not None
    # The snapshot holds IDs and versions, never text.
    assert "CSV" not in str(run.candidates)


def test_closed_problems_are_not_candidates(actor: Membership) -> None:
    from feedback.problems import change_problem_state

    problem = make_problem(actor=actor, title="CSV export times out")
    change_problem_state(
        actor=actor, problem_id=problem.pk, expected_version=1, action="decline", reason="No"
    )
    report = make_report(actor=actor, title="CSV export times out")
    run = run_latest(report)
    assert (run.state, run.abstain_reason, run.candidates) == ("abstained", "no_candidates", [])


def test_empty_pool_abstains(actor: Membership) -> None:
    run = run_latest(make_report(actor=actor, title="CSV export times out"))
    assert (run.state, run.abstain_reason) == ("abstained", "no_candidates")
    assert not run.suggestions.exists()


def test_linked_reports_are_capped_to_the_most_recent(actor: Membership) -> None:
    problem = make_problem(actor=actor, title="CSV export times out")
    start = timezone.now() - timedelta(days=1)
    linked = []
    for index in range(7):
        item = make_report(actor=actor, title=f"Export report {index}")
        link_report(actor=actor, report_id=item.pk, expected_version=1, problem_id=problem.pk)
        Report.objects.filter(pk=item.pk).update(created_at=start + timedelta(minutes=index))
        linked.append(str(item.pk))
    report = make_report(actor=actor, title="CSV export times out")

    run = run_latest(report)

    assert run.candidates is not None
    assert [item["id"] for item in run.candidates[0]["linked_reports"]] == linked[:1:-1]


def test_missing_executable_fails_without_retry(actor: Membership, tmp_path: Path) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    with override_settings(RESCRIBO_MATCHER_PATH=str(tmp_path / "absent")):
        run = run_latest(report)
    assert (run.state, run.failure, run.attempts) == ("failed", "executable_missing", 1)
    assert Report.objects.filter(pk=report.pk).exists()


def test_malformed_output_fails_without_retry(actor: Membership, tmp_path: Path) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    with override_settings(RESCRIBO_MATCHER_PATH=fake_matcher(tmp_path, "printf 'oops'")):
        run = run_latest(report)
    assert (run.state, run.failure) == ("failed", "invalid_response")
    assert not MatchSuggestion.objects.exists()


def test_oversized_request_is_rejected_not_truncated(actor: Membership) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export", description="times out " * 8000)
    run = run_latest(report)
    assert (run.state, run.failure) == ("failed", "invalid_request")


def test_timeouts_retry_with_a_bound(actor: Membership, tmp_path: Path) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    with override_settings(
        RESCRIBO_MATCHER_PATH=fake_matcher(tmp_path, "exec /bin/sleep 5"),
        RESCRIBO_MATCHER_TIMEOUT_SECONDS=0.2,
    ):
        run = run_latest(report)
        assert (run.state, run.attempts, run.failure) == ("pending", 1, "")
        assert run.due_at > timezone.now()
        for _ in range(2):
            MatchRun.objects.filter(pk=run.pk).update(due_at=timezone.now())
            execute_run(run.pk)
    run.refresh_from_db()
    assert (run.state, run.failure, run.attempts) == ("failed", "timeout", 3)


def test_retry_ranks_the_unchanged_snapshot(actor: Membership, tmp_path: Path) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    with override_settings(RESCRIBO_MATCHER_PATH=fake_matcher(tmp_path, "exit 1")):
        first = run_latest(report)
    assert first.state == "pending"
    MatchRun.objects.filter(pk=first.pk).update(due_at=timezone.now())
    execute_run(first.pk)
    first.refresh_from_db()
    assert first.state == "ranked"
    assert first.attempts == 2


def test_retry_after_a_candidate_change_is_stale(actor: Membership, tmp_path: Path) -> None:
    problem = make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    with override_settings(RESCRIBO_MATCHER_PATH=fake_matcher(tmp_path, "exit 1")):
        first = run_latest(report)
    update_problem(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        changes=ProblemChanges(title="CSV export times out for large files"),
    )
    MatchRun.objects.filter(pk=first.pk).update(due_at=timezone.now())
    execute_run(first.pk)
    first.refresh_from_db()
    assert (first.state, first.failure) == ("stale", "stale_snapshot")
    assert latest(report).state == "pending"


def test_report_change_during_ranking_is_stale_and_requeued(
    actor: Membership, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    during_ranking(
        monkeypatch,
        lambda: assign_report(
            actor=actor, report_id=report.pk, expected_version=1, assignee_id=actor.pk
        ),
    )
    run = run_latest(report)
    assert (run.state, run.failure) == ("stale", "stale_snapshot")
    assert not run.suggestions.exists()
    replacement = latest(report)
    assert (replacement.state, replacement.report_version) == ("pending", 2)


@pytest.mark.parametrize("change", ["problem_edit", "new_linked_report"])
def test_candidate_change_during_ranking_is_stale(
    actor: Membership, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    problem = make_problem(actor=actor, title="CSV export times out")
    other = make_report(actor=actor, title="Unrelated")
    report = make_report(actor=actor, title="CSV export times out")

    def apply() -> None:
        if change == "problem_edit":
            update_problem(
                actor=actor,
                problem_id=problem.pk,
                expected_version=1,
                changes=ProblemChanges(summary="Edited"),
            )
        else:
            link_report(actor=actor, report_id=other.pk, expected_version=1, problem_id=problem.pk)

    during_ranking(monkeypatch, apply)
    run = run_latest(report)
    assert run.state == "stale"
    assert latest(report).state == "pending"


def test_dismissed_during_ranking_is_stale_without_replacement(
    actor: Membership, monkeypatch: pytest.MonkeyPatch
) -> None:
    from feedback.reports import dismiss_report

    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    during_ranking(
        monkeypatch,
        lambda: dismiss_report(actor=actor, report_id=report.pk, expected_version=1),
    )
    run = run_latest(report)
    assert run.state == "stale"
    assert latest(report).pk == run.pk


def test_duplicate_dispatch_ranks_once(actor: Membership) -> None:
    make_problem(actor=actor, title="CSV export times out")
    report = make_report(actor=actor, title="CSV export times out")
    run = run_latest(report)
    execute_run(run.pk)
    assert run.state == "ranked"
    assert MatchSuggestion.objects.filter(run=run).count() == run.suggestions.count() >= 1
    assert MatchRun.objects.get(pk=run.pk).attempts == 1


def test_recovery_expires_leases_and_dispatches_due_runs(
    actor: Membership, no_dispatch: list[tuple[str, str]]
) -> None:
    now = timezone.now()
    abandoned = latest(make_report(actor=actor, title="First"))
    MatchRun.objects.filter(pk=abandoned.pk).update(
        state="running", attempts=1, lease_expires_at=now - timedelta(seconds=1)
    )
    waiting = latest(make_report(actor=actor, title="Second"))
    MatchRun.objects.filter(pk=waiting.pk).update(due_at=now - timedelta(minutes=5))
    fresh = latest(make_report(actor=actor, title="Third"))
    no_dispatch.clear()

    recover_runs(now=now)

    abandoned.refresh_from_db()
    assert (abandoned.state, abandoned.lease_token) == ("pending", None)
    assert (RUN_TASK, str(waiting.pk)) in no_dispatch
    assert (RUN_TASK, str(fresh.pk)) not in no_dispatch


def test_run_and_suggestion_workspaces_must_match(actor: Membership) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    foreign_actor = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="o@example.test")
    )
    foreign_problem: Problem = make_problem(actor=foreign_actor)
    run = latest(report)
    with pytest.raises(ValueError):
        MatchSuggestion.objects.create(
            workspace_id=actor.workspace_id,
            run=run,
            problem=foreign_problem,
            rank=1,
            score=1.0,
            features={},
            evidence=[],
        )
    with pytest.raises(ValueError):
        MatchRun.objects.create(
            workspace_id=foreign_actor.workspace_id,
            report=report,
            report_version=1,
            contract_version="1",
            algorithm_version="lexical-1",
            config_version="lexical-1.0",
        )
