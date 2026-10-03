"""Bot-token Slack calls used by capture. Callers handle `SlackApiError`."""

from typing import Any

from django.conf import settings
from slack_sdk import WebClient

from connections.credentials import decrypt
from integrations.slack.policy import SlackChannel, validate_channel

# Slack's acknowledgement deadline is three seconds, so interactive calls must fail fast.
INTERACTIVE_TIMEOUT = 2


def bot_client(credential: str, *, timeout: int = 10) -> WebClient:
    return WebClient(token=decrypt(credential), timeout=timeout)


def eligible_channel(credential: str, channel_id: str, *, timeout: int = 10) -> SlackChannel:
    """Fetch current channel state and raise `ChannelRejected` when it is not eligible."""
    response = bot_client(credential, timeout=timeout).conversations_info(channel=channel_id)
    return validate_channel(response["channel"])


def open_view(credential: str, *, trigger_id: str, view: dict[str, Any]) -> None:
    bot_client(credential, timeout=INTERACTIVE_TIMEOUT).views_open(trigger_id=trigger_id, view=view)


def message_permalink(credential: str, *, channel_id: str, message_ts: str) -> str:
    response = bot_client(credential).chat_getPermalink(channel=channel_id, message_ts=message_ts)
    permalink = response.get("permalink")
    if not isinstance(permalink, str) or not permalink:
        raise ValueError("Slack returned no permalink")
    return permalink


def _delivery_client(credential: str) -> Any:
    if settings.RESCRIBO_SLACK_FAKE_DELIVERY:
        from integrations.slack.fake_delivery import fake_delivery_client

        return fake_delivery_client()
    return bot_client(credential)


def _message_creation_client(credential: str) -> Any:
    if settings.RESCRIBO_SLACK_FAKE_DELIVERY:
        from integrations.slack.fake_delivery import fake_delivery_client

        return fake_delivery_client()
    # A lost response after chat.postMessage can mean Slack accepted the message.
    # Retrying here could create a duplicate customer notification.
    return WebClient(token=decrypt(credential), timeout=10, retry_handlers=[])


def conversations_open(credential: str, *, users: str) -> Any:
    return _delivery_client(credential).conversations_open(users=users)


def chat_post_message(
    credential: str, *, channel: str, text: str, blocks: list[dict[str, Any]]
) -> Any:
    return _message_creation_client(credential).chat_postMessage(
        channel=channel, text=text, blocks=blocks
    )


def chat_update(
    credential: str,
    *,
    channel: str,
    ts: str,
    text: str,
    blocks: list[dict[str, Any]],
) -> Any:
    return _delivery_client(credential).chat_update(
        channel=channel, ts=ts, text=text, blocks=blocks
    )
