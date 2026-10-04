"""An operation never runs on another workspace's connection. Provider calls are mocked."""

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from builders import make_connection, make_membership, make_problem, make_user, make_workspace

from operations.models import ExternalOperation
from operations.tasks import process_github_issue_create, reconcile_github_issue_create

pytestmark = pytest.mark.django_db


def operation_on_foreign_connection(state: str) -> tuple[ExternalOperation, Any]:
    """An operation in workspace A that names workspace B's connection, written past the ORM."""
    tag = uuid4().hex[:8]
    owner = make_membership(
        workspace=make_workspace(name=f"A {tag}", slug=f"a-{tag}"),
        user=make_user(email=f"a-{tag}@example.test"),
    )
    own = make_connection(workspace=owner.workspace, external_id="1", repository_id="999")
    foreign = make_connection(
        workspace=make_workspace(name=f"B {tag}", slug=f"b-{tag}"),
        external_id="2",
        repository_id="999",
    )
    problem = make_problem(actor=owner)
    operation = ExternalOperation.objects.create(
        kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
        workspace=owner.workspace,
        connection=own,
        problem=problem,
        requester=owner,
        action_key=uuid4(),
        state=state,
        title="Title",
        body="Body",
        destination="acme/widgets",
        repository_id="999",
        problem_version=problem.version,
        binding_revision=foreign.binding_revision,
    )
    ExternalOperation.objects.filter(pk=operation.pk).update(connection=foreign)
    operation.refresh_from_db()
    return operation, foreign


@pytest.mark.parametrize(
    ("state", "task"),
    [
        (ExternalOperation.State.QUEUED, process_github_issue_create),
        (ExternalOperation.State.UNCERTAIN, reconcile_github_issue_create),
    ],
    ids=["create", "reconcile"],
)
def test_operation_naming_another_workspaces_connection_makes_no_provider_call(
    state: str, task: Any
) -> None:
    operation, _ = operation_on_foreign_connection(state)
    with patch("operations.tasks.github_client") as factory:
        task(str(operation.pk))
    factory.assert_not_called()
    operation.refresh_from_db()
    assert operation.state != ExternalOperation.State.SUCCEEDED
    assert not operation.remote_issue_id


def test_issue_naming_another_workspaces_connection_is_not_synced() -> None:
    from builders import make_engineering_issue

    from feedback.engineering_issues import sync_issue
    from feedback.models import EngineeringIssue
    from feedback.tasks import sync_github_issue

    tag = uuid4().hex[:8]
    owner = make_membership(
        workspace=make_workspace(name=f"A {tag}", slug=f"a-{tag}"),
        user=make_user(email=f"a-{tag}@example.test"),
    )
    problem = make_problem(actor=owner)
    foreign = make_connection(
        workspace=make_workspace(name=f"B {tag}", slug=f"b-{tag}"), external_id="2"
    )
    issue = make_engineering_issue(
        problem=problem,
        connection=make_connection(workspace=owner.workspace, external_id="1"),
        created_by=owner,
    )
    EngineeringIssue.objects.filter(pk=issue.pk).update(
        connection=foreign, connection_installation_id=foreign.external_id
    )
    with patch("feedback.engineering_issues.github_client") as factory:
        sync_issue(issue_id=issue.pk)
        sync_github_issue(str(issue.pk))
    factory.assert_not_called()
