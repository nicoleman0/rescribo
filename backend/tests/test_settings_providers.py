"""Provider settings contracts with mocked SDK/API clients."""

from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from connections.credentials import decrypt
from connections.errors import SetupError
from integrations.github_app.settings import check_github, github_setup
from integrations.slack.client import revoke_token
from integrations.slack.errors import ChannelRejected
from integrations.slack.policy import REQUIRED_BOT_SCOPES
from integrations.slack.settings import channel_details, channel_options, slack_setup


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
        client.get_repository_installation.return_value["permissions"]["contents"] = "write"
        with pytest.raises(SetupError, match="Contents read is optional"):
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
        patch("integrations.slack.client.decrypt", return_value="secret"),
        patch("integrations.slack.client.WebClient") as sdk,
    ):
        sdk.return_value.conversations_info.return_value = {
            "channel": {"id": "C1", "is_member": True, flag: True}
        }
        with pytest.raises(ChannelRejected):
            channel_details("encrypted", "C1")


def test_revoke_token_calls_auth_revoke_with_the_decrypted_token() -> None:
    with (
        patch("integrations.slack.client.decrypt", return_value="secret"),
        patch("integrations.slack.client.WebClient") as sdk,
    ):
        revoke_token("encrypted")
    assert sdk.call_args.kwargs["token"] == "secret"
    sdk.return_value.auth_revoke.assert_called_once_with()


def test_channel_options_paginates_sorts_and_marks_external_channels() -> None:
    client = MagicMock()
    client.users_conversations.side_effect = [
        {
            "channels": [
                {"id": "C2", "name": "zeta", "is_ext_shared": True},
                {"id": "C3", "name": "archived", "is_archived": True},
                {"id": "D1", "name": "direct", "is_im": True},
            ],
            "response_metadata": {"next_cursor": "next"},
        },
        {"channels": [{"id": "C1", "name": "alpha"}], "response_metadata": {"next_cursor": ""}},
    ]
    with (
        patch("integrations.slack.client.decrypt", return_value="secret"),
        patch("integrations.slack.client.WebClient", return_value=client),
    ):
        result = channel_options("encrypted")
    assert [item["name"] for item in result["channels"]] == ["alpha", "zeta"]
    assert result["channels"][0]["unavailable_reason"] == ""
    assert result["channels"][1]["unavailable_reason"] == "externally_shared"
    assert result["truncated"] is False
    assert client.users_conversations.call_args_list[0].kwargs == {
        "types": "public_channel,private_channel",
        "exclude_archived": True,
        "limit": 200,
        "cursor": "",
    }
    assert client.users_conversations.call_args_list[1].kwargs["cursor"] == "next"


def test_member_channels_caps_at_one_thousand() -> None:
    from integrations.slack.client import member_channels

    client = MagicMock()
    client.users_conversations.return_value = {
        "channels": [{"id": f"C{i}", "name": str(i)} for i in range(200)],
        "response_metadata": {"next_cursor": "more"},
    }
    with (
        patch("integrations.slack.client.decrypt", return_value="secret"),
        patch("integrations.slack.client.WebClient", return_value=client),
    ):
        channels, truncated = member_channels("encrypted")
    assert len(channels) == 1000
    assert truncated is True
    assert client.users_conversations.call_count == 5


def test_channel_options_maps_slack_rate_limit() -> None:
    from slack_sdk.errors import SlackApiError

    response = MagicMock()
    response.status_code = 429
    error = SlackApiError(message="rate_limited", response=response)
    with patch("integrations.slack.settings.member_channels", side_effect=error):
        with pytest.raises(SetupError) as raised:
            channel_options("encrypted")
    assert raised.value.code == "slack_rate_limited"


@override_settings(RESCRIBO_SLACK_FAKE_DELIVERY=True)
def test_fake_channel_directory_supports_picker_and_submit_without_decrypt() -> None:
    with patch("integrations.slack.client.decrypt", side_effect=AssertionError("decrypted")):
        result = channel_options("fake")
        assert len(result["channels"]) == 3
        assert channel_details("fake", "C0E2EPUBLIC")["name"] == "support-requests"
        with pytest.raises(ChannelRejected):
            channel_details("fake", "C0E2ESHARED")
        with pytest.raises(Exception, match="channel_not_found"):
            channel_details("fake", "CUNKNOWN")
