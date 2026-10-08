from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest
from django.test import override_settings

from connections.providers import SetupError
from integrations.github_app.permissions import check_installation_permissions
from integrations.github_app.settings import github_setup


@pytest.mark.parametrize(
    "permissions",
    [
        {"issues": "write", "metadata": "read"},
        {"issues": "write", "metadata": "read", "contents": "read"},
    ],
)
def test_accepts_required_permissions_with_optional_contents(permissions: object) -> None:
    assert check_installation_permissions(permissions)


@pytest.mark.parametrize(
    "permissions",
    [
        {"issues": "write", "metadata": "read", "contents": "write"},
        {"metadata": "read"},
        {"issues": "write", "metadata": "read", "pull_requests": "read"},
        None,
    ],
)
def test_rejects_unsupported_permission_sets(permissions: object) -> None:
    assert not check_installation_permissions(permissions)


@pytest.mark.parametrize(("contents", "accepted"), [("read", True), ("write", False)])
@override_settings(RESCRIBO_GITHUB_CLIENT_ID="id", RESCRIBO_GITHUB_CLIENT_SECRET="secret")
def test_github_setup_accepts_only_optional_contents_read(
    monkeypatch: pytest.MonkeyPatch, contents: str, accepted: bool
) -> None:
    client = MagicMock()
    client.exchange_user_code.return_value = "user-token"
    client.get_repository_installation.return_value = {
        "id": 42,
        "permissions": {"issues": "write", "metadata": "read", "contents": contents},
        "suspended_at": None,
        "account": {"login": "owner"},
    }
    client.get_user_installation_repositories.return_value = {
        "repositories": [{"full_name": "owner/repo"}],
    }
    client.create_installation_token.return_value = ("token", "later")
    client.get_repository.return_value = {
        "full_name": "owner/repo",
        "id": 999,
        "visibility": "private",
    }

    @contextmanager
    def factory() -> Any:
        yield client

    monkeypatch.setattr("integrations.github_app.settings.github_client", factory)
    if accepted:
        result = github_setup("code", "https://callback", "owner/repo")
        assert "contents:read" in result["scopes"]
    else:
        with pytest.raises(SetupError, match="Contents read is optional"):
            github_setup("code", "https://callback", "owner/repo")
