import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any


class InvalidOAuthState(ValueError):
    """OAuth state is unknown, expired, reused, or bound to another workspace."""


class OAuthStateStore:
    def __init__(self, directory: Path, *, lifetime_seconds: int = 600) -> None:
        self._directory = directory
        self._lifetime_seconds = lifetime_seconds

    @staticmethod
    def _digest(state: str) -> str:
        return hashlib.sha256(state.encode()).hexdigest()

    def _path(self, state: str) -> Path:
        return self._directory / f"{self._digest(state)}.json"

    def create(self, workspace_id: str, repository: str, *, now: int | None = None) -> str:
        created_at = int(time.time()) if now is None else now
        state = secrets.token_urlsafe(32)
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(state)
        payload = {
            "workspace_id": workspace_id,
            "repository": repository,
            "expires_at": created_at + self._lifetime_seconds,
            "consumed": False,
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)
        return state

    def consume(self, state: str, workspace_id: str, *, now: int | None = None) -> str:
        current_time = int(time.time()) if now is None else now
        path = self._path(state)
        try:
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise InvalidOAuthState("OAuth state is invalid.") from error
        if payload.get("workspace_id") != workspace_id:
            raise InvalidOAuthState("OAuth state belongs to another workspace.")
        if payload.get("consumed") is not False:
            raise InvalidOAuthState("OAuth state has already been used.")
        expires_at = payload.get("expires_at")
        if not isinstance(expires_at, int) or current_time > expires_at:
            raise InvalidOAuthState("OAuth state has expired.")
        payload["consumed"] = True
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload), encoding="utf-8")
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
        repository = payload.get("repository")
        if not isinstance(repository, str) or not repository:
            raise InvalidOAuthState("OAuth state has no repository binding.")
        return repository
