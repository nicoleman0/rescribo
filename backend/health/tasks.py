from celery import shared_task


@shared_task
def ping() -> str:
    """A harmless task for verifying the broker-to-worker round trip."""
    return "pong"
