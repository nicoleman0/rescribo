"""Scoped access to a selected repository, identified by its stable GitHub ID."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from integrations.github_app.client import GitHubAppClient
from integrations.github_app.issues import IssueLinkError

logger = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 10
# Four requests, each with connect/read/write/pool timeouts, plus persistence time.
OPERATION_LEASE_SECONDS = 4 * 4 * REQUEST_TIMEOUT_SECONDS + 30


@contextmanager
def selected_repository(
    client: GitHubAppClient, *, installation_id: str, repository_id: str
) -> Iterator[tuple[str, str]]:
    token, _ = client.create_installation_token(
        installation_id=int(installation_id), repository_id=repository_id
    )
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
