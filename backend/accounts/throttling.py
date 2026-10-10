"""Redis-backed limits for login and one-use token endpoints."""

import hashlib

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from accounts.services import invited_account_email


class LoginIdentityThrottle(SimpleRateThrottle):
    scope = "login_identity"

    def identity_key(self, email: str) -> str:
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(email.strip().lower().encode()).hexdigest(),
        }

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        payload = request.data
        return self.identity_key(str(payload.get("email", "") if isinstance(payload, dict) else ""))


class InvitationPasswordThrottle(LoginIdentityThrottle):
    """Shares the login limit, so an invitation adds no password guesses for its account."""

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        if request.user.is_authenticated:
            return None
        payload = request.data
        secret = str(payload.get("token", "") if isinstance(payload, dict) else "")
        email = invited_account_email(secret=secret)
        return None if email is None else self.identity_key(email)


class LoginAddressThrottle(SimpleRateThrottle):
    scope = "login_address"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class TokenRedemptionThrottle(LoginAddressThrottle):
    scope = "token_redemption"


class InvitationCreationThrottle(SimpleRateThrottle):
    scope = "invitation_creation"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        return self.cache_format % {"scope": self.scope, "ident": str(request.user.pk)}
