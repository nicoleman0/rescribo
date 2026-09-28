import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from integrations.github_app.client import GitHubAPIError, GitHubAppClient


class IssueLinkError(ValueError):
    """The reference cannot be linked to the configured repository."""


def provider_time(value: str) -> datetime:
    """Parse a GitHub ISO-8601 timestamp for comparison and storage."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("Provider timestamps must include a timezone.")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class EngineeringIssueSnapshot:
    """The typed read result for one GitHub issue, shared by link, webhook, and reconcile reads."""

    issue_id: str
    number: int
    title: str
    url: str
    state: str
    state_reason: str | None
    updated_at: str
    repository_id: str = ""
    repository_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_issue_payload(
    issue: Mapping[str, Any], *, error: type[Exception]
) -> EngineeringIssueSnapshot:
    issue_id = issue.get("id")
    number = issue.get("number")
    title = issue.get("title")
    state = issue.get("state")
    updated_at = issue.get("updated_at")
    url = issue.get("html_url")
    state_reason = issue.get("state_reason")
    repository = issue.get("repository")
    repository_id = repository.get("id") if isinstance(repository, Mapping) else None
    repository_name = repository.get("full_name") if isinstance(repository, Mapping) else None
    if not (
        isinstance(issue_id, int)
        and not isinstance(issue_id, bool)
        and issue_id > 0
        and isinstance(number, int)
        and not isinstance(number, bool)
        and number > 0
        and isinstance(title, str)
        and bool(title.strip())
        and state in {"open", "closed"}
        and isinstance(updated_at, str)
        and isinstance(url, str)
        and isinstance(repository_id, int)
        and not isinstance(repository_id, bool)
        and repository_id > 0
        and isinstance(repository_name, str)
        and repository_name.count("/") == 1
    ):
        raise error("GitHub returned an incomplete issue payload.")
    if state_reason is not None and not isinstance(state_reason, str):
        raise error("GitHub returned an invalid issue state_reason.")
    try:
        provider_time(updated_at)
    except (ValueError, OverflowError) as failure:
        raise error("GitHub returned an invalid issue timestamp.") from failure
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or parsed_url.netloc.lower() != "github.com":
        raise error("GitHub returned a foreign issue URL.")
    if (
        parsed_url.path.lower() != f"/{repository_name}/issues/{number}".lower()
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise error("GitHub returned a mismatched issue URL.")
    return EngineeringIssueSnapshot(
        issue_id=str(issue_id),
        number=number,
        title=title,
        url=url,
        state=state,
        state_reason=state_reason,
        updated_at=updated_at,
        repository_id=str(repository_id),
        repository_name=repository_name,
    )


_ISSUE_URL = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9][A-Za-z0-9_.-]*)/"
    r"(?P<name>[A-Za-z0-9_.-]+)/issues/(?P<number>[1-9][0-9]*)/?$"
)


def parse_issue_reference(reference: str, *, expected_repository: str) -> int:
    """Return the issue number for a bare number or a github.com issue URL.

    URLs must point at the bound repository; anything else is rejected before
    any network access.
    """
    candidate = reference.strip()
    if candidate.isascii() and candidate.isdigit() and int(candidate) > 0:
        return int(candidate)
    match = _ISSUE_URL.match(candidate)
    if match is None:
        raise IssueLinkError(
            "Provide a GitHub issue number or an https://github.com/owner/name/issues/N URL."
        )
    referenced = f"{match.group('owner')}/{match.group('name')}"
    if referenced.lower() != expected_repository.lower():
        raise IssueLinkError(
            f"The issue belongs to {referenced}, not the configured {expected_repository}."
        )
    return int(match.group("number"))


def resolve_issue_link(
    client: GitHubAppClient,
    *,
    installation_token: str,
    expected_repository: str,
    expected_repository_id: str,
    reference: str,
) -> EngineeringIssueSnapshot:
    """Fetch and validate an existing issue for linking.

    Rejects pull requests (GitHub issue endpoints also return PRs) and issues
    outside the configured repository.
    """
    owner, _, name = expected_repository.partition("/")
    number = parse_issue_reference(reference, expected_repository=expected_repository)
    try:
        issue = client.get_issue(
            installation_token=installation_token, owner=owner, name=name, number=number
        )
    except GitHubAPIError as error:
        if error.status_code in {301, 404, 410}:
            raise IssueLinkError(
                f"Issue #{number} was not found in {expected_repository}."
            ) from error
        raise
    if "pull_request" in issue:
        raise IssueLinkError("Pull requests cannot be linked as issues.")
    snapshot = parse_issue_payload(issue, error=IssueLinkError)
    if snapshot.repository_id != expected_repository_id:
        raise IssueLinkError("The issue belongs to a different repository identity.")
    if snapshot.number != number:
        raise IssueLinkError("GitHub returned a different issue number.")
    return snapshot
