"""Bot-token Slack calls. Callers handle `SlackApiError`."""

from slack_sdk import WebClient

from connections.credentials import decrypt


def bot_client(credential: str, *, timeout: int = 10) -> WebClient:
    return WebClient(token=decrypt(credential), timeout=timeout)
