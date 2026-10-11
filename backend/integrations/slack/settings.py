"""Slack setup and allowed-channel verification."""

from typing import Any

from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from connections.credentials import cipher
from connections.errors import SetupError
from integrations.slack.client import bot_client, channel_info, member_channels
from integrations.slack.policy import (
    REQUIRED_BOT_SCOPES,
    SlackChannel,
    unavailable_reason,
    validate_channel,
)


def slack_setup(code: str, redirect_uri: str) -> dict[str, Any]:
    result = WebClient(timeout=10).oauth_v2_access(
        client_id=settings.RESCRIBO_SLACK_CLIENT_ID,
        client_secret=settings.RESCRIBO_SLACK_CLIENT_SECRET,
        code=code,
        redirect_uri=redirect_uri,
    )
    scopes = sorted(set(result.get("scope", "").split(",")))
    if set(scopes) != REQUIRED_BOT_SCOPES or result.get("app_id") != settings.RESCRIBO_SLACK_APP_ID:
        raise SetupError(
            "missing_scopes",
            "Check the Slack App identity and grant the required scopes, then reconnect.",
        )
    team = result["team"]
    token = result["access_token"]
    verified = WebClient(token=token, timeout=10).auth_test()
    if verified.get("team_id") != team["id"]:
        raise SetupError(
            "identity_mismatch",
            "Slack returned a different workspace. Start connection setup again.",
        )
    return dict(
        external_id=team["id"],
        identity=team["name"],
        scopes=scopes,
        credential=cipher().encrypt(token.encode()).decode(),
    )


def channel_details(credential: str, channel_id: str) -> dict[str, Any]:
    data = channel_info(credential, channel_id)
    validated = validate_channel(data)
    return dict(
        channel_id=validated.channel_id,
        name=data.get("name", validated.channel_id),
        is_private=validated.is_private,
    )


def channel_options(credential: str) -> dict[str, Any]:
    try:
        channels, truncated = member_channels(credential)
    except SlackApiError as error:
        if getattr(error.response, "status_code", None) == 429:
            raise SetupError(
                "slack_rate_limited", "Slack asked us to wait. Try again in a minute."
            ) from error
        raise
    options: list[dict[str, Any]] = []
    for data in channels:
        channel = SlackChannel.from_api(data)
        reason = unavailable_reason(channel)
        if reason and reason != "externally_shared":
            continue
        name = data.get("name")
        if not isinstance(name, str) or not name:
            name = channel.channel_id
        options.append(
            {
                "channel_id": channel.channel_id,
                "name": name,
                "is_private": channel.is_private,
                "unavailable_reason": reason or "",
            }
        )
    options.sort(key=lambda option: option["name"].casefold())
    return {"channels": options, "truncated": truncated}


def check_slack(credential: str, external_id: str) -> None:
    response = bot_client(credential).auth_test()
    if response.get("team_id") != external_id:
        raise SetupError("identity_mismatch", "Reconnect Slack to verify the workspace identity.")
    granted = set(response.headers.get("x-oauth-scopes", "").split(","))
    if not REQUIRED_BOT_SCOPES.issubset(granted):
        raise SetupError("missing_scopes", "Grant the required Slack scopes and reconnect.")
