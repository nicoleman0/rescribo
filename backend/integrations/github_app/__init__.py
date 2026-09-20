"""GitHub App integration boundary."""

from integrations.github_app.client import GitHubAppClient
from integrations.github_app.issues import IssueLinkError, LinkedIssue, resolve_issue_link
from integrations.github_app.probe import InstallationProbe, ProbeResult
from integrations.github_app.state import OAuthStateStore
from integrations.github_app.webhooks import (
    InstallationEvent,
    InvalidWebhookSignature,
    IssueEvent,
    IssueStateOutcome,
    apply_issue_event,
    parse_installation_event,
    parse_issue_event,
    verify_webhook_signature,
)

__all__ = [
    "GitHubAppClient",
    "InstallationEvent",
    "InstallationProbe",
    "InvalidWebhookSignature",
    "IssueEvent",
    "IssueLinkError",
    "IssueStateOutcome",
    "LinkedIssue",
    "OAuthStateStore",
    "ProbeResult",
    "apply_issue_event",
    "parse_installation_event",
    "parse_issue_event",
    "resolve_issue_link",
    "verify_webhook_signature",
]
