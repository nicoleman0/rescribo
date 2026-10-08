from dataclasses import dataclass
from typing import Any

from integrations.github_app.client import GitHubAPIError, GitHubAppClient


class ReleaseNotFound(ValueError):
    pass


class ReleaseAccessMissing(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseSnapshot:
    external_id: str
    tag_name: str
    name: str
    url: str
    published_at: str
    prerelease: bool


def parse_release_payload(payload: dict[str, Any], *, repository_name: str) -> ReleaseSnapshot:
    external_id = payload.get("id")
    tag = payload.get("tag_name")
    published = payload.get("published_at")
    url = payload.get("html_url")
    prefix = f"https://github.com/{repository_name}/releases/tag/".casefold()
    if (
        not isinstance(external_id, int)
        or external_id <= 0
        or not isinstance(tag, str)
        or not tag.strip()
        or payload.get("draft") is True
        or not isinstance(published, str)
        or not published
        or not isinstance(url, str)
        or not url.casefold().startswith(prefix)
    ):
        raise ValueError("GitHub returned an invalid published release.")
    name = payload.get("name")
    return ReleaseSnapshot(
        str(external_id),
        tag,
        name if isinstance(name, str) and name else tag,
        url,
        published,
        payload.get("prerelease") is True,
    )


def list_releases(
    client: GitHubAppClient, *, installation_token: str, repository_name: str, page: int
) -> tuple[list[ReleaseSnapshot], bool]:
    owner, name = repository_name.split("/", 1)
    rows, has_next = client.list_releases(
        installation_token=installation_token, owner=owner, name=name, page=page
    )
    result = []
    for row in rows:
        if row.get("draft") is True:
            continue
        result.append(parse_release_payload(row, repository_name=repository_name))
    return result, has_next


def get_release(
    client: GitHubAppClient, *, installation_token: str, repository_name: str, release_id: int
) -> ReleaseSnapshot:
    owner, name = repository_name.split("/", 1)
    try:
        payload = client.get_release(
            installation_token=installation_token, owner=owner, name=name, release_id=release_id
        )
    except GitHubAPIError as error:
        if error.status_code == 404:
            raise ReleaseNotFound() from error
        raise
    return parse_release_payload(payload, repository_name=repository_name)
