"""API tests for persisted GitHub issue previews and approval."""

from typing import Any

import pytest
from builders import (
    make_connection,
    make_membership,
    make_problem,
    make_report,
)
from django.test import Client, TestCase

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.reports import link_report
from feedback.submissions import SourceSnapshot
from operations.models import ExternalOperation

pytestmark = pytest.mark.django_db


def sign_in(client: Client, membership: Membership) -> None:
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()


def issue_url(membership: Membership, problem_id: Any, suffix: str) -> str:
    return f"/api/workspaces/{membership.workspace_id}/problems/{problem_id}/issue/{suffix}/"


def test_preview_get_uses_problem_summary_and_product_link(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor, title="Exports fail", summary="CSV export stops at 50%.")
    sign_in(client, actor)

    response = client.get(issue_url(actor, problem.pk, "preview"))

    assert response.status_code == 200
    assert response.json()["title"] == "Exports fail"
    assert "CSV export stops at 50%." in response.json()["body"]
    assert f"/problems/{problem.pk}" in response.json()["body"]


def test_preview_excludes_customer_and_slack_fields(client: Client) -> None:
    actor = make_membership()
    problem = make_problem(actor=actor, summary="Export stops partway through.")
    source = SourceSnapshot(
        "slack",
        "T1",
        "C1",
        "171234.1",
        "https://example.test/msg",
        "U1",
        "Slack Author",
        "Secret raw Slack excerpt",
    )
    report = make_report(
        actor=actor,
        source=source,
        customer_label="Acme Corp",
        customer_contact_reference="ops@acme.test",
    )
    link_report(
        actor=actor, report_id=report.pk, expected_version=report.version, problem_id=problem.pk
    )
    sign_in(client, actor)

    response = client.get(issue_url(actor, problem.pk, "preview"))

    body = response.json()["body"]
    for forbidden in ("Acme Corp", "ops@acme.test", "Secret raw Slack excerpt", "Slack Author"):
        assert forbidden not in body


def test_preview_persists_exact_content_and_never_writes_to_github(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)

    response = client.post(
        issue_url(actor, problem.pk, "preview"),
        {"expected_version": problem.version, "title": "Edited", "body": "Exact draft"},
        content_type="application/json",
    )

    assert response.status_code == 201
    draft = ExternalOperation.objects.get(pk=response.json()["id"])
    assert draft.state == ExternalOperation.State.DRAFT
    assert draft.title == "Edited"
    assert draft.body == "Exact draft"
    assert response.json()["body"].endswith(f"<!-- rescribo-operation:{draft.pk} -->")


def test_preview_rejects_blank_title_and_requires_connection(client: Client) -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    url = issue_url(actor, problem.pk, "preview")

    invalid = client.post(
        url, {"expected_version": 1, "title": "   "}, content_type="application/json"
    )
    assert invalid.status_code == 400
    connection.delete()
    unavailable = client.post(url, {"expected_version": 1}, content_type="application/json")
    assert unavailable.status_code == 400
    assert not ExternalOperation.objects.filter(problem=problem).exists()


def test_approval_queues_same_persisted_draft_and_replay_is_idempotent(client: Client) -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    sign_in(client, actor)
    preview = client.post(
        issue_url(actor, problem.pk, "preview"),
        {"expected_version": problem.version, "title": "Title", "body": "Body"},
        content_type="application/json",
    )
    draft = preview.json()

    with patch_task_dispatch(), TestCase.captureOnCommitCallbacks(execute=True):
        approved = client.post(
            issue_url(actor, problem.pk, "approve"),
            {"draft_id": draft["id"], "draft_version": draft["draft_version"], "approved": True},
            content_type="application/json",
        )
    assert approved.status_code == 202
    operation = ExternalOperation.objects.get(pk=draft["id"])
    assert operation.state == ExternalOperation.State.QUEUED

    replay = client.post(
        issue_url(actor, problem.pk, "approve"),
        {"draft_id": draft["id"], "draft_version": draft["draft_version"], "approved": True},
        content_type="application/json",
    )
    assert replay.status_code == 202
    assert replay.json()["id"] == approved.json()["id"]


def patch_task_dispatch() -> Any:
    from unittest.mock import patch

    return patch("operations.github_issue_create._dispatch_create")
