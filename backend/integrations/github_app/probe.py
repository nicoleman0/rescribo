from dataclasses import asdict, dataclass
from typing import Any, Literal

from integrations.github_app.client import GitHubAPIError, GitHubAppClient


class InvalidInstallation(ValueError):
    """The installation does not satisfy the feasibility check."""


@dataclass(frozen=True)
class ProbeResult:
    connection_status: Literal["active", "suspended", "revoked_or_unavailable"]
    installation_id: int | None
    repository: str | None
    visibility: str | None
    repository_selection: str | None
    permissions: dict[str, str]
    token_expires_at: str | None
    user_access_verified: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstallationProbe:
    REQUIRED_PERMISSIONS = {"issues": "write", "metadata": "read"}

    def __init__(self, client: GitHubAppClient) -> None:
        self._client = client

    def run(
        self,
        *,
        user_token: str,
        expected_repository: str,
        additional_repositories: set[str] | None = None,
    ) -> ProbeResult:
        owner, separator, name = expected_repository.partition("/")
        if not separator or not owner or not name:
            raise InvalidInstallation("Expected repository must use the owner/name form.")
        try:
            installation = self._client.get_repository_installation(owner=owner, name=name)
        except GitHubAPIError as error:
            if error.status_code == 404:
                return ProbeResult(
                    connection_status="revoked_or_unavailable",
                    installation_id=None,
                    repository=expected_repository,
                    visibility=None,
                    repository_selection=None,
                    permissions={},
                    token_expires_at=None,
                    user_access_verified=False,
                )
            raise

        installation_id = installation.get("id")
        if not isinstance(installation_id, int):
            raise InvalidInstallation("GitHub did not return a valid installation ID.")

        permissions = installation.get("permissions")
        if not isinstance(permissions, dict) or permissions != self.REQUIRED_PERMISSIONS:
            raise InvalidInstallation(
                "The GitHub App installation must grant only Issues write and Metadata read."
            )
        selection = installation.get("repository_selection")
        if selection != "selected":
            raise InvalidInstallation("The GitHub App must be limited to selected repositories.")
        if installation.get("suspended_at") is not None:
            return ProbeResult(
                connection_status="suspended",
                installation_id=installation_id,
                repository=expected_repository,
                visibility=None,
                repository_selection=selection,
                permissions=permissions,
                token_expires_at=None,
                user_access_verified=False,
            )

        repositories_response = self._client.get_user_installation_repositories(
            user_token=user_token,
            installation_id=installation_id,
        )
        repositories = repositories_response.get("repositories")
        total_count = repositories_response.get("total_count")
        expected_repositories = {expected_repository, *(additional_repositories or set())}
        if (
            not isinstance(repositories, list)
            or total_count != len(expected_repositories)
            or len(repositories) != len(expected_repositories)
        ):
            raise InvalidInstallation(
                "The authorised installation exposes an unexpected number of repositories."
            )
        repository_names = {
            repository.get("full_name")
            for repository in repositories
            if isinstance(repository, dict)
        }
        if repository_names != expected_repositories:
            raise InvalidInstallation(
                "The authorised installation exposes unexpected repositories."
            )

        installation_token, expires_at = self._client.create_installation_token(
            installation_id=installation_id,
            repository=name,
        )
        selected_repository = self._client.get_repository(
            installation_token=installation_token,
            owner=owner,
            name=name,
        )
        if selected_repository.get("full_name") != expected_repository:
            raise InvalidInstallation("The restricted token returned a different repository.")
        visibility = selected_repository.get("visibility")
        if not isinstance(visibility, str):
            raise InvalidInstallation("GitHub did not return repository visibility.")

        return ProbeResult(
            connection_status="active",
            installation_id=installation_id,
            repository=expected_repository,
            visibility=visibility,
            repository_selection=selection,
            permissions=permissions,
            token_expires_at=expires_at,
            user_access_verified=True,
        )
