import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from integrations.github_app.client import GitHubAPIError, GitHubAppClient
from integrations.github_app.issues import (
    EngineeringIssueSnapshot,
    parse_issue_payload,
    provider_time,
)


class InvalidWebhookSignature(PermissionError):
    """The webhook signature header is missing or does not match the payload."""


class InvalidWebhookPayload(ValueError):
    """The webhook payload is missing required fields."""


def verify_webhook_signature(*, secret: bytes, body: bytes, signature_header: str | None) -> None:
    if not signature_header:
        raise InvalidWebhookSignature("The webhook signature header is missing.")
    if not signature_header.startswith("sha256="):
        raise InvalidWebhookSignature("The webhook signature header is malformed.")
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
    repository_id: str
    issue_id: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_TRACKED_ISSUE_ACTIONS = {"closed", "reopened", "edited", "deleted", "transferred"}


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
    issue_id = issue.get("id")
    full_name = repository.get("full_name")
    repository_id = repository.get("id")
    updated_at = issue.get("updated_at")
    state_reason = issue.get("state_reason")
    if not (
        isinstance(number, int)
        and not isinstance(number, bool)
        and number > 0
        and isinstance(issue_id, int)
        and not isinstance(issue_id, bool)
        and issue_id > 0
        and isinstance(repository_id, int)
        and not isinstance(repository_id, bool)
        and repository_id > 0
        and isinstance(full_name, str)
        and "/" in full_name
        and isinstance(updated_at, str)
    ):
        raise InvalidWebhookPayload("The issues event has an invalid issue payload.")
    try:
        provider_time(updated_at)
    except (ValueError, OverflowError) as error:
        raise InvalidWebhookPayload("The issues event has an invalid updated_at value.") from error
    if state_reason is not None and not isinstance(state_reason, str):
        raise InvalidWebhookPayload("The issues event has an invalid state_reason.")
    return IssueEvent(
        action=action,
        number=number,
        repository=full_name,
        state_reason=state_reason,
        updated_at=updated_at,
        repository_id=str(repository_id),
        issue_id=str(issue_id),
    )


@dataclass(frozen=True)
class InstallationEvent:
    event: str
    action: str
    repositories_removed: tuple[str, ...]
    access_lost: bool
    repositories_removed_ids: tuple[str, ...] = ()
    repositories_added_ids: tuple[str, ...] = ()

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
        if action not in {"removed", "added"}:
            return None
        field = "repositories_removed" if action == "removed" else "repositories_added"
        removed = payload.get(field)
        if not isinstance(removed, list):
            raise InvalidWebhookPayload("The installation_repositories event is malformed.")
        if any(
            not isinstance(repository, dict)
            or not isinstance(repository.get("id"), int)
            or isinstance(repository.get("id"), bool)
            or repository["id"] <= 0
            or not isinstance(repository.get("full_name"), str)
            for repository in removed
        ):
            raise InvalidWebhookPayload("The installation_repositories event is malformed.")
        names = tuple(repository["full_name"] for repository in removed)
        ids = tuple(str(repository["id"]) for repository in removed)
        return InstallationEvent(
            event=event_name,
            action=action,
            repositories_removed=names if action == "removed" else (),
            access_lost=action == "removed",
            repositories_removed_ids=ids if action == "removed" else (),
            repositories_added_ids=ids if action == "added" else (),
        )
    return None


@dataclass(frozen=True)
class IssueStateOutcome:
    """The result of fetching current issue state for one event.

    `snapshot` is None exactly when `access` is `access_lost`. `applied` tells the
    caller whether `snapshot.updated_at` is newer than what is already stored: callers
    must only overwrite persisted state and `provider_updated_at` when `applied` is
    True, so a stale or replayed delivery cannot roll stored state backward.
    """

    number: int
    applied: bool
    access: Literal["ok", "access_lost"]
    snapshot: EngineeringIssueSnapshot | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_issue_event(
    client: GitHubAppClient,
    *,
    installation_token: str,
    expected_repository: str,
    expected_repository_id: str,
    event: IssueEvent,
    stored_updated_at: str | None,
    stored_state: str | None = None,
) -> IssueStateOutcome:
    """Apply a verified issues event after fetching current state from GitHub.

    The webhook payload is never trusted for state. An inaccessible issue is
    reported as access_lost, never as closed. A fetch whose provider timestamp
    is not newer than the stored one is treated as a stale delivery: `snapshot`
    still carries GitHub's current answer, but `applied` is False so the caller
    knows not to persist it.

    A `transferred` event fired by the destination repository arrives with a
    repository that no longer matches the binding; that is the expected signal
    that the issue left the bound repository and is reported as access_lost.
    """
    if event.action == "transferred" and event.repository.lower() != expected_repository.lower():
        return IssueStateOutcome(
            number=event.number, applied=False, access="access_lost", snapshot=None
        )
    if event.repository.lower() != expected_repository.lower():
        raise InvalidWebhookPayload(
            f"The event belongs to {event.repository}, not {expected_repository}."
        )
    return fetch_current_issue(
        client,
        installation_token=installation_token,
        expected_repository=expected_repository,
        expected_repository_id=expected_repository_id,
        number=event.number,
        issue_id=event.issue_id,
        stored_updated_at=stored_updated_at,
        stored_state=stored_state,
    )


def fetch_current_issue(
    client: GitHubAppClient,
    *,
    installation_token: str,
    expected_repository: str,
    expected_repository_id: str,
    number: int,
    issue_id: str,
    stored_updated_at: str | None,
    stored_state: str | None = None,
) -> IssueStateOutcome:
    owner, _, name = expected_repository.partition("/")
    try:
        issue = client.get_issue(
            installation_token=installation_token,
            owner=owner,
            name=name,
            number=number,
        )
    except GitHubAPIError as error:
        if error.status_code in {301, 404, 410}:
            return IssueStateOutcome(
                number=number, applied=False, access="access_lost", snapshot=None
            )
        raise
    snapshot = parse_issue_payload(issue, error=InvalidWebhookPayload)
    if snapshot.repository_id != expected_repository_id:
        raise InvalidWebhookPayload("The fetched issue belongs to another repository identity.")
    if snapshot.issue_id != issue_id:
        raise InvalidWebhookPayload("The fetched issue has a different stable identity.")
    fetched_time = provider_time(snapshot.updated_at)
    stored_time = provider_time(stored_updated_at) if stored_updated_at else None
    applied = (
        stored_time is None
        or fetched_time > stored_time
        or (fetched_time == stored_time and snapshot.state != stored_state)
    )
    return IssueStateOutcome(number=number, applied=applied, access="ok", snapshot=snapshot)


@dataclass(frozen=True)
class NormalizedDelivery:
    event: str
    action: str
    installation_id: str
    repository_id: str
    issue_id: str
    normalized: dict[str, Any]
    provider_at: datetime | None


def parse_delivery(headers: Mapping[str, str], body: bytes) -> NormalizedDelivery | None:
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidWebhookPayload("The delivery must contain JSON.") from error
    if not isinstance(payload, dict):
        raise InvalidWebhookPayload("The delivery must be an object.")
    event_name = headers.get("X-GitHub-Event", "")
    if event_name == "issues":
        parsed = parse_issue_event(payload)
        if parsed is None:
            return None
        normalized = parsed.as_dict()
        action, repository_id, issue_id = parsed.action, parsed.repository_id, parsed.issue_id
        provider_at = provider_time(parsed.updated_at)
    elif event_name in {"installation", "installation_repositories"}:
        installation_event = parse_installation_event(event_name, payload)
        if installation_event is None:
            return None
        normalized = installation_event.as_dict()
        action = installation_event.action
        ids = (
            installation_event.repositories_removed_ids + installation_event.repositories_added_ids
        )
        repository_id, issue_id = ids[0] if len(ids) == 1 else "", ""
        provider_at = None
    else:
        return None
    installation = payload.get("installation")
    if not isinstance(installation, dict):
        raise InvalidWebhookPayload("The delivery lacks an installation.")
    installation_id = installation.get("id")
    if (
        not isinstance(installation_id, int)
        or isinstance(installation_id, bool)
        or installation_id <= 0
    ):
        raise InvalidWebhookPayload("The installation identity is invalid.")
    if event_name != "issues" and installation.get("updated_at") is not None:
        raw_time = installation["updated_at"]
        if not isinstance(raw_time, str):
            raise InvalidWebhookPayload("The provider timestamp is malformed.")
        try:
            provider_at = provider_time(raw_time)
        except (ValueError, OverflowError) as error:
            raise InvalidWebhookPayload("The provider timestamp is malformed.") from error
    return NormalizedDelivery(
        event_name, action, str(installation_id), repository_id, issue_id, normalized, provider_at
    )
