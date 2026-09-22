"""Workspace permissions recheck membership on every scoped request."""

from typing import Any, cast

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from accounts.models import Membership, User
from accounts.services import resolve_active_membership


class IsWorkspaceMember(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        try:
            view.membership = resolve_active_membership(
                user=cast(User, request.user), workspace_id=view.kwargs["workspace_id"]
            )
        except LookupError as error:
            raise NotFound("Not found.") from error
        return True


class IsWorkspaceOwner(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        # Resolve membership first so a foreign workspace remains a 404.
        return view.membership.role == Membership.Role.OWNER
