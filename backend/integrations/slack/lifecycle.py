"""Slack lifecycle payloads that disable a connection on verified removal."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AppUninstalled:
    team_id: str
    app_id: str | None


def parse_app_uninstalled(payload: Mapping[str, Any]) -> AppUninstalled:
    if payload.get("type") != "event_callback":
        raise ValueError("Slack lifecycle payload is not an event callback")
    event = payload.get("event")
    if not isinstance(event, Mapping) or event.get("type") != "app_uninstalled":
        raise ValueError("Slack lifecycle payload is not app_uninstalled")
    team_id = payload.get("team_id")
    if not isinstance(team_id, str) or not team_id:
        raise ValueError("Slack app_uninstalled payload has no team id")
    app_id = payload.get("api_app_id")
    return AppUninstalled(team_id=team_id, app_id=app_id if isinstance(app_id, str) else None)
