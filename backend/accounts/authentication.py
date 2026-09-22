"""Session authentication with an explicit 401 challenge."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import SessionAuthentication


class Session401Authentication(SessionAuthentication):
    def authenticate_header(self, request: object) -> str:
        return "Session"


class SessionCookieScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.Session401Authentication"
    name = "sessionCookie"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
