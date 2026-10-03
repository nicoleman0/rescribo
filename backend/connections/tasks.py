"""Slack capture background work."""

from uuid import UUID

from celery import shared_task

from connections import slack_delivery, slack_inbound


@shared_task
def revalidate_capture_channel(context_id: str) -> None:
    slack_inbound.revalidate_capture_channel(UUID(context_id))


@shared_task
def resolve_slack_permalink(source_id: str) -> None:
    slack_inbound.resolve_permalink(UUID(source_id))


@shared_task
def sweep_slack_capture() -> None:
    slack_inbound.sweep()


@shared_task
def send_follow_up_notification(operation_id: str) -> None:
    slack_delivery.send_follow_up_notification(UUID(operation_id))


@shared_task
def sweep_slack_delivery() -> None:
    slack_delivery.sweep()
