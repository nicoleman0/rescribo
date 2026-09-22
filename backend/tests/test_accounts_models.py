import pytest
from builders import make_membership
from django.db import IntegrityError, transaction

from accounts.models import Invitation, Membership, User

pytestmark = pytest.mark.django_db


def test_email_is_stored_lowercase() -> None:
    user = User.objects.create_user(email="Owner@Example.Test", full_name="Owner", password="ok")
    assert user.email == "owner@example.test"
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(email="OWNER@example.test", full_name="Duplicate", password="ok")


def test_membership_unique_workspace_user() -> None:
    row = make_membership()
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(workspace=row.workspace, user=row.user)


def test_membership_active_must_match_revocation() -> None:
    row = make_membership()
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.filter(pk=row.pk).update(is_active=False)


def test_one_pending_invitation_per_workspace_and_email() -> None:
    actor = make_membership(role=Membership.Role.OWNER)
    Invitation.objects.create(
        workspace=actor.workspace,
        email="invite@example.test",
        role="member",
        token_digest="a" * 64,
        created_by_membership=actor,
        expires_at=actor.created_at,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(
            workspace=actor.workspace,
            email="invite@example.test",
            role="member",
            token_digest="b" * 64,
            created_by_membership=actor,
            expires_at=actor.created_at,
        )
