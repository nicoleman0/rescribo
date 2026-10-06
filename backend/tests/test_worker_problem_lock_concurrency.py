"""Worker problem locks allow FK references while still excluding other writers."""

from collections.abc import Callable
from functools import partial
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from concurrency import race
from django.db import DatabaseError, connection, connections, transaction
from django.utils import timezone
from issue_world import World, github_reads

from feedback.engineering_issues import (
    _finish_issue_sync_failure,
    apply_installation_webhook,
    refresh_issue,
    sync_issue,
)
from feedback.models import EngineeringIssue, Problem
from feedback.tasks import _complete_reconciliation_target, reconcile_github_issues
from integrations.github_app.webhooks import InstallationEvent
from operations.github_issue_create import approve_draft, create_draft
from operations.models import ExternalOperation
from operations.tasks import process_github_issue_create, revalidate_github_connection

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def issue_draft(world: World) -> ExternalOperation:
    world.issue.delete()
    world.problem.refresh_from_db()
    return create_draft(
        actor=world.actor,
        problem_id=world.problem.pk,
        expected_version=world.problem.version,
    )


def test_reconciliation(world: World) -> None:
    assert_problem_locks(world, reconcile_github_issues, expected_locks=1)


def test_reconciliation_completion(world: World) -> None:
    assert_problem_locks(
        world, partial(_complete_reconciliation_target, world.issue.pk), expected_locks=1
    )


def test_refresh(world: World) -> None:
    assert_problem_locks(
        world,
        partial(
            refresh_issue,
            actor=world.actor,
            problem_id=world.problem.pk,
            expected_issue_id=world.issue.pk,
        ),
        expected_locks=1,
    )


def test_sync_claim(world: World) -> None:
    assert_problem_locks(world, partial(sync_issue, issue_id=world.issue.pk), expected_locks=2)


def test_sync_failure(world: World) -> None:
    claim = uuid4()
    EngineeringIssue.objects.filter(pk=world.issue.pk).update(sync_lease_token=claim)
    assert_problem_locks(
        world,
        partial(
            _finish_issue_sync_failure,
            issue_id=world.issue.pk,
            connection_id=world.connection.pk,
            problem_id=world.problem.pk,
            workspace_id=world.actor.workspace_id,
            claim=claim,
            now=timezone.now(),
            error_code="inaccessible",
        ),
        expected_locks=1,
    )


def test_installation_status(world: World) -> None:
    assert_problem_locks(
        world,
        partial(
            apply_installation_webhook,
            installation_id=world.connection.external_id,
            event=InstallationEvent(
                event="installation", action="suspend", repositories_removed=(), access_lost=True
            ),
        ),
        expected_locks=1,
    )


def test_create_worker(world: World, issue_draft: ExternalOperation) -> None:
    ExternalOperation.objects.filter(pk=issue_draft.pk).update(state=ExternalOperation.State.QUEUED)
    assert_problem_locks(
        world, partial(process_github_issue_create, str(issue_draft.pk)), expected_locks=3
    )


def test_revalidation(world: World) -> None:
    assert_problem_locks(
        world, partial(revalidate_github_connection, str(world.connection.pk)), expected_locks=1
    )


def test_approval(world: World, issue_draft: ExternalOperation) -> None:
    assert_problem_locks(
        world,
        partial(
            approve_draft,
            actor=world.actor,
            problem_id=world.problem.pk,
            draft_id=issue_draft.pk,
            draft_version=issue_draft.draft_version,
            approved=True,
        ),
        expected_locks=1,
    )


def assert_problem_locks(world: World, work: Callable[[], Any], *, expected_locks: int) -> None:
    locks_checked = 0
    reference_errors: list[DatabaseError] = []

    def check_reference(
        execute: Callable[..., Any], sql: str, params: Any, many: bool, context: Any
    ) -> Any:
        nonlocal locks_checked
        result = execute(sql, params, many, context)
        if f'FROM "{Problem._meta.db_table}"' in sql and "FOR " in sql:
            # Use a separate connection to exercise the FK lock at every acquisition/upgrade.
            member = connections.create_connection("default")
            try:
                with member.cursor() as cursor:
                    cursor.execute("BEGIN")
                    cursor.execute("SET LOCAL lock_timeout = '500ms'")
                    cursor.execute(
                        f"SELECT id FROM {Problem._meta.db_table} WHERE id = %s FOR KEY SHARE",
                        [world.problem.pk],
                    )
                    assert cursor.fetchone() is not None
                locks_checked += 1
            except DatabaseError as error:
                reference_errors.append(error)
            finally:
                member.close()
        return result

    def worker() -> None:
        with connection.execute_wrapper(check_reference):
            work()

    def competing_writer() -> None:
        with transaction.atomic():
            Problem.objects.select_for_update(no_key=True).get(pk=world.problem.pk)

    with (
        patch("feedback.tasks.dispatch_task"),
        patch("feedback.engineering_issues.dispatch_task"),
        patch("operations.github_issue_create.dispatch_task"),
        patch("operations.tasks.dispatch_task"),
        patch("operations.tasks.github_client") as factory,
        github_reads(world.github_says(state="closed", seconds=30)) as client,
    ):
        client.create_issue.return_value = world.github_says(state="open", seconds=30)
        factory.return_value.__enter__.return_value = client
        outcomes = race(worker, competing_writer)

    errors = {name: out for name, out in outcomes.items() if isinstance(out, Exception)}
    assert not errors, f"A side was aborted: {errors!r}"
    assert not reference_errors, f"A problem reference was blocked: {reference_errors!r}"
    assert locks_checked == expected_locks
