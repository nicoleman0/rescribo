from typing import Any

from django.apps import AppConfig
from django.conf import settings
from django.core import checks


class ConnectionsConfig(AppConfig):
    name = "connections"

    def ready(self) -> None:
        checks.register(check_credential_key)


def check_credential_key(**kwargs: Any) -> list[checks.CheckMessage]:
    """Fail at deploy, not at the first Slack connect, when production has no usable key."""
    from connections.credentials import cipher
    from connections.errors import SetupError

    # Local setups without Slack run fine without a key.
    if settings.DEBUG:
        return []
    try:
        cipher()
    except SetupError:
        return [
            checks.Error(
                "RESCRIBO_CREDENTIAL_KEY is missing or not a valid Fernet key.",
                hint="Generate one as described in docs/DEPLOYMENT.md.",
                id="connections.E001",
            )
        ]
    return []
