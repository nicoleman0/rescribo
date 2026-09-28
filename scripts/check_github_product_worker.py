"""Check durable GitHub work recovery through a restarted Celery worker."""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from accounts.models import Membership, User, Workspace  # noqa: E402
from connections.models import Connection  # noqa: E402
from feedback.models import Problem  # noqa: E402
from operations.models import ExternalOperation, InboundReceipt  # noqa: E402
from operations.tasks import dispatch_due_operations  # noqa: E402


def start_worker(log_path: str, queue: str) -> tuple[subprocess.Popen[bytes], str]:
    hostname = f"issue10-{uuid4().hex[:8]}@localhost"
    with open(log_path, "ab") as log:
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "celery",
                "--workdir=backend",
                "-A",
                "config",
                "worker",
                "--loglevel=WARNING",
                "--pool=solo",
                f"--queues={queue}",
                "--include=operations.tasks,feedback.tasks",
                f"--hostname={hostname}",
            ],
            cwd=ROOT,
            env={**os.environ, "RESCRIBO_CELERY_DEFAULT_QUEUE": queue},
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return process, hostname


def stop_worker(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def wait_for_worker(process: subprocess.Popen[bytes], hostname: str) -> None:
    from config.celery import app

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("The product-check worker exited during startup.")
        if app.control.ping(timeout=1, destination=[hostname]):
            return
        time.sleep(0.25)
    raise TimeoutError("The product-check worker did not become ready.")


def main() -> None:
    suffix = uuid4().hex
    workspace = Workspace.objects.create(name="Issue 10 worker check", slug=f"issue10-{suffix}")
    user = User.objects.create_user(email=f"issue10-{suffix}@example.test")
    member = Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.OWNER)
    connection = Connection.objects.create(
        workspace=workspace,
        provider=Connection.Provider.GITHUB,
        external_id="1",
        repository="example/project",
        repository_id="1",
        status=Connection.Status.ERROR,
    )
    problem = Problem.objects.create(workspace=workspace, title="Worker recovery check")
    operation = ExternalOperation.objects.create(
        kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
        workspace=workspace,
        connection=connection,
        problem=problem,
        requester=member,
        action_key=uuid4(),
        state=ExternalOperation.State.QUEUED,
        title="Synthetic",
        body="The stale connection prevents provider access.",
        destination=connection.repository,
        repository_id=connection.repository_id,
        problem_version=problem.version,
        binding_revision=connection.binding_revision,
    )
    receipt = InboundReceipt.objects.create(
        provider=InboundReceipt.Provider.GITHUB,
        delivery_id=f"issue10-{suffix}",
        event="irrelevant",
    )
    worker: subprocess.Popen[bytes] | None = None
    with tempfile.NamedTemporaryFile(prefix="issue10-worker-", suffix=".log") as log:
        try:
            queue = f"issue10-{suffix[:12]}"
            from config.celery import app

            app.conf.update(task_default_queue=queue, task_default_routing_key=queue)
            worker, hostname = start_worker(log.name, queue)
            wait_for_worker(worker, hostname)
            stop_worker(worker)
            worker, hostname = start_worker(log.name, queue)
            wait_for_worker(worker, hostname)
            result = dispatch_due_operations.apply_async(queue=queue)
            result.get(timeout=15, propagate=True)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                operation.refresh_from_db()
                receipt.refresh_from_db()
                if (
                    operation.state == ExternalOperation.State.CANCELLED
                    and receipt.status == InboundReceipt.Status.SUCCEEDED
                ):
                    print("Committed receipt and operation recovered after worker restart: OK")
                    return
                time.sleep(0.25)
            raise TimeoutError(
                f"Durable work remained pending: operation={operation.state}, "
                f"receipt={receipt.status}"
            )
        finally:
            if worker is not None:
                stop_worker(worker)
            operation.delete()
            receipt.delete()
            problem.delete()
            connection.delete()
            member.delete()
            user.delete()
            workspace.delete()


if __name__ == "__main__":
    main()
