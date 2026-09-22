from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Membership, PasswordReset, User, Workspace
from accounts.services import (
    LastActiveOwner,
    bootstrap_owner,
    change_membership_role,
    create_invitation,
    create_password_reset,
    operator_set_owner_password,
    preview_invitation,
    redeem_password_reset,
    revoke_membership,
)
from accounts.tokens import TokenError

pytestmark = pytest.mark.django_db


def test_bootstrap_owner_creates_workspace_and_owner() -> None:
    workspace, user, membership = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
        workspace_name="Example",
        workspace_slug="example",
    )
    assert membership.workspace == workspace and membership.user == user
    assert membership.role == Membership.Role.OWNER


def test_invitation_secret_is_not_stored_and_expires_after_48_hours() -> None:
    _, _, actor = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
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
    _, _, owner = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
        workspace_name="Example",
        workspace_slug="example",
    )
    with pytest.raises(LastActiveOwner):
        revoke_membership(actor=owner, target=owner)


def test_demoting_last_owner_is_rejected() -> None:
    _, _, owner = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
        workspace_name="Example",
        workspace_slug="example",
    )
    with pytest.raises(LastActiveOwner):
        change_membership_role(actor=owner, target=owner, role=Membership.Role.MEMBER)


def test_revoking_one_of_two_owners_succeeds() -> None:
    _, user, first = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
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


def make_owner_and_member() -> tuple[Workspace, Membership, Membership]:
    workspace, _, owner = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password="Strong-password-928!Cedar",
        workspace_name="Example",
        workspace_slug="example",
    )
    user = User.objects.create_user(
        email="member@example.test", full_name="Member", password="Old-password-928!Cedar"
    )
    member = Membership.objects.create(workspace=workspace, user=user, role=Membership.Role.MEMBER)
    return workspace, owner, member


@pytest.mark.parametrize("case", ["owner", "multi", "inactive"])
def test_owner_reset_eligibility_refused(case: str) -> None:
    workspace, owner, member = make_owner_and_member()
    if case == "owner":
        member.role = Membership.Role.OWNER
        member.save(update_fields=["role"])
    elif case == "multi":
        Membership.objects.create(
            workspace=bootstrap_owner(
                email="other-owner@example.test",
                full_name="Other",
                password="Strong-password-928!Cedar",
                workspace_name="Other",
                workspace_slug="other",
            )[0],
            user=member.user,
            role=Membership.Role.MEMBER,
        )
    else:
        member.user.is_active = False
        member.user.save(update_fields=["is_active"])
    with pytest.raises(LookupError):
        create_password_reset(actor=owner, target=member)


@pytest.mark.parametrize("change", ["joined", "revoked"])
def test_owner_reset_redeem_checks_original_membership_and_single_membership(
    change: str,
) -> None:
    workspace, owner, member = make_owner_and_member()
    _, secret = create_password_reset(actor=owner, target=member)
    if change == "joined":
        other_workspace = bootstrap_owner(
            email="other-owner@example.test",
            full_name="Other",
            password="Strong-password-928!Cedar",
            workspace_name="Other",
            workspace_slug="other",
        )[0]
        Membership.objects.create(
            workspace=other_workspace, user=member.user, role=Membership.Role.MEMBER
        )
    else:
        member.is_active = False
        member.revoked_at = timezone.now()
        member.save(update_fields=["is_active", "revoked_at"])
    with pytest.raises(TokenError):
        redeem_password_reset(secret=secret, password="New-password-928!Cedar")


def test_new_reset_redeem_and_operator_password_revoke_older_resets() -> None:
    _, owner, member = make_owner_and_member()
    first, _ = create_password_reset(actor=owner, target=member)
    second, secret2 = create_password_reset(actor=owner, target=member)
    first.refresh_from_db()
    assert first.revoked_at is not None
    older = PasswordReset.objects.create(
        user=member.user,
        workspace=owner.workspace,
        issued_by_membership=owner,
        token_digest="older-unused-reset-digest",
        expires_at=timezone.now() + timedelta(hours=1),
    )
    redeem_password_reset(secret=secret2, password="New-password-928!Cedar")
    second.refresh_from_db()
    older.refresh_from_db()
    assert second.used_at is not None
    assert older.revoked_at is not None
    # Operator recovery revokes any outstanding reset for its owner target.
    _, _ = create_password_reset(actor=owner, target=owner, issued_by_operator=True)
    outstanding, _ = create_password_reset(actor=owner, target=owner, issued_by_operator=True)
    operator_set_owner_password(actor=owner, password="Operator-password-928!Cedar")
    outstanding.refresh_from_db()
    assert outstanding.revoked_at is not None


def test_revoked_invitation_previews_as_unknown() -> None:
    _, _, owner = make_owner_and_member()
    invitation, secret = create_invitation(
        actor=owner, email="invite@example.test", role=Membership.Role.MEMBER
    )
    from accounts.services import revoke_invitation

    revoke_invitation(workspace_id=owner.workspace_id, invitation_id=invitation.pk)
    assert preview_invitation(secret=secret) == {"status": "unknown"}


def test_superseded_invitation_previews_as_unknown() -> None:
    _, _, owner = make_owner_and_member()
    _, old_secret = create_invitation(
        actor=owner, email="same@example.test", role=Membership.Role.MEMBER
    )
    create_invitation(actor=owner, email="same@example.test", role=Membership.Role.MEMBER)
    assert preview_invitation(secret=old_secret) == {"status": "unknown"}
