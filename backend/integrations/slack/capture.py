"""Capture persistence boundaries that keep permalink failures retryable."""

from dataclasses import dataclass, replace
from typing import Protocol

from integrations.slack.errors import slack_error_code


class PermalinkClient(Protocol):
    def chat_getPermalink(self, *, channel: str, message_ts: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class CapturedReport:
    report_id: str
    team_id: str
    channel_id: str
    actor_id: str
    message_ts: str
    title: str
    permalink: str | None = None
    permalink_error: str | None = None


def resolve_report_permalink(report: CapturedReport, client: PermalinkClient) -> CapturedReport:
    """Attach a permalink when available without discarding the report."""
    try:
        response = client.chat_getPermalink(channel=report.channel_id, message_ts=report.message_ts)
        permalink = response.get("permalink")
    except Exception as error:
        return replace(report, permalink_error=slack_error_code(error) or type(error).__name__)
    if not isinstance(permalink, str) or not permalink:
        return replace(report, permalink_error="missing_permalink")
    return replace(report, permalink=permalink, permalink_error=None)
