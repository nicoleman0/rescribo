from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Membership, User
from accounts.services import (
    LastActiveOwner,
    bootstrap_workspace_owner,
    change_membership_role,
    create_invitation,
    revoke_membership,
)

pytestmark = pytest.mark.django_db


def test_bootstrap_owner_creates_workspace_and_owner() -> None:
    workspace, user, membership = bootstrap_workspace_owner(
        email="owner@example.test",
        full_name="Owner",
        password="safe",
        workspace_name="Example",
        workspace_slug="example",
    )
    assert membership.workspace == workspace and membership.user == user
    assert membership.role == Membership.Role.OWNER


def test_invitation_secret_is_not_stored_and_expires_after_48_hours() -> None:
    _, _, actor = bootstrap_workspace_owner(
        email="owner@example.test",
        full_name="Owner",
        password="safe",
        workspace_name="Example",
        workspace_slug="example",
    )
    now = timezone.now()
    invitation, secret = create_invitation(
        actor=actor, email="invite@example.test", role=Membership.Role.MEMBER, now=now
    )
    assert invitation.token_digest != secret
    assert invitation.expires_at == now + timedelta(hours=48)
    assert secret not in " ".join(str(value) for value in invitation.__dict__.values())


def test_revoking_last_owner_is_rejected() -> None:
    _, _, owner = bootstrap_workspace_owner(
        email="owner@example.test",
        full_name="Owner",
        password="safe",
        workspace_name="Example",
        workspace_slug="example",
    )
    with pytest.raises(LastActiveOwner):
        revoke_membership(actor=owner, target=owner)


def test_demoting_last_owner_is_rejected() -> None:
    _, _, owner = bootstrap_workspace_owner(
        email="owner@example.test",
        full_name="Owner",
        password="safe",
        workspace_name="Example",
        workspace_slug="example",
    )
    with pytest.raises(LastActiveOwner):
        change_membership_role(actor=owner, target=owner, role=Membership.Role.MEMBER)


def test_revoking_one_of_two_owners_succeeds() -> None:
    _, user, first = bootstrap_workspace_owner(
        email="owner@example.test",
        full_name="Owner",
        password="safe",
        workspace_name="Example",
        workspace_slug="example",
    )
    second_user = User.objects.create_user(
        email="second@example.test", full_name="Second", password="safe"
    )
    second = Membership.objects.create(
        workspace=first.workspace, user=second_user, role=Membership.Role.OWNER
    )
    revoke_membership(actor=first, target=second)
    second.refresh_from_db()
    assert second.is_active is False
    assert user.is_active is True


def test_invitation_preview_does_not_leak_unknown_email() -> None:
    from accounts.services import preview_invitation

    assert preview_invitation(secret="not-a-real-token") == {"status": "unknown"}
