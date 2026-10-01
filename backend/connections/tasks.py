"""Slack capture background work."""

from uuid import UUID

from celery import shared_task

from connections import slack_inbound


@shared_task
def revalidate_capture_channel(context_id: str) -> None:
    slack_inbound.revalidate_capture_channel(UUID(context_id))


@shared_task
def resolve_slack_permalink(source_id: str) -> None:
    slack_inbound.resolve_permalink(UUID(source_id))


@shared_task
def sweep_slack_capture() -> None:
    slack_inbound.sweep()
