import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from integrations.github_app.client import GitHubAPIError, GitHubAppClient


class InvalidWebhookSignature(PermissionError):
    """The webhook signature header is missing or does not match the payload."""


class InvalidWebhookPayload(ValueError):
    """The webhook payload is missing required fields."""


def verify_webhook_signature(*, secret: bytes, body: bytes, signature_header: str | None) -> None:
    if not signature_header or not signature_header.startswith("sha256="):
        raise InvalidWebhookSignature("The webhook signature header is missing.")
    expected = f"sha256={hmac.new(secret, body, hashlib.sha256).hexdigest()}"
    if not hmac.compare_digest(expected, signature_header):
        raise InvalidWebhookSignature("The webhook signature does not match the payload.")


@dataclass(frozen=True)
class IssueEvent:
    action: str
    number: int
    repository: str
    state_reason: str | None
    updated_at: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_TRACKED_ISSUE_ACTIONS = {"closed", "reopened", "edited", "deleted"}


def parse_issue_event(payload: Mapping[str, Any]) -> IssueEvent | None:
    """Parse an issues webhook payload. Returns None for untracked actions."""
    action = payload.get("action")
    if action not in _TRACKED_ISSUE_ACTIONS:
        return None
    issue = payload.get("issue")
    repository = payload.get("repository")
    if not isinstance(issue, dict) or not isinstance(repository, dict):
        raise InvalidWebhookPayload("The issues event lacks issue or repository data.")
    number = issue.get("number")
    full_name = repository.get("full_name")
    updated_at = issue.get("updated_at")
    state_reason = issue.get("state_reason")
    if not (isinstance(number, int) and isinstance(full_name, str) and isinstance(updated_at, str)):
        raise InvalidWebhookPayload("The issues event has an invalid issue payload.")
    if state_reason is not None and not isinstance(state_reason, str):
        raise InvalidWebhookPayload("The issues event has an invalid state_reason.")
    return IssueEvent(
        action=action,
        number=number,
        repository=full_name,
        state_reason=state_reason,
        updated_at=updated_at,
    )


@dataclass(frozen=True)
class InstallationEvent:
    event: str
    action: str
    repositories_removed: tuple[str, ...]
    access_lost: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_installation_event(
    event_name: str, payload: Mapping[str, Any]
) -> InstallationEvent | None:
    """Parse installation lifecycle events that signal access loss."""
    if event_name == "installation":
        action = payload.get("action")
        if action not in {"deleted", "suspend", "unsuspend", "new_permissions_accepted"}:
            return None
        return InstallationEvent(
            event=event_name,
            action=str(action),
            repositories_removed=(),
            access_lost=action in {"deleted", "suspend"},
        )
    if event_name == "installation_repositories":
        action = payload.get("action")
        if action != "removed":
            return None
        removed = payload.get("repositories_removed")
        if not isinstance(removed, list):
            raise InvalidWebhookPayload("The installation_repositories event is malformed.")
        names = tuple(
            repository["full_name"]
            for repository in removed
            if isinstance(repository, dict) and isinstance(repository.get("full_name"), str)
        )
        return InstallationEvent(
            event=event_name,
            action="removed",
            repositories_removed=names,
            access_lost=True,
        )
    return None


@dataclass(frozen=True)
class IssueStateOutcome:
    number: int
    applied: bool
    access: Literal["ok", "access_lost"]
    state: str | None
    state_reason: str | None
    updated_at: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _provider_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def apply_issue_event(
    client: GitHubAppClient,
    *,
    installation_token: str,
    expected_repository: str,
    event: IssueEvent,
    stored_updated_at: str | None,
) -> IssueStateOutcome:
    """Apply a verified issues event after fetching current state from GitHub.

    The webhook payload is never trusted for state. An inaccessible issue is
    reported as access_lost, never as closed. A fetch whose provider timestamp
    is not newer than the stored one is treated as a stale delivery.
    """
    if event.repository.lower() != expected_repository.lower():
        raise InvalidWebhookPayload(
            f"The event belongs to {event.repository}, not {expected_repository}."
        )
    owner, _, name = expected_repository.partition("/")
    try:
        issue = client.get_issue(
            installation_token=installation_token,
            owner=owner,
            name=name,
            number=event.number,
        )
    except GitHubAPIError as error:
        if error.status_code in {404, 410}:
            return IssueStateOutcome(
                number=event.number,
                applied=False,
                access="access_lost",
                state=None,
                state_reason=None,
                updated_at=None,
            )
        raise
    fetched_updated_at = issue.get("updated_at")
    state = issue.get("state")
    state_reason = issue.get("state_reason")
    if not (isinstance(fetched_updated_at, str) and isinstance(state, str)):
        raise InvalidWebhookPayload("GitHub returned an incomplete issue payload.")
    if stored_updated_at is not None and _provider_time(fetched_updated_at) <= _provider_time(
        stored_updated_at
    ):
        return IssueStateOutcome(
            number=event.number,
            applied=False,
            access="ok",
            state=state,
            state_reason=state_reason if isinstance(state_reason, str) else None,
            updated_at=fetched_updated_at,
        )
    return IssueStateOutcome(
        number=event.number,
        applied=True,
        access="ok",
        state=state,
        state_reason=state_reason if isinstance(state_reason, str) else None,
        updated_at=fetched_updated_at,
    )
