"""Operator-key encryption for stored provider credentials."""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from connections.errors import SetupError


def cipher() -> Fernet:
    try:
        return Fernet(settings.RESCRIBO_CREDENTIAL_KEY.encode())
    except (ValueError, AttributeError) as error:
        raise SetupError(
            "operator_setup", "Ask the operator to configure the credential encryption key."
        ) from error


def decrypt(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken as error:
        raise SetupError(
            "credential_unavailable",
            "Ask the operator to restore the encryption key, then reconnect.",
        ) from error
