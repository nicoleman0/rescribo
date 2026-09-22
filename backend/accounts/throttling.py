"""Redis-backed limits for login and one-use token endpoints."""

import hashlib

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class LoginIdentityThrottle(SimpleRateThrottle):
    scope = "login_identity"

    def get_cache_key(self, request: Request, view: APIView) -> str:
        payload = request.data
        identity = (
            str(payload.get("email", "") if isinstance(payload, dict) else "").strip().lower()
        )
        return self.cache_format % {
            "scope": self.scope,
            "ident": hashlib.sha256(identity.encode()).hexdigest(),
        }


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
