"""HTTP contracts for match suggestions: reads, retry, accept, and reject."""

from pathlib import Path
from typing import Any

import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace
from django.test import Client, override_settings

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import Activity, Report
from feedback.reports import dismiss_report
from matching import runs
from matching.models import MatchRun, MatchSuggestion
from matching.runs import execute_run

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runs, "dispatch_task", lambda name, ref: None)


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


@pytest.fixture
def actor(client: Client) -> Membership:
    membership = make_membership()
    sign_in(client, membership)
    return membership


def api(membership: Membership, path: str) -> str:
    return f"/api/workspaces/{membership.workspace_id}/{path}"


def post(client: Client, url: str, body: dict[str, Any] | None = None) -> Any:
    return client.post(url, body or {}, content_type="application/json")


def ranked_report(actor: Membership) -> tuple[Report, MatchSuggestion]:
    make_problem(actor=actor, title="CSV export times out", summary="Large exports fail")
    make_problem(actor=actor, title="Dark mode colours are wrong")
    report = make_report(actor=actor, title="CSV export times out", description="Large exports")
    run = MatchRun.objects.get(report=report)
    execute_run(run.pk)
    suggestion = MatchSuggestion.objects.get(run=run, rank=1)
    return report, suggestion


def test_read_before_and_after_ranking(client: Client, actor: Membership) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    pending = client.get(api(actor, f"reports/{report.pk}/match/")).json()
    assert pending["run"]["state"] == "pending"
    assert pending["run"]["suggestions"] == []

    MatchRun.objects.filter(report=report).delete()
    assert client.get(api(actor, f"reports/{report.pk}/match/")).json() == {"run": None}


def test_ranked_read_shows_evidence_and_rank_not_confidence(
    client: Client, actor: Membership
) -> None:
    report, suggestion = ranked_report(actor)
    body = client.get(api(actor, f"reports/{report.pk}/match/")).json()
    run = body["run"]
    assert run["state"] == "ranked"
    first = run["suggestions"][0]
    assert first["id"] == str(suggestion.pk)
    assert first["rank"] == 1
    assert first["problem"]["title"] == "CSV export times out"
    assert first["evidence"][0] == {
        "record": "problem",
        "id": str(suggestion.problem_id),
        "field": "title",
        "explanation": "Problem title",
    }
    assert "probability" not in str(body) and "confidence" not in str(body)


def test_inbox_marks_failed_matching_unavailable(
    client: Client, actor: Membership, tmp_path: Path
) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    untouched = make_report(actor=actor, title="Another")
    MatchRun.objects.filter(report=untouched).delete()
    with override_settings(RESCRIBO_MATCHER_PATH=str(tmp_path / "absent")):
        execute_run(MatchRun.objects.get(report=report).pk)
    rows = {row["id"]: row for row in client.get(api(actor, "reports/")).json()["results"]}
    assert rows[str(report.pk)]["match_state"] == "failed"
    assert rows[str(untouched.pk)]["match_state"] is None


def test_accept_links_through_the_normal_use_case(client: Client, actor: Membership) -> None:
    report, suggestion = ranked_report(actor)
    response = post(
        client,
        api(actor, f"match-suggestions/{suggestion.pk}/accept/"),
        {"expected_version": report.version},
    )
    assert response.status_code == 200
    assert response.json()["run"]["suggestions"][0]["decision"] == "accepted"
    report.refresh_from_db()
    assert (report.triage_state, report.problem_id) == ("linked", suggestion.problem_id)
    assert Activity.objects.filter(
        record_id=report.pk, action=Activity.Action.REPORT_LINKED, actor_membership=actor
    ).exists()
    suggestion.refresh_from_db()
    assert suggestion.decided_by_id == actor.pk

    again = post(
        client,
        api(actor, f"match-suggestions/{suggestion.pk}/accept/"),
        {"expected_version": report.version},
    )
    assert again.status_code == 409


def test_accept_with_a_stale_report_version_conflicts(client: Client, actor: Membership) -> None:
    report, suggestion = ranked_report(actor)
    response = post(
        client,
        api(actor, f"match-suggestions/{suggestion.pk}/accept/"),
        {"expected_version": report.version + 1},
    )
    assert response.status_code == 409
    assert response.json()["reason"] == "version_conflict"
    assert response.json()["current"]["run"]["suggestions"][0]["decision"] == "pending"
    report.refresh_from_db()
    assert report.triage_state == "new"


def test_accept_on_a_triaged_report_conflicts(client: Client, actor: Membership) -> None:
    report, suggestion = ranked_report(actor)
    dismiss_report(actor=actor, report_id=report.pk, expected_version=report.version)
    response = post(
        client,
        api(actor, f"match-suggestions/{suggestion.pk}/accept/"),
        {"expected_version": report.version + 1},
    )
    assert (response.status_code, response.json()["reason"]) == (409, "suggestion_not_current")


def test_suggestions_from_a_superseded_run_cannot_be_decided(
    client: Client, actor: Membership
) -> None:
    report, suggestion = ranked_report(actor)
    from feedback.reports import ReportChanges, update_report

    update_report(
        actor=actor,
        report_id=report.pk,
        expected_version=report.version,
        changes=ReportChanges(title="CSV export is slow"),
    )
    response = post(client, api(actor, f"match-suggestions/{suggestion.pk}/reject/"))
    assert (response.status_code, response.json()["reason"]) == (409, "suggestion_not_current")


def test_reject_records_the_decision_only(client: Client, actor: Membership) -> None:
    report, suggestion = ranked_report(actor)
    response = post(client, api(actor, f"match-suggestions/{suggestion.pk}/reject/"))
    assert response.status_code == 200
    suggestion.refresh_from_db()
    assert suggestion.decision == "rejected"
    report.refresh_from_db()
    assert (report.triage_state, report.version) == ("new", 1)


def test_retry_queues_a_fresh_run_only_after_failure(
    client: Client, actor: Membership, tmp_path: Path
) -> None:
    report = make_report(actor=actor, title="CSV export times out")
    url = api(actor, f"reports/{report.pk}/match/retry/")
    assert post(client, url).json()["reason"] == "match_not_retryable"

    with override_settings(RESCRIBO_MATCHER_PATH=str(tmp_path / "absent")):
        execute_run(MatchRun.objects.get(report=report).pk)
    response = post(client, url)
    assert response.status_code == 202
    assert response.json()["run"]["state"] == "pending"
    assert MatchRun.objects.filter(report=report).count() == 2


def test_other_workspaces_get_404(client: Client, actor: Membership) -> None:
    report, suggestion = ranked_report(actor)
    outsider = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="o@example.test")
    )
    sign_in(client, outsider)
    for response in (
        client.get(api(outsider, f"reports/{report.pk}/match/")),
        post(client, api(outsider, f"reports/{report.pk}/match/retry/")),
        post(
            client,
            api(outsider, f"match-suggestions/{suggestion.pk}/accept/"),
            {"expected_version": 1},
        ),
        post(client, api(outsider, f"match-suggestions/{suggestion.pk}/reject/")),
    ):
        assert response.status_code == 404
    suggestion.refresh_from_db()
    assert suggestion.decision == "pending"


def test_requires_sign_in() -> None:
    report = make_report(title="CSV export times out")
    response = Client().get(f"/api/workspaces/{report.workspace_id}/reports/{report.pk}/match/")
    assert response.status_code == 401
