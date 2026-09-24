from datetime import timedelta
from typing import Any

import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import Activity, Report
from feedback.reports import assign_report, dismiss_report, link_report
from feedback.submissions import SourceSnapshot

pytestmark = pytest.mark.django_db


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def reports_url(membership: Membership) -> str:
    return f"/api/workspaces/{membership.workspace_id}/reports/"


def slack_source(message: str = "171234.1") -> SourceSnapshot:
    return SourceSnapshot(
        "slack", "T1", "C1", message, "https://example.test/msg", "U1", "Slack Author", "snapshot"
    )


def titles(response: Any) -> list[str]:
    return [row["title"] for row in response.json()["results"]]


def test_manual_capture_uses_the_report_workflow(client: Client) -> None:
    actor = make_membership()
    sign_in(client, actor)
    response = client.post(
        reports_url(actor),
        {
            "title": "  CSV export fails  ",
            "description": "Export stops at 50%.",
            "customer_label": "Acme",
            "customer_contact_reference": "ops@acme.test",
            "affected_version": "2.3.1",
        },
        content_type="application/json",
    )
    assert response.status_code == 201
    body = response.json()
    report = Report.objects.get(pk=body["id"])
    assert report.title == body["title"] == "CSV export fails"
    assert report.source.kind == body["provenance"]["kind"] == "manual"
    assert body["submitted_by"]["id"] == str(actor.pk)
    assert body["triage_state"] == "new" and body["assignee"] is None and body["problem"] is None
    assert body["version"] == 1
    activity = Activity.objects.get(record_id=report.pk)
    assert activity.action == Activity.Action.REPORT_CREATED and activity.metadata == {}


def test_manual_capture_rejects_blank_title_and_oversized_fields(client: Client) -> None:
    actor = make_membership()
    sign_in(client, actor)
    response = client.post(
        reports_url(actor),
        {"title": "   ", "affected_version": "v" * 101},
        content_type="application/json",
    )
    assert response.status_code == 400
    body = response.json()
    assert body["reason"] == "invalid_request"
    assert set(body["field_errors"]) == {"title", "affected_version"}
    assert not Report.objects.exists()


def test_manual_capture_requires_csrf_token() -> None:
    actor = make_membership()
    client = Client(enforce_csrf_checks=True)
    sign_in(client, actor)
    response = client.post(reports_url(actor), {"title": "A"}, content_type="application/json")
    assert response.status_code == 403
    assert not Report.objects.exists()


def test_inbox_requires_sign_in(client: Client) -> None:
    workspace = make_workspace()
    response = client.get(f"/api/workspaces/{workspace.pk}/reports/")
    assert response.status_code == 401


def test_inbox_lists_newest_first_with_pagination(client: Client) -> None:
    actor = make_membership()
    sign_in(client, actor)
    reports = [make_report(actor=actor, title=f"Report {index:02}") for index in range(27)]
    for index, report in enumerate(reports):
        Report.objects.filter(pk=report.pk).update(
            created_at=report.created_at + timedelta(minutes=index)
        )
    first = client.get(reports_url(actor))
    assert first.status_code == 200
    body = first.json()
    assert body["count"] == 27 and len(body["results"]) == 25
    assert body["results"][0]["title"] == "Report 26"
    assert body["results"][0]["source_kind"] == "manual"
    assert body["next"] is not None and body["previous"] is None
    second = client.get(reports_url(actor), {"page": 2})
    assert titles(second) == ["Report 01", "Report 00"]
    assert client.get(reports_url(actor), {"page": 3}).status_code == 404


def test_inbox_searches_text_and_customer_separately(client: Client) -> None:
    actor = make_membership()
    sign_in(client, actor)
    make_report(actor=actor, title="Export fails", customer_label="Acme")
    make_report(actor=actor, title="Login slow", description="acme sso export")
    make_report(actor=actor, title="Captured", source=slack_source())
    make_report(actor=actor, title="Billing", customer_contact_reference="jo@globex.test")
    assert sorted(titles(client.get(reports_url(actor), {"q": "EXPORT"}))) == [
        "Export fails",
        "Login slow",
    ]
    assert titles(client.get(reports_url(actor), {"q": "snapshot"})) == ["Captured"]
    assert titles(client.get(reports_url(actor), {"customer": "acme"})) == ["Export fails"]
    assert titles(client.get(reports_url(actor), {"customer": "globex"})) == ["Billing"]
    assert titles(client.get(reports_url(actor), {"q": "export", "customer": "acme"})) == [
        "Export fails"
    ]


def test_inbox_filters_by_state_assignee_and_source(client: Client) -> None:
    actor = make_membership()
    other = make_membership(workspace=actor.workspace, user=make_user(email="other@example.test"))
    sign_in(client, actor)
    new = make_report(actor=actor, title="New")
    linked = make_report(actor=actor, title="Linked")
    dismissed = make_report(actor=actor, title="Dismissed")
    slack = make_report(actor=actor, title="Slack", source=slack_source())
    problem = make_problem(actor=actor)
    link_report(actor=actor, report_id=linked.pk, expected_version=1, problem_id=problem.pk)
    dismiss_report(actor=actor, report_id=dismissed.pk, expected_version=1)
    assign_report(actor=actor, report_id=new.pk, expected_version=1, assignee_id=other.pk)
    assign_report(actor=actor, report_id=slack.pk, expected_version=1, assignee_id=actor.pk)

    def query(**params: str) -> list[str]:
        response = client.get(reports_url(actor), params)
        assert response.status_code == 200
        return sorted(titles(response))

    assert query(triage_state="linked") == ["Linked"]
    assert query(triage_state="dismissed") == ["Dismissed"]
    assert query(triage_state="new") == ["New", "Slack"]
    assert query(assignee=str(other.pk)) == ["New"]
    assert query(assignee="unassigned") == ["Dismissed", "Linked"]
    assert query(source_kind="slack") == ["Slack"]
    assert query(source_kind="manual", triage_state="new") == ["New"]
    linked_row = client.get(reports_url(actor), {"triage_state": "linked"}).json()["results"][0]
    assert linked_row["problem"] == {
        "id": str(problem.pk),
        "title": problem.title,
        "state": "open",
    }


@pytest.mark.parametrize(
    "params",
    [
        {"triage_state": "archived"},
        {"source_kind": "email"},
        {"assignee": "someone"},
        {"q": "x" * 201},
    ],
)
def test_inbox_rejects_invalid_filters(client: Client, params: dict[str, str]) -> None:
    actor = make_membership()
    sign_in(client, actor)
    response = client.get(reports_url(actor), params)
    assert response.status_code == 400
    assert response.json()["reason"] == "invalid_request"
    assert set(response.json()["field_errors"]) == set(params)


def test_report_detail_includes_provenance_people_and_problem(client: Client) -> None:
    actor = make_membership()
    sign_in(client, actor)
    report = make_report(actor=actor, title="Captured", source=slack_source())
    problem = make_problem(actor=actor, title="Exports")
    assign_report(actor=actor, report_id=report.pk, expected_version=1, assignee_id=actor.pk)
    link_report(actor=actor, report_id=report.pk, expected_version=2, problem_id=problem.pk)
    response = client.get(f"{reports_url(actor)}{report.pk}/")
    assert response.status_code == 200
    body = response.json()
    assert body["provenance"] == {
        "kind": "slack",
        "permalink": "https://example.test/msg",
        "author_display_name": "Slack Author",
        "snapshot_text": "snapshot",
        "captured_at": body["provenance"]["captured_at"],
    }
    member = {"id": str(actor.pk), "full_name": "Test Member", "email": "member@example.test"}
    assert body["submitted_by"] == body["assignee"] == member
    assert body["problem"]["title"] == "Exports" and body["triage_state"] == "linked"
    assert body["version"] == 3


def test_foreign_workspace_reports_are_hidden(client: Client) -> None:
    actor = make_membership()
    foreign = make_membership(
        workspace=make_workspace(slug="foreign"), user=make_user(email="f@example.test")
    )
    foreign_report = make_report(actor=foreign, title="Foreign marker", customer_label="Acme")
    make_report(actor=actor, title="Mine", customer_label="Acme")
    sign_in(client, actor)
    listing = client.get(reports_url(actor), {"customer": "acme"})
    assert titles(listing) == ["Mine"]
    assert client.get(f"{reports_url(actor)}{foreign_report.pk}/").status_code == 404
    assert client.get(f"{reports_url(foreign)}{foreign_report.pk}/").status_code == 404
    assert client.get(reports_url(foreign)).status_code == 404
    assert client.get(reports_url(actor), {"assignee": str(foreign.pk)}).json()["count"] == 0
    response = client.post(
        reports_url(foreign), {"title": "Injected"}, content_type="application/json"
    )
    assert response.status_code == 404
    assert not Report.objects.filter(title="Injected").exists()


def test_revoked_member_loses_inbox_access(client: Client) -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    member = make_membership(workspace=owner.workspace, user=make_user(email="m@example.test"))
    sign_in(client, member)
    assert client.get(reports_url(member)).status_code == 200
    Membership.objects.filter(pk=member.pk).update(is_active=False, revoked_at=owner.created_at)
    assert client.get(reports_url(member)).status_code == 404


def test_member_directory_lists_active_workspace_members(client: Client) -> None:
    actor = make_membership(role=Membership.Role.MEMBER)
    make_membership(
        workspace=actor.workspace, user=make_user(email="a@example.test", full_name="Ada")
    )
    revoked = make_membership(workspace=actor.workspace, user=make_user(email="r@example.test"))
    Membership.objects.filter(pk=revoked.pk).update(is_active=False, revoked_at=actor.created_at)
    make_membership(workspace=make_workspace(slug="other"), user=make_user(email="o@example.test"))
    sign_in(client, actor)
    response = client.get(f"/api/workspaces/{actor.workspace_id}/members/")
    assert response.status_code == 200
    assert [row["email"] for row in response.json()] == ["a@example.test", "member@example.test"]
