"""Committed receipts and operations survive a dead broker and a killed worker.

Real services: PostgreSQL (rows are committed, not rolled back per test) and Redis.
Simulated, not mocked:
- Broker outage: the Celery app is pointed at a port nobody listens on, so publishing
  fails with a real kombu connection error. Recovery publishes to the real Redis.
- Worker crash: a child process claims work and SIGKILLs itself mid-task, leaving the
  lease on the committed row exactly as a dead worker would.
Lease expiry is then simulated by moving lease_expires_at into the past.
"""

import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from builders import make_connection, make_membership, make_problem
from django.conf import settings
from django.db import connection as db_connection
from django.test import Client, override_settings
from django.utils import timezone
from redis import Redis

from config.celery import app
from integrations.github_app.webhooks import IssueEvent
from operations.github_issue_create import approve_draft, create_draft
from operations.models import ExternalOperation, InboundReceipt
from operations.tasks import (
    dispatch_due_operations,
    process_github_issue_create,
    process_inbound_receipt,
)

pytestmark = pytest.mark.django_db(transaction=True)

BACKEND = Path(__file__).resolve().parents[1]
DEAD_BROKER = "redis://127.0.0.1:1/0"
SECRET = "wh-secret"  # matches test_github_webhook_view


def reset_celery_publishers() -> None:
    app._pool = None
    app.amqp._producer_pool = None
    app.amqp.flush_routes()
    app.amqp.__dict__.pop("router", None)


@contextmanager
def broker(url: str | None, queue: str | None = None) -> Iterator[None]:
    """Publish to url (None keeps the configured Redis), optionally into one queue."""
    app.conf.update(
        broker_write_url=url,
        task_routes={"operations.tasks.*": {"queue": queue}} if queue else None,
    )
    reset_celery_publishers()
    try:
        yield
    finally:
        app.conf.update(broker_write_url=None, task_routes=None)
        reset_celery_publishers()


@pytest.fixture
def queue_name() -> Iterator[str]:
    name = f"durability-{uuid4().hex[:12]}"
    yield name
    Redis.from_url(settings.REDIS_URL).delete(name)


@pytest.fixture(autouse=True)
def no_approval_wakeup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("operations.github_issue_create.dispatch_task", lambda *a, **k: None)


def issue_event() -> IssueEvent:
    return IssueEvent(
        action="closed",
        number=7,
        repository="acme/widgets",
        repository_id="999",
        issue_id="555",
        state_reason=None,
        updated_at=timezone.now().isoformat(),
    )


def make_receipt(**overrides: Any) -> InboundReceipt:
    values: dict[str, Any] = {
        "provider": "github",
        "delivery_id": f"d-{uuid4().hex}",
        "event": "issues",
        "installation_id": "42",
        "normalized": issue_event().as_dict(),
    }
    return InboundReceipt.objects.create(**{**values, **overrides})


def queued_operation() -> ExternalOperation:
    actor = make_membership()
    make_connection(workspace=actor.workspace)
    problem = make_problem(actor=actor)
    draft = create_draft(
        actor=actor,
        problem_id=problem.pk,
        expected_version=problem.version,
        title="Approved title",
        body="Approved body",
    )
    operation = approve_draft(
        actor=actor,
        problem_id=problem.pk,
        draft_id=draft.pk,
        draft_version=draft.draft_version,
        approved=True,
    )
    assert operation.state == ExternalOperation.State.QUEUED
    return operation


def fake_provider(create: Callable[..., Any]) -> MagicMock:
    client = MagicMock()
    client.create_installation_token.return_value = ("short-lived", "expires")
    client.get_repository_by_id.return_value = {"id": 999, "full_name": "acme/widgets"}
    client.create_issue.side_effect = create
    return client


def run_in_killed_worker(code: str) -> subprocess.CompletedProcess[bytes]:
    """Run code against the test database in a child that the code kills with SIGKILL."""
    db = db_connection.settings_dict
    url = f"postgresql://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
    env = {
        **os.environ,
        "RESCRIBO_DATABASE_URL": url,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "PYTHONPATH": str(BACKEND),
    }
    preamble = "import django, os, signal; django.setup()\n"
    return subprocess.run(
        [sys.executable, "-c", preamble + code], cwd=BACKEND, env=env, timeout=60, check=False
    )


# Receipts stored before acknowledging, broker down at the time.


@override_settings(RESCRIBO_GITHUB_WEBHOOK_SECRET=SECRET)
def test_webhook_acknowledges_a_stored_receipt_while_the_broker_is_down(client: Client) -> None:
    from test_github_webhook_view import post_webhook, tracked_payload

    delivery = f"d-{uuid4().hex}"
    with broker(DEAD_BROKER):
        response = post_webhook(client, tracked_payload(), delivery=delivery)

    assert response.status_code == 202
    receipt = InboundReceipt.objects.get(provider="github", delivery_id=delivery)
    assert receipt.status == InboundReceipt.Status.PENDING


# Broker outage after commit: the periodic dispatcher recovers the work.


def test_dispatcher_survives_a_dead_broker_and_republishes_after_it_returns(
    queue_name: str,
) -> None:
    operation = queued_operation()
    receipt = make_receipt()

    with broker(DEAD_BROKER):
        dispatch_due_operations()
    operation.refresh_from_db()
    receipt.refresh_from_db()
    assert operation.state == ExternalOperation.State.QUEUED
    assert receipt.status == InboundReceipt.Status.PENDING

    with broker(None, queue_name):
        dispatch_due_operations()
    assert Redis.from_url(settings.REDIS_URL).llen(queue_name) == 2


# Worker crash after claiming: committed work is recovered, not lost or repeated.


def test_receipt_claimed_by_a_killed_worker_is_reclaimed_after_the_lease_expires() -> None:
    receipt = make_receipt()
    result = run_in_killed_worker(
        "from unittest.mock import patch\n"
        "from operations.tasks import process_inbound_receipt\n"
        "with patch('operations.tasks.apply_issue_webhook',"
        " side_effect=lambda **k: os.kill(os.getpid(), signal.SIGKILL)):\n"
        f"    process_inbound_receipt('{receipt.pk}')\n"
    )
    assert result.returncode == -signal.SIGKILL
    receipt.refresh_from_db()
    assert receipt.status == InboundReceipt.Status.RUNNING

    with patch("operations.tasks.dispatch_task") as wakeup:
        dispatch_due_operations()
    wakeup.assert_not_called()

    InboundReceipt.objects.filter(pk=receipt.pk).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    with patch("operations.tasks.dispatch_task") as wakeup:
        dispatch_due_operations()
    wakeup.assert_any_call("operations.tasks.process_inbound_receipt", str(receipt.pk))

    with patch("operations.tasks.apply_issue_webhook") as apply_event:
        process_inbound_receipt(str(receipt.pk))
    apply_event.assert_called_once()
    receipt.refresh_from_db()
    assert receipt.status == InboundReceipt.Status.SUCCEEDED
    assert receipt.attempts == 2


def test_operation_killed_during_the_write_becomes_uncertain_and_is_never_resent() -> None:
    operation = queued_operation()
    result = run_in_killed_worker(
        "from unittest.mock import MagicMock, patch\n"
        "from operations.tasks import process_github_issue_create\n"
        "client = MagicMock()\n"
        "client.create_installation_token.return_value = ('t', 'e')\n"
        "client.get_repository_by_id.return_value = {'id': 999, 'full_name': 'acme/widgets'}\n"
        "client.create_issue.side_effect = lambda **k: os.kill(os.getpid(), signal.SIGKILL)\n"
        "with patch('operations.tasks.github_client') as factory:\n"
        "    factory.return_value.__enter__.return_value = client\n"
        f"    process_github_issue_create('{operation.pk}')\n"
    )
    assert result.returncode == -signal.SIGKILL
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.RUNNING

    ExternalOperation.objects.filter(pk=operation.pk).update(
        lease_expires_at=timezone.now() - timedelta(seconds=1)
    )
    with patch("operations.tasks.dispatch_task"):
        dispatch_due_operations()
    operation.refresh_from_db()
    assert operation.state == ExternalOperation.State.UNCERTAIN
    assert operation.safe_error == "worker_lease_expired"

    client = fake_provider(lambda **k: {})
    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        process_github_issue_create(str(operation.pk))
    client.create_issue.assert_not_called()


# Atomic claim under real concurrency.


def run_concurrently(target: Callable[[], None], count: int = 2) -> None:
    threads = [threading.Thread(target=target) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads)


def test_concurrent_workers_apply_a_receipt_once() -> None:
    receipt = make_receipt()
    calls: list[int] = []

    def slow_apply(**kwargs: Any) -> None:
        calls.append(1)
        time.sleep(1)  # hold the claim while the other worker tries

    def work() -> None:
        try:
            process_inbound_receipt(str(receipt.pk))
        finally:
            db_connection.close()

    with patch("operations.tasks.apply_issue_webhook", side_effect=slow_apply):
        run_concurrently(work)

    assert len(calls) == 1
    receipt.refresh_from_db()
    assert (receipt.status, receipt.attempts) == (InboundReceipt.Status.SUCCEEDED, 1)


def test_concurrent_workers_write_an_operation_once() -> None:
    operation = queued_operation()

    def slow_create(**kwargs: Any) -> Any:
        time.sleep(1)  # hold the claim while the other worker tries
        raise TimeoutError("ambiguous")

    client = fake_provider(slow_create)

    def work() -> None:
        try:
            process_github_issue_create(str(operation.pk))
        finally:
            db_connection.close()

    with patch("operations.tasks.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        run_concurrently(work)

    assert client.create_issue.call_count == 1
    operation.refresh_from_db()
    assert operation.attempts == 1
