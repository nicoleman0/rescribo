import base64
import json
import time
from collections.abc import Mapping
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class GitHubAPIError(RuntimeError):
    """A safe GitHub API error which does not include response content."""

    def __init__(self, operation: str, status_code: int) -> None:
        super().__init__(f"GitHub {operation} failed with HTTP {status_code}.")
        self.status_code = status_code


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
        if response.is_error:
            raise GitHubAPIError(operation, response.status_code)
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
        self, *, user_token: str, installation_id: int
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/user/installations/{installation_id}/repositories",
            token=user_token,
            operation="user installation access check",
            params={"per_page": 100},
        )

    def create_installation_token(
        self, *, installation_id: int, repository: str
    ) -> tuple[str, str]:
        data = self._request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
            operation="installation token creation",
            json_body={
                "repositories": [repository],
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
