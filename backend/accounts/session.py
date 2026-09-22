"""Session generation binding and global session revocation."""

from django.contrib import auth
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

from accounts.models import User

SESSION_GENERATION_KEY = "accounts.session_generation"


def bind_session_generation(*, request: HttpRequest, user: User) -> None:
    request.session[SESSION_GENERATION_KEY] = user.session_generation


class SessionGenerationMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest) -> None:
        user = request.user
        if (
            user.is_authenticated
            and request.session.get(SESSION_GENERATION_KEY) != user.session_generation
        ):
            auth.logout(request)

    def process_response(self, request: HttpRequest, response: object) -> object:
        user = getattr(request, "user", None)
        if (
            user is not None
            and user.is_authenticated
            and SESSION_GENERATION_KEY not in request.session
        ):
            bind_session_generation(request=request, user=user)
        return response
