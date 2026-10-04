"""Celery entry points for match runs."""

from uuid import UUID

from celery import shared_task

from matching.runs import execute_run, recover_runs


@shared_task
def run_match(run_id: str) -> None:
    execute_run(UUID(run_id))


@shared_task
def recover_match_runs() -> None:
    recover_runs()
