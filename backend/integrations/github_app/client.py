import base64
import json
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class GitHubAPIError(RuntimeError):
    """A safe GitHub API error which does not include response content."""

    def __init__(
        self,
        operation: str,
        status_code: int,
        *,
        retry_after_seconds: int | None = None,
        rate_limited: bool = False,
    ) -> None:
        super().__init__(f"GitHub {operation} failed with HTTP {status_code}.")
        self.operation = operation
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.rate_limited = rate_limited


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def create_app_jwt(app_id: str, private_key: bytes, *, now: int | None = None) -> str:
    issued_at = int(time.time()) if now is None else now
    header = _base64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _base64url(
        json.dumps({"iat": issued_at - 60, "exp": issued_at + 540, "iss": app_id}).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    key = serialization.load_pem_private_key(private_key, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("GitHub App private key must be an RSA private key.")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_base64url(signature)}"


class GitHubAppClient:
    def __init__(self, http: httpx.Client, *, app_id: str, private_key: bytes) -> None:
        self._http = http
        self._app_id = app_id
        self._private_key = private_key

    def _request_response(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        operation: str,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> httpx.Response:
        auth_token = token or create_app_jwt(self._app_id, self._private_key)
        response = self._http.request(
            method,
            path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {auth_token}",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            json=json_body,
            params=params,
        )
        if response.is_error or response.is_redirect:
            raw_retry_after = response.headers.get("Retry-After")
            rate_limited = response.status_code == 429 or (
                response.status_code == 403
                and (
                    response.headers.get("X-RateLimit-Remaining") == "0"
                    or raw_retry_after is not None
                )
            )
            retry_after: int | None = None
            if rate_limited:
                if raw_retry_after and raw_retry_after.isdigit():
                    retry_after = int(raw_retry_after)
                elif response.headers.get("X-RateLimit-Reset", "").isdigit():
                    reset_at = int(response.headers["X-RateLimit-Reset"])
                    retry_after = max(0, reset_at - int(datetime.now(UTC).timestamp()))
            raise GitHubAPIError(
                operation,
                response.status_code,
                retry_after_seconds=retry_after,
                rate_limited=rate_limited,
            )
        return response

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        operation: str,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
    ) -> dict[str, Any]:
        response = self._request_response(
            method, path, token=token, operation=operation, json_body=json_body, params=params
        )
        if response.status_code == 204 or not response.content:
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"GitHub {operation} returned an unexpected response shape.")
        return data

    def exchange_user_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
    ) -> str:
        response = self._http.request(
            "POST",
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if response.is_error:
            raise GitHubAPIError("user authorisation exchange", response.status_code)
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("GitHub user authorisation returned an unexpected response shape.")
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("GitHub did not return a user access token.")
        return token

    def get_repository_installation(self, *, owner: str, name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}/installation",
            operation="repository installation lookup",
        )

    def get_user_installation_repositories(
        self, *, user_token: str, installation_id: int, page: int = 1
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/user/installations/{installation_id}/repositories",
            token=user_token,
            operation="user installation access check",
            params={"per_page": 100, "page": page},
        )

    def create_installation_token(
        self,
        *,
        installation_id: int,
        repository: str | None = None,
        repository_id: str | None = None,
    ) -> tuple[str, str]:
        if (repository is None) == (repository_id is None):
            raise ValueError("Supply exactly one selected repository name or ID.")
        selection: dict[str, Any]
        if repository_id is not None and repository_id.isdigit() and int(repository_id) > 0:
            selection = {"repository_ids": [int(repository_id)]}
        elif repository is not None:
            selection = {"repositories": [repository]}
        else:
            raise ValueError("A positive stable GitHub repository ID is required.")
        data = self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            operation="installation token creation",
            json_body={
                **selection,
                "permissions": {"issues": "write", "metadata": "read"},
            },
        )
        token = data.get("token")
        expires_at = data.get("expires_at")
        if not isinstance(token, str) or not isinstance(expires_at, str):
            raise RuntimeError("GitHub returned an invalid installation token response.")
        return token, expires_at

    def get_repository(self, *, installation_token: str, owner: str, name: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}",
            token=installation_token,
            operation="selected repository lookup",
        )

    def get_repository_by_id(
        self, *, installation_token: str, repository_id: str
    ) -> dict[str, Any]:
        if not repository_id.isdigit() or int(repository_id) <= 0:
            raise ValueError("A stable GitHub repository ID is required.")
        return self._request(
            "GET",
            f"/repositories/{repository_id}",
            token=installation_token,
            operation="repository identity lookup",
        )

    def create_issue(
        self,
        *,
        installation_token: str,
        owner: str,
        name: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/repos/{owner}/{name}/issues",
            token=installation_token,
            operation="issue creation",
            json_body={"title": title, "body": body},
        )

    def get_issue(
        self, *, installation_token: str, owner: str, name: str, number: int
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/repos/{owner}/{name}/issues/{number}",
            token=installation_token,
            operation="issue lookup",
        )

    def list_issues(
        self, *, installation_token: str, owner: str, name: str, page: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return one repository issues page and whether another page may exist."""
        response = self._request_response(
            "GET",
            f"/repos/{owner}/{name}/issues",
            token=installation_token,
            operation="issue listing",
            params={"state": "all", "per_page": 100, "page": page},
        )
        data = response.json()
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise RuntimeError("GitHub returned an invalid issue list.")
        link = response.headers.get("Link", "")
        has_next = any('rel="next"' in part for part in link.split(","))
        return data, has_next

    def update_issue_state(
        self, *, installation_token: str, owner: str, name: str, number: int, state: str
    ) -> dict[str, Any]:
        if state not in {"open", "closed"}:
            raise ValueError("Issue state must be open or closed.")
        return self._request(
            "PATCH",
            f"/repos/{owner}/{name}/issues/{number}",
            token=installation_token,
            operation="issue state update",
            json_body={"state": state},
        )

    def delete_installation(self, *, installation_id: int) -> None:
        self._request(
            "DELETE",
            f"/app/installations/{installation_id}",
            operation="installation deletion",
        )

    def revoke_installation_token(self, *, token: str) -> None:
        self._request("DELETE", "/installation/token", token=token, operation="token revocation")
