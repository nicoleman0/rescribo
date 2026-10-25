import pytest
from builders import make_membership, make_problem, make_user, make_workspace
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import Activity, Problem
from feedback.problems import confirm_fix

pytestmark = pytest.mark.django_db


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def state_url(actor: Membership, problem: Problem) -> str:
    return f"/api/workspaces/{actor.workspace_id}/problems/{problem.pk}/state/"


def test_problem_state_lifecycle_and_activity(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    url = state_url(actor, problem)

    for action, state in (("start", "in_progress"), ("stop", "open")):
        response = client.post(
            url,
            {"expected_version": problem.version, "action": action},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["state"] == state
        problem.refresh_from_db()

    response = client.post(
        url,
        {"expected_version": problem.version, "action": "decline", "reason": "No longer needed"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["state"] == "not_planned"
    assert response.json()["not_planned_reason"] == "No longer needed"
    problem.refresh_from_db()
    response = client.post(
        url,
        {"expected_version": problem.version, "action": "reopen"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["state"] == "open"
    assert response.json()["not_planned_reason"] == ""
    assert (
        Activity.objects.filter(
            record_id=problem.pk,
            actor_membership=actor,
            action=Activity.Action.PROBLEM_STATE_CHANGED,
        ).count()
        == 4
    )


@pytest.mark.parametrize(
    ("action", "reason"),
    [("decline", "  "), ("not-an-action", "")],
)
def test_problem_state_rejects_invalid_input(client: Client, action: str, reason: str) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    response = client.post(
        state_url(actor, problem),
        {"expected_version": 1, "action": action, "reason": reason},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["reason"] == (
        "reason_required" if action == "decline" else "invalid_request"
    )
    if action == "decline":
        assert "reason" in response.json()["field_errors"]
    problem.refresh_from_db()
    assert problem.state == "open"


def test_problem_state_conflicts_return_current_without_mutation(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    problem = confirm_fix(
        actor=actor,
        problem_id=problem.pk,
        expected_version=1,
        fix_note="Fixed",
        fix_version="1.0",
    )
    sign_in(client, actor)
    response = client.post(
        state_url(actor, problem),
        {"expected_version": problem.version, "action": "decline", "reason": "No longer needed"},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["reason"] == "invalid_transition"
    assert response.json()["current"]["state"] == "fix_available"
    problem.refresh_from_db()
    assert problem.state == "fix_available"

    response = client.post(
        state_url(actor, problem),
        {"expected_version": 1, "action": "start"},
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["reason"] == "version_conflict"
    problem.refresh_from_db()
    assert problem.state == "fix_available"


def test_problem_state_does_not_expose_another_workspaces_problem(client: Client) -> None:
    actor = make_membership()
    other = make_membership(
        workspace=make_workspace(slug="other"), user=make_user(email="other@example.test")
    )
    problem = make_problem(actor=other)
    sign_in(client, actor)
    response = client.post(
        state_url(actor, problem),
        {"expected_version": 1, "action": "start"},
        content_type="application/json",
    )
    assert response.status_code == 404
    problem.refresh_from_db()
    assert problem.state == "open"


def test_problem_state_is_allowed_in_demo_workspace(client: Client) -> None:
    actor = make_membership(workspace=make_workspace(is_demo=True))
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    response = client.post(
        state_url(actor, problem),
        {"expected_version": 1, "action": "start"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["state"] == "in_progress"


def test_problem_state_requires_csrf() -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    client = Client(enforce_csrf_checks=True)
    sign_in(client, actor)
    response = client.post(
        state_url(actor, problem),
        {"expected_version": 1, "action": "start"},
        content_type="application/json",
    )
    assert response.status_code == 403
    problem.refresh_from_db()
    assert problem.state == "open"
