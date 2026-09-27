"""Celery tasks that apply verified, deduplicated GitHub webhook deliveries."""

from typing import Any

from celery import shared_task

from feedback.engineering_issues import apply_installation_webhook, apply_issue_webhook
from integrations.github_app.webhooks import parse_installation_event, parse_issue_event


@shared_task
def process_github_delivery(*, event_name: str, payload: dict[str, Any]) -> None:
    """Resolve the installation, then apply a tracked issue or access-loss event.

    An unrecognised installation, untracked action, or malformed payload is a
    no-op or a loud task failure, not a silent partial application: the caller
    already verified the signature, so a shape we do not expect is unexpected.
    """
    installation = payload.get("installation")
    installation_id = str(installation["id"]) if isinstance(installation, dict) else None
    if installation_id is None:
        return
    if event_name == "issues":
        event = parse_issue_event(payload)
        if event is not None:
            apply_issue_webhook(installation_id=installation_id, event=event)
        return
    if event_name in ("installation", "installation_repositories"):
        installation_event = parse_installation_event(event_name, payload)
        if installation_event is not None:
            apply_installation_webhook(installation_id=installation_id, event=installation_event)
