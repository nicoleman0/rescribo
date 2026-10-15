"""Validate the GitHub App private key setting at startup, before first use."""

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.exceptions import ImproperlyConfigured

MESSAGE = (
    "RESCRIBO_GITHUB_PRIVATE_KEY is set but is not an unencrypted RSA private key in PEM format. "
    "Use the PEM file's text with real newlines, or one line with \\n between the PEM lines. "
    "See docs/SETTINGS.md."
)


def load_private_key(value: str) -> str:
    """Return the key as PEM text, ``""`` when unset, or fail with a clear error.

    Accepts PEM text with real newlines, or one line with literal ``\\n`` and
    ``\\r\\n`` escapes, which env files and Compose produce. Raises
    ``ImproperlyConfigured`` for anything `create_app_jwt` would reject.
    """
    pem = value.replace("\\r\\n", "\n").replace("\\n", "\n").strip()
    if not pem:
        return ""
    try:
        parsed = serialization.load_pem_private_key(pem.encode(), password=None)
    except TypeError, UnsupportedAlgorithm, ValueError:
        raise ImproperlyConfigured(MESSAGE) from None
    if not isinstance(parsed, rsa.RSAPrivateKey):
        raise ImproperlyConfigured(MESSAGE)
    return pem
