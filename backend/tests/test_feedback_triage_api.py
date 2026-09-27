"""HTTP contracts for report triage and the problems screens."""

from typing import Any

import pytest
from builders import (
    make_membership,
    make_notification,
    make_problem,
    make_report,
    make_user,
    make_workspace,
)
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import Activity, Problem, Report, ReportNotificationOperation
from feedback.problems import assign_problem_owner
from feedback.reports import assign_report, link_report, unlink_report
from feedback.submissions import SourceSnapshot

pytestmark = pytest.mark.django_db


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def api(membership: Membership, path: str) -> str:
    return f"/api/workspaces/{membership.workspace_id}/{path}"


def post(client: Client, url: str, body: dict[str, Any]) -> Any:
    return client.post(url, body, content_type="application/json")


def slack_source() -> SourceSnapshot:
    return SourceSnapshot(
        "slack", "T1", "C1", "171.1", "https://example.test/msg", "U1", "Author", "snapshot"
    )


@pytest.fixture
def actor(client: Client) -> Membership:
    membership = make_membership(role=Membership.Role.OWNER)
    sign_in(client, membership)
    return membership


def teammate(actor: Membership, email: str = "t@example.test", name: str = "Ada") -> Membership:
    return make_membership(workspace=actor.workspace, user=make_user(email=email, full_name=name))


def foreign_member() -> Membership:
    return make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )


def test_two_reports_grouped_into_one_problem(client: Client, actor: Membership) -> None:
    owner = teammate(actor)
    first = make_report(actor=actor, title="First", source=slack_source())
    second = make_report(actor=actor, title="Second")
    created = post(
        client,
        api(actor, f"reports/{first.pk}/create-problem/"),
        {
            "expected_version": 1,
            "title": "Exports fail",
            "summary": "",
            "owner_id": str(owner.pk),
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["triage_state"] == "linked" and body["version"] == 2
    assert body["provenance"]["kind"] == "slack"
    problem_id = body["problem"]["id"]
    linked = post(
        client,
        api(actor, f"reports/{second.pk}/link/"),
        {"expected_version": 1, "problem_id": problem_id},
    )
    assert linked.status_code == 200 and linked.json()["problem"]["id"] == problem_id
    detail = client.get(api(actor, f"problems/{problem_id}/")).json()
    assert detail["report_count"] == 2
    assert detail["owner"] == {"id": str(owner.pk), "display_name": "Ada"}
    assert detail["state"] == "open" and detail["version"] == 1
    reports = client.get(api(actor, f"problems/{problem_id}/reports/")).json()
    assert [row["title"] for row in reports["results"]] == ["First", "Second"]
    assert reports["results"][0]["provenance"]["snapshot_text"] == "snapshot"


def test_ungroup_dismiss_restore_and_assign(client: Client, actor: Membership) -> None:
    member = teammate(actor)
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
    url = api(actor, f"reports/{report.pk}/")
    ungrouped = post(client, f"{url}unlink/", {"expected_version": 2})
    assert ungrouped.status_code == 200
    assert ungrouped.json()["triage_state"] == "new" and ungrouped.json()["problem"] is None
    assert post(client, f"{url}dismiss/", {"expected_version": 3}).json()["triage_state"] == (
        "dismissed"
    )
    assert post(client, f"{url}restore/", {"expected_version": 4}).json()["triage_state"] == "new"
    assigned = post(client, f"{url}assign/", {"expected_version": 5, "assignee_id": str(member.pk)})
    assert assigned.json()["assignee"] == {"id": str(member.pk), "display_name": "Ada"}
    cleared = post(client, f"{url}assign/", {"expected_version": 6, "assignee_id": None})
    assert cleared.json()["assignee"] is None and cleared.json()["version"] == 7


def test_reassignment_over_http_cancels_pending_and_keeps_sent(
    client: Client, actor: Membership
) -> None:
    member = teammate(actor)
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    report = link_report(
        actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk
    )
    pending = make_notification(report=report)
    sent = make_notification(report=report, state="sent")
    response = post(
        client,
        api(actor, f"reports/{report.pk}/assign/"),
        {"expected_version": 2, "assignee_id": str(member.pk)},
    )
    assert response.status_code == 200
    pending.refresh_from_db()
    assert pending.state == "cancelled"
    assert ReportNotificationOperation.objects.get(pk=sent.pk).state == "sent"


@pytest.mark.parametrize(
    ("path", "body", "fields"),
    [
        ("link/", {"problem_id": "not-a-uuid", "expected_version": 1}, {"problem_id"}),
        ("link/", {"expected_version": 1}, {"problem_id"}),
        ("dismiss/", {}, {"expected_version"}),
        ("dismiss/", {"expected_version": 0}, {"expected_version"}),
        ("dismiss/", {"expected_version": "one"}, {"expected_version"}),
        ("assign/", {"expected_version": 1}, {"assignee_id"}),
        ("create-problem/", {"expected_version": 1, "title": "  "}, {"title"}),
        ("create-problem/", {"expected_version": 1, "title": "x" * 201}, {"title"}),
    ],
)
def test_report_actions_validate_input(
    client: Client, actor: Membership, path: str, body: dict[str, Any], fields: set[str]
) -> None:
    report = make_report(actor=actor)
    response = post(client, api(actor, f"reports/{report.pk}/{path}"), body)
    assert response.status_code == 400
    assert response.json()["reason"] == "invalid_request"
    assert set(response.json()["field_errors"]) == fields
    assert Report.objects.get(pk=report.pk).version == 1
    assert not Problem.objects.exists()


def test_invalid_references_are_field_errors(client: Client, actor: Membership) -> None:
    foreign = foreign_member()
    foreign_problem = make_problem(actor=foreign)
    report = make_report(actor=actor)
    cases = [
        ("link/", {"problem_id": str(foreign_problem.pk)}, "problem_id"),
        ("assign/", {"assignee_id": str(foreign.pk)}, "assignee_id"),
        ("create-problem/", {"title": "New", "owner_id": str(foreign.pk)}, "owner_id"),
    ]
    for path, body, field in cases:
        response = post(
            client, api(actor, f"reports/{report.pk}/{path}"), {"expected_version": 1, **body}
        )
        assert response.status_code == 400
        assert response.json()["reason"] == "invalid_reference"
        assert response.json()["field_errors"] == {field: ["invalid_reference"]}
    assert Report.objects.get(pk=report.pk).version == 1
    assert Problem.objects.filter(workspace=actor.workspace).count() == 0


def test_stale_version_returns_current_report(client: Client, actor: Membership) -> None:
    member = teammate(actor)
    report = make_report(actor=actor, title="Current title")
    assign_report(actor=actor, report_id=report.pk, expected_version=1, assignee_id=member.pk)
    activity = Activity.objects.count()
    response = post(
        client,
        api(actor, f"reports/{report.pk}/create-problem/"),
        {"expected_version": 1, "title": "Stale decision"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["reason"] == "version_conflict"
    assert body["current"]["version"] == 2 and body["current"]["title"] == "Current title"
    assert body["current"]["assignee"] == {"id": str(member.pk), "display_name": "Ada"}
    assert "email" not in str(body)
    assert not Problem.objects.exists() and Activity.objects.count() == activity


@pytest.mark.parametrize(
    ("setup", "path", "body", "reason"),
    [
        ("linked", "dismiss/", {}, "invalid_transition"),
        ("new", "unlink/", {}, "invalid_transition"),
        ("linked", "link/", {"problem_id": "SAME"}, "already_linked"),
        ("new", "assign/", {"assignee_id": None}, "no_changes"),
    ],
)
def test_conflicting_actions_return_409_with_current(
    client: Client, actor: Membership, setup: str, path: str, body: dict[str, Any], reason: str
) -> None:
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    version = 1
    if setup == "linked":
        link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
        version = 2
    if body.get("problem_id") == "SAME":
        body = {"problem_id": str(problem.pk)}
    response = post(
        client, api(actor, f"reports/{report.pk}/{path}"), {"expected_version": version, **body}
    )
    assert response.status_code == 409
    assert response.json()["reason"] == reason
    assert response.json()["current"]["version"] == version


def test_report_actions_hide_foreign_reports(client: Client, actor: Membership) -> None:
    foreign = foreign_member()
    foreign_report = make_report(actor=foreign)
    for path in ("dismiss/", "unlink/", "restore/"):
        response = post(
            client, api(actor, f"reports/{foreign_report.pk}/{path}"), {"expected_version": 1}
        )
        assert response.status_code == 404
        assert "current" not in response.json()
    response = post(
        client, api(foreign, f"reports/{foreign_report.pk}/dismiss/"), {"expected_version": 1}
    )
    assert response.status_code == 404
    assert Report.objects.get(pk=foreign_report.pk).triage_state == "new"


def test_report_actions_require_session_csrf_and_active_membership() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    member = teammate(owner)
    report = make_report(actor=owner)
    url = api(owner, f"reports/{report.pk}/dismiss/")
    anonymous = Client()
    assert post(anonymous, url, {"expected_version": 1}).status_code == 401
    strict = Client(enforce_csrf_checks=True)
    sign_in(strict, member)
    response = post(strict, url, {"expected_version": 1})
    assert response.status_code == 403 and response.json()["reason"] == "csrf_failed"
    relaxed = Client()
    sign_in(relaxed, member)
    Membership.objects.filter(pk=member.pk).update(is_active=False, revoked_at=timezone.now())
    assert post(relaxed, url, {"expected_version": 1}).status_code == 404
    assert Report.objects.get(pk=report.pk).version == 1


def test_problem_list_searches_counts_and_hides_foreign(client: Client, actor: Membership) -> None:
    owner = teammate(actor)
    exports = make_problem(actor=actor, title="Exports fail", summary="CSV " + "x" * 300)
    make_problem(actor=actor, title="Login slow", summary="export button hidden")
    make_problem(actor=actor, title="Billing")
    assign_problem_owner(actor=actor, problem_id=exports.pk, expected_version=1, owner_id=owner.pk)
    Problem.objects.filter(pk=exports.pk).update(needs_review=True)
    for index in range(2):
        report = make_report(actor=actor, title=f"R{index}")
        link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=exports.pk)
    foreign = foreign_member()
    make_problem(actor=foreign, title="Foreign export")
    listing = client.get(api(actor, "problems/"), {"q": "EXPORT"}).json()
    assert listing["count"] == 2
    rows = {row["title"]: row for row in listing["results"]}
    assert set(rows) == {"Exports fail", "Login slow"}
    assert rows["Exports fail"]["report_count"] == 2
    assert rows["Exports fail"]["needs_review"] is True
    assert rows["Exports fail"]["owner"] == {"id": str(owner.pk), "display_name": "Ada"}
    assert len(rows["Exports fail"]["summary_excerpt"]) == 160
    assert rows["Login slow"]["report_count"] == 0
    assert client.get(api(actor, "problems/")).json()["count"] == 3
    assert client.get(api(actor, "problems/"), {"q": "x" * 201}).status_code == 400
    assert client.get(api(foreign, "problems/")).status_code == 404


def test_problem_list_paginates(client: Client, actor: Membership) -> None:
    for index in range(26):
        make_problem(actor=actor, title=f"Problem {index:02}")
    first = client.get(api(actor, "problems/")).json()
    assert first["count"] == 26 and len(first["results"]) == 25
    assert first["results"][0]["title"] == "Problem 25"
    second = client.get(api(actor, "problems/"), {"page": 2}).json()
    assert [row["title"] for row in second["results"]] == ["Problem 00"]


def test_unknown_or_foreign_problem_is_404_not_empty(client: Client, actor: Membership) -> None:
    foreign_problem = make_problem(actor=foreign_member())
    for suffix in ("", "reports/", "activity/"):
        response = client.get(api(actor, f"problems/{foreign_problem.pk}/{suffix}"))
        assert response.status_code == 404, suffix
    for suffix, body in (("edit/", {"title": "x"}), ("assign-owner/", {"owner_id": None})):
        response = post(
            client,
            api(actor, f"problems/{foreign_problem.pk}/{suffix}"),
            {"expected_version": 1, **body},
        )
        assert response.status_code == 404
        assert "current" not in response.json()


def test_problem_activity_keeps_removed_reports_and_names_people(
    client: Client, actor: Membership
) -> None:
    member = teammate(actor, email="ada@example.test")
    first = make_problem(actor=actor, title="First")
    second = make_problem(actor=actor, title="Second")
    report = make_report(actor=actor, title="Moved report", customer_label="secret-customer")
    link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=first.pk)
    assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=member.pk)
    link_report(actor=actor, report_id=report.pk, expected_version=3, problem_id=second.pk)
    unlink_report(actor=actor, report_id=report.pk, expected_version=4)
    response = client.get(api(actor, f"problems/{first.pk}/activity/"))
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["action"] for row in rows] == [
        "report.unlinked",
        "report.assigned",
        "report.linked",
        "problem.created",
    ]
    moved = rows[0]
    assert moved["report"] == {"id": str(report.pk), "title": "Moved report"}
    assert moved["to_problem"] == {"id": str(second.pk), "title": "Second"}
    assert moved["actor"] == {"id": str(actor.pk), "display_name": "Test Member"}
    assert rows[1]["to_assignee"] == {"id": str(member.pk), "display_name": "Ada"}
    assert rows[1]["from_assignee"] is None
    text = response.content.decode()
    assert "ada@example.test" not in text and "secret-customer" not in text
    second_rows = client.get(api(actor, f"problems/{second.pk}/activity/")).json()["results"]
    assert second_rows[0]["action"] == "report.unlinked" and second_rows[0]["to_problem"] is None
    assert second_rows[1]["from_problem"] == {"id": str(first.pk), "title": "First"}


def test_problem_edit_and_owner(client: Client, actor: Membership) -> None:
    member = teammate(actor)
    problem = make_problem(actor=actor, title="Old", summary="Old summary")
    url = api(actor, f"problems/{problem.pk}/")
    edited = post(client, f"{url}edit/", {"expected_version": 1, "title": " New ", "summary": ""})
    assert edited.status_code == 200
    assert (edited.json()["title"], edited.json()["summary"], edited.json()["version"]) == (
        "New",
        "",
        2,
    )
    owned = post(client, f"{url}assign-owner/", {"expected_version": 2, "owner_id": str(member.pk)})
    assert owned.json()["owner"] == {"id": str(member.pk), "display_name": "Ada"}
    cleared = post(client, f"{url}assign-owner/", {"expected_version": 3, "owner_id": None})
    assert cleared.json()["owner"] is None
    stale = post(client, f"{url}edit/", {"expected_version": 1, "title": "Lost"})
    assert stale.status_code == 409 and stale.json()["reason"] == "version_conflict"
    assert stale.json()["current"]["title"] == "New" and stale.json()["current"]["version"] == 4
    same = post(client, f"{url}edit/", {"expected_version": 4, "title": "New"})
    assert same.status_code == 409 and same.json()["reason"] == "no_changes"
    empty = post(client, f"{url}edit/", {"expected_version": 4})
    assert empty.status_code == 400 and "title" in empty.json()["field_errors"]
    bad_owner = post(
        client, f"{url}assign-owner/", {"expected_version": 4, "owner_id": str(foreign_member().pk)}
    )
    assert bad_owner.json()["field_errors"] == {"owner_id": ["invalid_reference"]}
    assert Problem.objects.get(pk=problem.pk).version == 4


def test_problem_writes_require_csrf(actor: Membership) -> None:
    problem = make_problem(actor=actor)
    strict = Client(enforce_csrf_checks=True)
    sign_in(strict, actor)
    response = post(
        strict,
        api(actor, f"problems/{problem.pk}/edit/"),
        {"expected_version": 1, "title": "Changed"},
    )
    assert response.status_code == 403
    assert Problem.objects.get(pk=problem.pk).title == problem.title


def query_count(client: Client, url: str) -> int:
    with CaptureQueriesContext(connection) as queries:
        assert client.get(url).status_code == 200
    return len(queries)


def test_problem_reads_do_not_query_per_row(client: Client, actor: Membership) -> None:
    member = teammate(actor)
    problem = make_problem(actor=actor, owner_id=member.pk)
    make_problem(actor=actor, owner_id=actor.pk)

    def add_report() -> None:
        report = make_report(actor=actor)
        link_report(actor=actor, report_id=report.pk, expected_version=1, problem_id=problem.pk)
        assign_report(actor=actor, report_id=report.pk, expected_version=2, assignee_id=member.pk)

    add_report()
    urls = [
        api(actor, "problems/"),
        api(actor, f"problems/{problem.pk}/reports/"),
        api(actor, f"problems/{problem.pk}/activity/"),
    ]
    few = [query_count(client, url) for url in urls]
    for _ in range(4):
        add_report()
    make_problem(actor=actor, owner_id=member.pk)
    assert [query_count(client, url) for url in urls] == few
