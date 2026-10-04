"""Workspace isolation over HTTP, swept from the URL config on real PostgreSQL.

Every route under `api/workspaces/<workspace_id>/` must appear in ROUTES. Adding a route without
listing it fails `test_every_workspace_route_is_listed`, so a new record-ID route cannot ship
untested. Provider calls are never made: each request is refused before it reaches one.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from builders import (
    make_connection,
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.apps import apps
from django.test import Client
from django.urls import get_resolver
from django.utils import timezone

from accounts.models import Membership, User
from accounts.permissions import IsWorkspaceMember
from accounts.services import create_invitation
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import FollowUp, Problem, Report, ReportNotificationOperation
from feedback.problems import confirm_fix
from feedback.reports import link_report
from matching import runs
from matching.models import MatchRun, MatchSuggestion
from operations.models import ExternalOperation

pytestmark = pytest.mark.django_db

PREFIX = "api/workspaces/<uuid:workspace_id>/"
APPS = ("accounts", "connections", "feedback", "operations", "matching")


@dataclass
class Side:
    """One workspace with an owner, a member, and one of each record the API can address."""

    owner: Membership
    member: Membership
    ids: dict[str, str]
    secrets: list[str]

    @property
    def workspace_id(self) -> str:
        return str(self.owner.workspace_id)


def build_side() -> Side:
    tag = uuid4().hex[:10]
    workspace = make_workspace(name=f"Workspace {tag}", slug=f"ws-{tag}")
    owner = make_membership(
        workspace=workspace, role="owner", user=make_user(email=f"owner-{tag}@example.test")
    )
    member = make_membership(
        workspace=workspace, user=make_user(email=f"member-{tag}@example.test")
    )
    connection = make_connection(workspace=workspace)
    problem = make_problem(actor=owner, title=f"Problem {tag}", summary=f"Summary {tag}")
    report = make_report(actor=owner, title=f"Report {tag}", description=f"Details {tag}")
    link_report(actor=owner, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    confirm_fix(
        actor=owner,
        problem_id=problem.pk,
        expected_version=1,
        fix_note=f"Fix {tag}",
        fix_version="1.0",
    )
    report = Report.objects.select_related("problem").get(pk=report.pk)
    notification = make_notification(report=report)
    operation = ExternalOperation.objects.create(
        kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
        workspace=workspace,
        connection=connection,
        problem=problem,
        requester=owner,
        action_key=uuid4(),
        state=ExternalOperation.State.UNCERTAIN,
        title=f"Issue {tag}",
        body="body",
        destination="acme/widgets",
        problem_version=problem.version,
        binding_revision=connection.binding_revision,
    )
    invitation, _ = create_invitation(
        actor=owner, email=f"invitee-{tag}@example.test", role="member"
    )
    run = MatchRun.objects.filter(report=report).first() or MatchRun.objects.create(
        workspace=workspace,
        report=report,
        report_version=report.version,
        state=MatchRun.State.RANKED,
        contract_version="1",
        algorithm_version="1",
        config_version="1",
    )
    suggestion = MatchSuggestion.objects.create(
        workspace=workspace, run=run, problem=problem, rank=1, score=0.5, features={}, evidence=[]
    )
    follow_up = FollowUp.objects.get(report=report)
    return Side(
        owner=owner,
        member=member,
        ids={
            "report_id": str(report.pk),
            "problem_id": str(problem.pk),
            "follow_up_id": str(follow_up.pk),
            "operation_id": str(operation.pk),
            "membership_id": str(member.pk),
            "invitation_id": str(invitation.pk),
            "suggestion_id": str(suggestion.pk),
            "notification_id": str(notification.pk),
        },
        secrets=[tag, str(operation.pk)],
    )


@pytest.fixture(autouse=True)
def suggestions_on(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Enabled so the matching routes are refused for isolation, not because the flag is off.
    settings.RESCRIBO_MATCH_SUGGESTIONS_ENABLED = True
    monkeypatch.setattr(runs, "dispatch_task", lambda name, ref: None)


@pytest.fixture
def a() -> Side:
    return build_side()


@pytest.fixture
def b() -> Side:
    return build_side()


def sign_in(client: Client, membership: Membership) -> Client:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()
    return client


def snapshot() -> dict[str, list[dict[str, Any]]]:
    """Every row of every product table, to prove a refused request changed nothing."""
    return {
        model._meta.label: list(model.objects.order_by("pk").values())
        for app in APPS
        for model in apps.get_app_config(app).get_models()
        if model is not User
    }


# Method and body per route. A body is valid for the serializer so that a refusal comes from
# workspace scoping, not from validation.
Body = Callable[[dict[str, str]], dict[str, Any] | None]
VERSION = {"expected_version": 1}
NOTIFICATION = lambda ids: {"notification_id": ids["notification_id"], "draft_version": 1}  # noqa: E731
ROUTES: dict[str, list[tuple[str, Body]]] = {
    "connections/": [("get", lambda ids: None)],
    "connections/<str:provider>/setup/": [
        ("post", lambda ids: {"consent": True, "repository": "acme/widgets"})
    ],
    "connections/<str:provider>/callback/": [("get", lambda ids: None)],
    "connections/<str:provider>/disconnect/": [
        ("post", lambda ids: {"version": 1, "confirmation": "DISCONNECT"})
    ],
    "connections/<str:provider>/refresh/": [("post", lambda ids: {"version": 1})],
    "channels/": [
        ("post", lambda ids: {"version": 1, "channel_id": "C0123", "consent": True}),
    ],
    "delete/": [("post", lambda ids: {"confirmation": "nope"})],
    "slack/identity/": [("get", lambda ids: None)],
    "slack/identity/unlink/": [("post", lambda ids: {})],
    "slack/link-code/": [("post", lambda ids: {})],
    "reports/<uuid:report_id>/confirm-fix-applies/": [
        ("post", lambda ids: {**VERSION, "expected_resolution_revision": 1})
    ],
    "reports/<uuid:report_id>/delete/": [
        ("post", lambda ids: {"version": 1, "confirmation": "DELETE"})
    ],
    "reports/<uuid:report_id>/permalink/retry/": [("post", lambda ids: {})],
    "invitations/": [
        ("get", lambda ids: None),
        ("post", lambda ids: {"email": "new@example.test", "role": "member"}),
    ],
    "invitations/<uuid:invitation_id>/revoke/": [("post", lambda ids: {})],
    "memberships/": [("get", lambda ids: None)],
    "memberships/<uuid:membership_id>/revoke/": [("post", lambda ids: {})],
    "memberships/<uuid:membership_id>/role/": [("post", lambda ids: {"role": "owner"})],
    "memberships/<uuid:membership_id>/password-reset/": [("post", lambda ids: {})],
    "members/": [("get", lambda ids: None)],
    "reports/": [
        ("get", lambda ids: None),
        ("post", lambda ids: {"submission_key": str(uuid4()), "title": "New report"}),
    ],
    "reports/<uuid:report_id>/": [("get", lambda ids: None)],
    "reports/<uuid:report_id>/link/": [
        ("post", lambda ids: {**VERSION, "problem_id": str(uuid4())})
    ],
    "reports/<uuid:report_id>/create-problem/": [
        ("post", lambda ids: {**VERSION, "title": "New problem"})
    ],
    "reports/<uuid:report_id>/unlink/": [("post", lambda ids: VERSION)],
    "reports/<uuid:report_id>/dismiss/": [("post", lambda ids: VERSION)],
    "reports/<uuid:report_id>/restore/": [("post", lambda ids: VERSION)],
    "reports/<uuid:report_id>/assign/": [("post", lambda ids: {**VERSION, "assignee_id": None})],
    "follow-ups/": [("get", lambda ids: None)],
    "follow-ups/<uuid:follow_up_id>/": [("get", lambda ids: None)],
    "follow-ups/<uuid:follow_up_id>/notification/": [("post", lambda ids: {})],
    "follow-ups/<uuid:follow_up_id>/notification/edit/": [
        ("post", lambda ids: {**NOTIFICATION(ids), "message": "Hello"})
    ],
    "follow-ups/<uuid:follow_up_id>/notification/approve/": [("post", NOTIFICATION)],
    "follow-ups/<uuid:follow_up_id>/notification/mark-delivered/": [("post", NOTIFICATION)],
    "follow-ups/<uuid:follow_up_id>/notification/send-again/": [
        ("post", lambda ids: {**NOTIFICATION(ids), "checked_slack": True})
    ],
    "follow-ups/<uuid:follow_up_id>/notification/cancel/": [("post", NOTIFICATION)],
    "follow-ups/<uuid:follow_up_id>/outcome/": [
        ("post", lambda ids: {**VERSION, "state": "contacted"})
    ],
    "follow-ups/<uuid:follow_up_id>/outcome/correct/": [
        (
            "post",
            lambda ids: {**VERSION, "state": "still_affected", "note": "n", "reason": "r"},
        )
    ],
    "follow-ups/<uuid:follow_up_id>/recipient/": [
        ("post", lambda ids: {"new_recipient_id": str(uuid4())})
    ],
    "problems/": [("get", lambda ids: None)],
    "problems/<uuid:problem_id>/": [("get", lambda ids: None)],
    "problems/<uuid:problem_id>/confirm-fix/": [
        ("post", lambda ids: {**VERSION, "fix_note": "Fixed", "fix_version": "2.0"})
    ],
    "problems/<uuid:problem_id>/reports/": [("get", lambda ids: None)],
    "problems/<uuid:problem_id>/activity/": [("get", lambda ids: None)],
    "problems/<uuid:problem_id>/edit/": [("post", lambda ids: {**VERSION, "title": "Renamed"})],
    "problems/<uuid:problem_id>/assign-owner/": [
        ("post", lambda ids: {**VERSION, "owner_id": None})
    ],
    "problems/<uuid:problem_id>/issue/link/": [
        (
            "post",
            lambda ids: {**VERSION, "reference": "https://github.com/acme/widgets/issues/1"},
        )
    ],
    "problems/<uuid:problem_id>/issue/preview/": [
        ("get", lambda ids: None),
        ("post", lambda ids: {**VERSION}),
    ],
    "problems/<uuid:problem_id>/issue/approve/": [
        ("post", lambda ids: {"draft_id": str(uuid4()), "draft_version": 1, "approved": True})
    ],
    "problems/<uuid:problem_id>/issue/operations/<uuid:operation_id>/": [("get", lambda ids: None)],
    "problems/<uuid:problem_id>/issue/operations/<uuid:operation_id>/abandon/": [
        ("post", lambda ids: {"reason": "Checked GitHub"})
    ],
    "problems/<uuid:problem_id>/issue/operations/<uuid:operation_id>/reconcile/": [
        ("post", lambda ids: {})
    ],
    "problems/<uuid:problem_id>/issue/refresh/": [("post", lambda ids: {"issue_id": str(uuid4())})],
    "reports/<uuid:report_id>/match/": [("get", lambda ids: None)],
    "reports/<uuid:report_id>/match/retry/": [("post", lambda ids: {})],
    "match-suggestions/<uuid:suggestion_id>/accept/": [("post", lambda ids: VERSION)],
    "match-suggestions/<uuid:suggestion_id>/reject/": [("post", lambda ids: {})],
}


def workspace_routes() -> dict[str, Any]:
    """Route template (without the workspace prefix) to its view class, from the URL config."""
    found: dict[str, Any] = {}

    def walk(patterns: Any, prefix: str = "") -> None:
        for entry in patterns:
            if hasattr(entry, "url_patterns"):
                walk(entry.url_patterns, prefix + str(entry.pattern))
            elif (route := prefix + str(entry.pattern)).startswith(PREFIX):
                found[route.removeprefix(PREFIX)] = entry.callback.cls

    walk(get_resolver().url_patterns)
    return found


LISTS = {
    "connections/",
    "invitations/",
    "memberships/",
    "members/",
    "reports/",
    "follow-ups/",
    "problems/",
}


def record_routes() -> list[str]:
    return [route for route in ROUTES if re.search(r"<uuid:(?!workspace_id)", route)]


def path(workspace_id: str, template: str, ids: dict[str, str]) -> str:
    resolved = re.sub(r"<uuid:(\w+)>", lambda m: ids[m.group(1)], template)
    return f"/api/workspaces/{workspace_id}/{resolved.replace('<str:provider>', 'github')}"


def call(client: Client, method: str, url: str, body: dict[str, Any] | None) -> Any:
    if method == "get":
        return client.get(url)
    return client.post(url, body or {}, content_type="application/json")


def calls() -> list[Any]:
    return [
        pytest.param(route, method, body, id=f"{method} {route}")
        for route, entries in ROUTES.items()
        for method, body in entries
    ]


def record_calls() -> list[Any]:
    return [p for p in calls() if p.values[0] in record_routes()]


def assert_hidden(response: Any, side: Side) -> None:
    assert response.status_code == 404, response.content[:200]
    text = response.content.decode()
    for secret in [*side.ids.values(), *side.secrets]:
        assert secret not in text


def random_ids(ids: dict[str, str]) -> dict[str, str]:
    return {key: str(uuid4()) for key in ids}


def test_every_workspace_route_is_listed() -> None:
    assert set(workspace_routes()) == set(ROUTES)


def test_every_workspace_route_requires_active_membership() -> None:
    for route, view in workspace_routes().items():
        assert IsWorkspaceMember in view.permission_classes, route


@pytest.mark.parametrize(("route", "method", "body"), record_calls())
def test_foreign_record_id_in_own_workspace_is_indistinguishable_from_unknown(
    route: str, method: str, body: Body, a: Side, b: Side
) -> None:
    """B's owner on B's URL names A's record ID: same answer as for an ID that does not exist."""
    client = sign_in(Client(), b.owner)
    before = snapshot()
    foreign = call(client, method, path(b.workspace_id, route, a.ids), body(a.ids))
    unknown = call(client, method, path(b.workspace_id, route, random_ids(a.ids)), body(a.ids))
    assert_hidden(foreign, a)
    assert (foreign.status_code, foreign.json()) == (unknown.status_code, unknown.json())
    assert snapshot() == before


@pytest.mark.parametrize(("route", "method", "body"), calls())
def test_member_of_another_workspace_is_refused_on_foreign_url(
    route: str, method: str, body: Body, a: Side, b: Side
) -> None:
    client = sign_in(Client(), b.owner)
    before = snapshot()
    response = call(client, method, path(a.workspace_id, route, a.ids), body(a.ids))
    assert_hidden(response, a)
    assert snapshot() == before


@pytest.mark.parametrize(("route", "method", "body"), calls())
def test_deactivated_member_is_refused_with_a_live_session(
    route: str, method: str, body: Body, a: Side
) -> None:
    """The session predates the revocation, so only the per-request membership check stops it."""
    client = sign_in(Client(), a.owner)
    Membership.objects.filter(pk=a.owner.pk).update(is_active=False, revoked_at=timezone.now())
    before = snapshot()
    response = call(client, method, path(a.workspace_id, route, a.ids), body(a.ids))
    assert_hidden(response, a)
    assert snapshot() == before


# Foreign IDs in the body: B's own record, A's member or problem as the target.

FOREIGN_BODY_CALLS: list[tuple[str, str, Callable[[Side, Side], dict[str, Any]]]] = [
    (
        "reports/<uuid:report_id>/link/",
        "problem_id",
        lambda a, b: {"problem_id": a.ids["problem_id"]},
    ),
    (
        "reports/<uuid:report_id>/assign/",
        "assignee_id",
        lambda a, b: {"assignee_id": str(a.member.pk)},
    ),
    (
        "reports/<uuid:report_id>/create-problem/",
        "owner_id",
        lambda a, b: {"title": "New", "owner_id": str(a.member.pk)},
    ),
    (
        "problems/<uuid:problem_id>/assign-owner/",
        "owner_id",
        lambda a, b: {"owner_id": str(a.member.pk)},
    ),
    (
        "follow-ups/<uuid:follow_up_id>/recipient/",
        "new_recipient_id",
        lambda a, b: {"new_recipient_id": str(a.member.pk)},
    ),
]


@pytest.mark.parametrize(
    ("route", "field", "body"),
    [pytest.param(*row, id=row[0]) for row in FOREIGN_BODY_CALLS],
)
def test_foreign_id_in_request_body_is_rejected_like_an_unknown_one(
    route: str, field: str, body: Callable[[Side, Side], dict[str, Any]], a: Side, b: Side
) -> None:
    client = sign_in(Client(), b.owner)
    own = {**b.ids, "report_id": str(make_report(actor=b.owner).pk)}
    version = Problem.objects.get(pk=own["problem_id"]).version
    expected = {"expected_version": version if "problem_id" in route else 1}
    url = path(b.workspace_id, route, own)
    before = snapshot()
    foreign = client.post(url, {**expected, **body(a, b)}, content_type="application/json")
    unknown = client.post(
        url, {**expected, **body(a, b), field: str(uuid4())}, content_type="application/json"
    )
    assert foreign.status_code == unknown.status_code, foreign.content[:200]
    assert foreign.status_code in (400, 404)
    assert foreign.json() == unknown.json()
    assert snapshot() == before


@pytest.mark.parametrize(
    "route", [r for r, entries in ROUTES.items() if r in LISTS and entries[0][0] == "get"]
)
def test_list_routes_show_only_the_callers_workspace(route: str, a: Side, b: Side) -> None:
    client = sign_in(Client(), b.owner)
    response = client.get(path(b.workspace_id, route, {}))
    assert response.status_code == 200
    text = response.content.decode()
    for value in [*a.ids.values(), *a.secrets, a.owner.user.email, a.member.user.email]:
        assert value not in text
    if route == "connections/":
        assert len(response.json()) == 1


def test_search_and_counts_ignore_other_workspaces(a: Side, b: Side) -> None:
    client = sign_in(Client(), b.owner)
    a_tag = a.secrets[0]
    for template, query in (
        ("reports/", {"q": a_tag}),
        ("reports/", {"customer": a_tag}),
        ("problems/", {"q": a_tag}),
    ):
        body = client.get(path(b.workspace_id, template, {}), query).json()
        assert body["count"] == 0 and body["results"] == []
    assert client.get(path(b.workspace_id, "follow-ups/", {})).json()["count"] == 1
    assert Problem.objects.filter(workspace_id=a.workspace_id).count() == 1
    assert ReportNotificationOperation.objects.filter(workspace_id=a.workspace_id).count() == 1
