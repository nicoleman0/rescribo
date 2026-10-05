"""Run two writers on separate PostgreSQL connections with a fixed lock interleaving."""

import threading
from collections.abc import Callable
from typing import Any

from django.db import connection, connections, transaction

WAIT_SECONDS = 10


def backend_pid() -> int:
    connection.ensure_connection()
    return int(connection.connection.info.backend_pid)


def waiting_on_lock(pid: int) -> bool:
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
        row = cursor.fetchone()
    return row is not None and row[0] == "Lock"


def race(
    holder: Callable[[], Any],
    challenger: Callable[[], Any],
    *,
    then: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Run holder in an open transaction; release it once challenger waits on a lock.

    `then` runs in the holder's transaction after the challenger is queued, so a holder can
    take its second lock while the challenger already holds its first.
    """
    holder_locked = threading.Event()
    release = threading.Event()
    challenger_pid: list[int] = []
    outcomes: dict[str, Any] = {}

    def run(name: str, work: Callable[[], Any]) -> None:
        try:
            outcomes[name] = work()
        except Exception as error:
            outcomes[name] = error
        finally:
            connection.close()

    def hold() -> Any:
        with transaction.atomic():
            result = holder()
            holder_locked.set()
            if not release.wait(WAIT_SECONDS):
                raise TimeoutError("The challenger never queued behind the holder.")
            if then is not None:
                then()
            return result

    def challenge() -> Any:
        challenger_pid.append(backend_pid())
        if not holder_locked.wait(WAIT_SECONDS):
            raise TimeoutError("The holder never took its locks.")
        return challenger()

    threads = [
        threading.Thread(target=run, args=("holder", hold)),
        threading.Thread(target=run, args=("challenger", challenge)),
    ]
    for thread in threads:
        thread.start()
    holder_locked.wait(WAIT_SECONDS)
    queued = threading.Event()
    for _ in range(WAIT_SECONDS * 100):
        if challenger_pid and waiting_on_lock(challenger_pid[0]):
            queued.set()
            break
        queued.wait(0.01)
    release.set()
    for thread in threads:
        thread.join(WAIT_SECONDS)
    assert queued.is_set(), "The challenger did not wait on a row lock."
    assert not any(thread.is_alive() for thread in threads)
    return outcomes
