"""Shared Slack API helpers for the opt-in live feasibility check scripts."""

from typing import Any

from slack_sdk import WebClient

from integrations.slack import REQUIRED_BOT_SCOPES


def check_granted_scopes(client: WebClient) -> dict[str, Any]:
    """Assert the token carries exactly the proposed bot scopes, and name the bot."""
    response = client.auth_test()
    header_value = response.headers.get("x-oauth-scopes", "") if response.headers else ""
    # Slack sends the scopes comma-separated, e.g. "commands,chat:write,channels:read".
    granted = {scope.strip() for scope in header_value.split(",") if scope.strip()}
    if granted != REQUIRED_BOT_SCOPES:
        raise SystemExit(
            f"Granted scopes {sorted(granted)} are not exactly the proposed set "
            f"{sorted(REQUIRED_BOT_SCOPES)}."
        )
    data = response.data if isinstance(response.data, dict) else {}
    team_id = data.get("team_id")
    bot_user_id = data.get("user_id")
    print(f"Signed in as bot {bot_user_id} on team {team_id}.")
    print(f"Granted scopes: {', '.join(sorted(granted))}")
    return {"team_id": team_id, "bot_user_id": bot_user_id, "granted_scopes": sorted(granted)}
