import re
from dataclasses import asdict, dataclass
from typing import Any

from integrations.github_app.client import GitHubAPIError, GitHubAppClient


class IssueLinkError(ValueError):
    """The reference cannot be linked to the configured repository."""


@dataclass(frozen=True)
class LinkedIssue:
    number: int
    title: str
    state: str
    state_reason: str | None
    url: str
    updated_at: str
    repository: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    reference: str,
) -> LinkedIssue:
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
    repository_url = issue.get("repository_url")
    if isinstance(repository_url, str) and not repository_url.lower().endswith(
        f"/repos/{expected_repository.lower()}"
    ):
        raise IssueLinkError("The fetched issue does not belong to the configured repository.")
    title = issue.get("title")
    state = issue.get("state")
    updated_at = issue.get("updated_at")
    url = issue.get("html_url")
    state_reason = issue.get("state_reason")
    if not (
        isinstance(title, str)
        and isinstance(state, str)
        and isinstance(updated_at, str)
        and isinstance(url, str)
    ):
        raise IssueLinkError("GitHub returned an incomplete issue payload.")
    if state_reason is not None and not isinstance(state_reason, str):
        raise IssueLinkError("GitHub returned an invalid issue state_reason.")
    return LinkedIssue(
        number=number,
        title=title,
        state=state,
        state_reason=state_reason,
        url=url,
        updated_at=updated_at,
        repository=expected_repository,
    )
