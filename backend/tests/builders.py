"""Small explicit builders for account tests."""

from typing import Any

from accounts.models import Membership, User, Workspace


def make_user(**overrides: Any) -> User:
    values = {"email": "member@example.test", "full_name": "Test Member"}
    values.update(overrides)
    return User.objects.create_user(**values)


def make_workspace(**overrides: Any) -> Workspace:
    values = {"name": "Example", "slug": "example"}
    values.update(overrides)
    return Workspace.objects.create(**values)


def make_membership(**overrides: Any) -> Membership:
    user = overrides.pop("user", None) or make_user()
    workspace = overrides.pop("workspace", None) or make_workspace()
    values = {"user": user, "workspace": workspace}
    values.update(overrides)
    return Membership.objects.create(**values)
