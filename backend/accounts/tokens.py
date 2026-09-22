"""One-use account credentials.

Secrets are CSPRNG output, so SHA-256 supports indexed lookup without password
stretching; user-chosen passwords still use Django's password hasher.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

INVITATION_LIFETIME = timedelta(hours=48)
PASSWORD_RESET_LIFETIME = timedelta(hours=24)


@dataclass(frozen=True)
class IssuedToken:
    secret: str
    digest: str
    expires_at: datetime


class TokenError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.messages: list[str] = []
        super().__init__(reason)


def issue_token(*, now: datetime, lifetime: timedelta) -> IssuedToken:
    secret = secrets.token_urlsafe(32)
    return IssuedToken(secret, digest(secret), now + lifetime)


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def matches(*, secret: str, expected_digest: str) -> bool:
    candidate = digest(secret)
    return hmac.compare_digest(candidate, expected_digest)


def check_token(
    *, secret: str, digest: str, expires_at: datetime, used: bool, now: datetime
) -> None:
    if not matches(secret=secret, expected_digest=digest):
        raise TokenError("invalid_token")
    if used:
        raise TokenError("invitation_already_used")
    if now >= expires_at:
        raise TokenError("invitation_expired")
