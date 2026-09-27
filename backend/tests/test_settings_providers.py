"""Provider settings contracts with mocked SDK/API clients."""

from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from connections.credentials import decrypt
from connections.errors import SetupError
from integrations.github_app.settings import check_github, github_setup
from integrations.slack.errors import ChannelRejected
from integrations.slack.policy import REQUIRED_BOT_SCOPES
from integrations.slack.settings import channel_details, slack_setup


@override_settings(
    RESCRIBO_SLACK_APP_ID="A1", RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode()
)
def test_slack_verifies_identity_scopes_and_encrypts_token() -> None:
    with patch("integrations.slack.settings.WebClient") as sdk:
        sdk.return_value.oauth_v2_access.return_value = {
            "scope": ",".join(REQUIRED_BOT_SCOPES),
            "app_id": "A1",
            "team": {"id": "T1", "name": "Team"},
            "access_token": "secret",
        }
        sdk.return_value.auth_test.return_value = {"team_id": "T1"}
        result = slack_setup("code", "https://example.test/callback")
        assert result["external_id"] == "T1"
        assert decrypt(result["credential"]) == "secret"
        sdk.return_value.auth_test.return_value = {"team_id": "T2"}
        with pytest.raises(SetupError, match="different workspace"):
            slack_setup("code", "https://example.test/callback")
        sdk.return_value.oauth_v2_access.return_value["scope"] = "commands"
        with pytest.raises(SetupError, match="scopes"):
            slack_setup("code", "https://example.test/callback")


def github_mock() -> MagicMock:
    client = MagicMock()
    client.exchange_user_code.return_value = "user-secret"
    client.get_repository_installation.return_value = {
        "id": 123,
        "permissions": {"issues": "write", "metadata": "read"},
        "account": {"login": "org"},
    }
    client.get_user_installation_repositories.return_value = {
        "repositories": [{"id": 7, "full_name": "org/repo"}]
    }
    client.create_installation_token.return_value = ("installation-secret", "expires")
    client.get_repository.return_value = {"id": 7, "full_name": "org/repo", "visibility": "private"}
    return client


def test_github_verifies_user_access_and_revokes_temporary_token() -> None:
    client = github_mock()
    with patch("integrations.github_app.settings.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        result = github_setup("code", "https://example.test/callback", "org/repo")
    assert result["repository_id"] == "7" and result["credential"] == ""
    assert "user-secret" not in str(result) and "installation-secret" not in str(result)
    client.revoke_installation_token.assert_called_once_with(token="installation-secret")


def test_github_denies_unverified_user_and_extra_permissions() -> None:
    client = github_mock()
    with patch("integrations.github_app.settings.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        client.get_user_installation_repositories.return_value = {"repositories": []}
        with pytest.raises(SetupError, match="Authorise"):
            github_setup("code", "callback", "org/repo")
        client.create_installation_token.assert_not_called()
        client.get_repository_installation.return_value["permissions"]["contents"] = "read"
        with pytest.raises(SetupError, match="only Issues"):
            github_setup("code", "callback", "org/repo")


def test_github_access_check_paginates_and_detects_replaced_repository() -> None:
    client = github_mock()
    client.get_user_installation_repositories.side_effect = [
        {"repositories": [{"full_name": "org/other"}] * 100},
        {"repositories": [{"full_name": "org/repo"}]},
    ]
    with patch("integrations.github_app.settings.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        github_setup("code", "callback", "org/repo")
        assert client.get_user_installation_repositories.call_args.kwargs["page"] == 2
        with pytest.raises(SetupError, match="identity changed"):
            check_github("123", "org/repo", "8")
    assert client.revoke_installation_token.call_count == 2


@pytest.mark.parametrize("flag", ["is_im", "is_mpim", "is_archived", "is_ext_shared"])
def test_channel_policy_rejects_ineligible_sources(flag: str) -> None:
    with (
        patch("integrations.slack.settings.decrypt", return_value="secret"),
        patch("integrations.slack.settings.WebClient") as sdk,
    ):
        sdk.return_value.conversations_info.return_value = {
            "channel": {"id": "C1", "is_member": True, flag: True}
        }
        with pytest.raises(ChannelRejected):
            channel_details("encrypted", "C1")
