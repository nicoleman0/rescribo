"""Scoped access to a selected repository, identified by its stable GitHub ID."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from integrations.github_app.client import (
    INSTALLATION_TOKEN_OPERATION,
    GitHubAPIError,
    GitHubAppClient,
)
from integrations.github_app.issues import IssueLinkError
from integrations.github_app.permissions import ISSUE_PERMISSIONS, RELEASE_PERMISSIONS
from integrations.github_app.releases import ReleaseAccessMissing

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 10
# Four requests, each with connect/read/write/pool timeouts, plus persistence time.
OPERATION_LEASE_SECONDS = 4 * 4 * REQUEST_TIMEOUT_SECONDS + 30


@contextmanager
def selected_repository(
    client: GitHubAppClient,
    *,
    installation_id: str,
    repository_id: str,
    permissions: Mapping[str, str] = ISSUE_PERMISSIONS,
) -> Iterator[tuple[str, str]]:
    try:
        token, _ = client.create_installation_token(
            installation_id=int(installation_id),
            repository_id=repository_id,
            permissions=permissions,
        )
    except GitHubAPIError as error:
        if (
            permissions == RELEASE_PERMISSIONS
            and error.operation == INSTALLATION_TOKEN_OPERATION
            and error.status_code == 422
        ):
            raise ReleaseAccessMissing() from error
        raise
    try:
        repository = client.get_repository_by_id(
            installation_token=token, repository_id=repository_id
        )
        canonical = repository.get("full_name")
        if (
            str(repository.get("id")) != repository_id
            or not isinstance(canonical, str)
            or canonical.count("/") != 1
            or not all(canonical.split("/"))
        ):
            raise IssueLinkError("The selected repository identity changed.")
        yield token, canonical
    finally:
        try:
            client.revoke_installation_token(token=token)
        except Exception:
            # Revocation must not hide the outcome of a completed write.
            logger.warning("GitHub installation token revocation failed")
