"""Tests for approved and uncertain GitHub issue create operations."""

from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from builders import make_connection, make_membership, make_problem

from feedback.models import EngineeringIssue
from operations.github_issue_create import approve_draft, create_draft
from operations.models import ExternalOperation
from operations.tasks import process_github_issue_create, reconcile_github_issue_create

pytestmark = pytest.mark.django_db

CREATED_ISSUE: dict[str, Any] = {
    "id": 555,
    "number": 7,
    "title": "Export failure",
    "state": "open",
    "state_reason": None,
    "html_url": "https://github.com/acme/widgets/issues/7",
    "repository_url": "https://api.github.com/repos/acme/widgets",
    "repository": {"id": 999, "full_name": "acme/widgets"},
    "updated_at": "2026-09-20T21:00:00Z",
}


def approved_operation(actor: Any, problem: Any) -> ExternalOperation:
    draft = create_draft(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        title="Approved title",
        body="Approved body",
    )
    return approve_draft(
        actor=actor,
        problem_id=problem.pk,
        draft_id=draft.pk,
        draft_version=draft.draft_version,
        approved=True,
    )


def fake_provider(*, create_error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("short-lived", "expires")
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    if create_error is not None:
        client.create_issue.side_effect = create_error
    else:
        client.create_issue.return_value = dict(CREATED_ISSUE)
    return client


def test_approved_content_is_the_only_content_written_and_linked() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider()

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    issue = EngineeringIssue.objects.get(problem=problem, active=True)
    assert operation.state == ExternalOperation.State.SUCCEEDED
    assert client.create_issue.call_count == 1
    assert client.create_issue.call_args.kwargs["title"] == "Approved title"
    sent_body = client.create_issue.call_args.kwargs["body"]
    assert sent_body.startswith("Approved body\n\n<!-- rescribo-operation:")
    assert str(operation.pk) in sent_body
    assert issue.issue_id == "555"


def test_ambiguous_create_is_uncertain_and_never_posts_again() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    client = fake_provider(create_error=httpx.TimeoutException("timeout"))

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
        process_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.UNCERTAIN
    assert client.create_issue.call_count == 1
    assert not EngineeringIssue.objects.filter(problem=problem, active=True).exists()


def test_marker_recovery_paginates_and_ignores_pull_requests() -> None:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    operation = approved_operation(actor, problem)
    operation.state = ExternalOperation.State.UNCERTAIN
    operation.save(update_fields=["state"])
    marker = f"<!-- rescribo-operation:{operation.pk} -->"
    client = fake_provider()
    client.list_issues.side_effect = [
        ([{"pull_request": {}, "body": marker}], True),
        ([{**CREATED_ISSUE, "body": marker}], False),
    ]

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        reconcile_github_issue_create(str(operation.pk))

    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.SUCCEEDED
    assert client.list_issues.call_count == 2
    assert EngineeringIssue.objects.get(problem=problem, active=True).issue_id == "555"
