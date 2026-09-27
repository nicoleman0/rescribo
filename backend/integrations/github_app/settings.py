"""GitHub settings verify user access before binding an installation."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
from django.conf import settings

from connections.errors import SetupError
from integrations.github_app.client import GitHubAppClient


@contextmanager
def github_client() -> Iterator[GitHubAppClient]:
    if not settings.RESCRIBO_GITHUB_PRIVATE_KEY or not settings.RESCRIBO_GITHUB_APP_ID:
        raise SetupError("operator_setup", "Ask the operator to configure the GitHub App.")
    with httpx.Client(base_url="https://api.github.com", timeout=10) as http:
        yield GitHubAppClient(
            http,
            app_id=settings.RESCRIBO_GITHUB_APP_ID,
            private_key=settings.RESCRIBO_GITHUB_PRIVATE_KEY.encode(),
        )


def github_setup(code: str, redirect_uri: str, repository: str) -> dict[str, Any]:
    owner, name = repository.split("/")
    with github_client() as client:
        user_token = client.exchange_user_code(
            client_id=settings.RESCRIBO_GITHUB_CLIENT_ID,
            client_secret=settings.RESCRIBO_GITHUB_CLIENT_SECRET,
            code=code,
            redirect_uri=redirect_uri,
        )
        installation = client.get_repository_installation(owner=owner, name=name)
        permissions = installation.get("permissions", {})
        if installation.get("suspended_at") or permissions != {
            "issues": "write",
            "metadata": "read",
        }:
            raise SetupError(
                "missing_scopes",
                "Unsuspend the installation and grant only Issues write and Metadata read, "
                "then reconnect.",
            )
        # Check this user's repository access, including installations with multiple pages.
        found = False
        for page in range(1, 101):
            data = client.get_user_installation_repositories(
                user_token=user_token, installation_id=installation["id"], page=page
            )
            rows = data.get("repositories", [])
            if any(row.get("full_name", "").lower() == repository.lower() for row in rows):
                found = True
                break
            if len(rows) < 100:
                break
        if not found:
            raise SetupError(
                "repository_access",
                "Authorise a GitHub user with access to the selected installation and repository.",
            )
        token, _ = client.create_installation_token(
            installation_id=installation["id"], repository=name
        )
        try:
            repo = client.get_repository(installation_token=token, owner=owner, name=name)
        finally:
            client.revoke_installation_token(token=token)
        return dict(
            external_id=str(installation["id"]),
            identity=installation["account"]["login"],
            scopes=[f"{k}:{v}" for k, v in sorted(permissions.items())],
            repository=repo["full_name"],
            repository_id=str(repo["id"]),
            visibility=repo["visibility"],
            credential="",
        )


def check_github(external_id: str, repository: str, repository_id: str) -> None:
    owner, name = repository.split("/")
    with github_client() as client:
        token, _ = client.create_installation_token(
            installation_id=int(external_id), repository=name
        )
        try:
            repo = client.get_repository(installation_token=token, owner=owner, name=name)
            if str(repo["id"]) != repository_id:
                raise SetupError(
                    "repository_changed",
                    "Repository identity changed. Select it again and reauthorise GitHub.",
                )
        finally:
            client.revoke_installation_token(token=token)
