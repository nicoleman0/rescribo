import pytest
from builders import (
    make_connection,
    make_engineering_issue,
    make_membership,
    make_problem,
    make_user,
    make_workspace,
)
from django.db import IntegrityError, transaction

from feedback.models import EngineeringIssue

pytestmark = pytest.mark.django_db


def test_one_active_issue_per_problem_constraint() -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    connection = make_connection(workspace=actor.workspace)
    make_engineering_issue(problem=problem, connection=connection, created_by=actor, issue_id="1")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_engineering_issue(
            problem=problem, connection=connection, created_by=actor, issue_id="2"
        )

    # A superseded (inactive) row never conflicts with the active one.
    make_engineering_issue(
        problem=problem,
        connection=connection,
        created_by=actor,
        issue_id="3",
        active=False,
        unlinked_at=actor.created_at,
    )


def test_one_active_problem_per_issue_constraint() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    first = make_problem(actor=actor, title="First problem")
    second = make_problem(actor=actor, title="Second problem")
    make_engineering_issue(
        problem=first, connection=connection, created_by=actor, issue_id="555", number=7
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        make_engineering_issue(
            problem=second, connection=connection, created_by=actor, issue_id="555", number=7
        )


def test_issue_uniqueness_is_workspace_scoped() -> None:
    actor = make_membership()
    connection = make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    make_engineering_issue(
        problem=problem, connection=connection, created_by=actor, issue_id="555", number=7
    )

    other_actor = make_membership(
        user=make_user(email="other@example.test"),
        workspace=make_workspace(slug="other", name="Other"),
    )
    other_connection = make_connection(workspace=other_actor.workspace)
    other_problem = make_problem(actor=other_actor)
    other_issue = make_engineering_issue(
        problem=other_problem,
        connection=other_connection,
        created_by=other_actor,
        issue_id="555",
        number=7,
    )
    assert other_issue.pk is not None


def test_save_asserts_workspace_matches_problem_workspace() -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    other_actor = make_membership(
        user=make_user(email="other@example.test"),
        workspace=make_workspace(slug="other", name="Other"),
    )
    connection = make_connection(workspace=other_actor.workspace)

    with pytest.raises(AssertionError):
        EngineeringIssue.objects.create(
            workspace=other_actor.workspace,
            problem=problem,
            connection=connection,
            repository_id=connection.repository_id,
            issue_id="1",
            number=1,
            url="https://github.com/acme/widgets/issues/1",
            title="Mismatched workspace",
            state=EngineeringIssue.State.OPEN,
            provider_updated_at=actor.created_at,
            created_by=other_actor,
        )
