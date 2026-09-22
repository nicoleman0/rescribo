"""Provider-neutral input contract for report capture."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSnapshot:
    kind: str
    external_workspace_id: str
    external_channel_id: str
    external_message_id: str
    permalink: str
    author_external_id: str
    author_display_name: str
    snapshot_text: str


@dataclass(frozen=True)
class ReportSubmission:
    title: str
    description: str
    customer_label: str
    customer_contact_reference: str
    affected_version: str
    source: SourceSnapshot | None
