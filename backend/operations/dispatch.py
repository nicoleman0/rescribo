"""Best-effort wakeups for work that is already durable."""

import logging

from celery import current_app

logger = logging.getLogger(__name__)


def dispatch_task(name: str, record_id: str) -> None:
    try:
        task = current_app.tasks.get(name)
        if task is None:
            current_app.loader.import_default_modules()
            task = current_app.tasks[name]
        task.delay(record_id)
    except Exception:
        logger.warning("Task dispatch deferred to the durable dispatcher: %s", name)
