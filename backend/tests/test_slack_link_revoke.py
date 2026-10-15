from typing import Any

import pytest
from builders import make_membership, make_user, make_workspace
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from accounts.models import Membership
from accounts.services import LastActiveOwner, accept_invitation, create_invitation
from connections import slack_identity
from connections.models import Connection, ExternalIdentity

pytestmark = pytest.mark.django_db


def link(membership: Membership, *, team: str = "T1", user: str = "U1") -> ExternalIdentity:
    return ExternalIdentity.objects.create(
        workspace_id=membership.workspace_id,
        membership=membership,
        provider=Connection.Provider.SLACK,
        provider_team_id=team,
        provider_user_id=user,
    )


def test_revoked_slack_user_can_link_to_another_member() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    revoked = make_membership(workspace=owner.workspace, user=make_user(email="revoked@test"))
    replacement = make_membership(workspace=owner.workspace, user=make_user(email="next@test"))
    link(revoked)

    slack_identity.revoke_member(actor=owner, target=revoked)
    code = slack_identity.issue_link_code(replacement)
    result = slack_identity.redeem_link_code(
        code.secret, workspace_id=owner.workspace_id, team_id="T1", user_id="U1"
    )

    assert result == replacement
    assert slack_identity.linked_identity(revoked) is None
    assert (
        slack_identity.linked_membership(
            workspace_id=owner.workspace_id, team_id="T1", user_id="U1"
        )
        == replacement
    )


def test_restoring_revoked_member_does_not_restore_slack_identity() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    member = make_membership(workspace=owner.workspace, user=make_user(email="restore@test"))
    link(member)
    slack_identity.revoke_member(actor=owner, target=member)
    _, secret = create_invitation(actor=owner, email=member.user.email, role=Membership.Role.MEMBER)
    accept_invitation(
        secret=secret,
        full_name="Member",
        password="unused",
        authenticated_user=member.user,
    )

    assert slack_identity.linked_identity(member) is None


def test_revoke_preserves_same_slack_user_linked_in_another_workspace() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    target = make_membership(workspace=owner.workspace, user=make_user(email="shared@test"))
    other = make_membership(workspace=make_workspace(slug="other"), user=target.user)
    identity = link(target)
    other_identity = link(other)

    slack_identity.revoke_member(actor=owner, target=target)

    assert not ExternalIdentity.objects.filter(pk=identity.pk).exists()
    assert ExternalIdentity.objects.filter(pk=other_identity.pk).exists()


def test_last_active_owner_revoke_keeps_slack_identity() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    identity = link(owner)

    with pytest.raises(LastActiveOwner):
        slack_identity.revoke_member(actor=owner, target=owner)

    owner.refresh_from_db()
    assert owner.is_active
    assert ExternalIdentity.objects.filter(pk=identity.pk).exists()


def test_unlink_failure_rolls_back_membership_revocation() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    target = make_membership(workspace=owner.workspace, user=make_user(email="fail@test"))
    identity = link(target)

    from unittest.mock import patch

    with patch("connections.slack_identity.unlink", side_effect=RuntimeError("unlink failed")):
        with pytest.raises(RuntimeError, match="unlink failed"):
            slack_identity.revoke_member(actor=owner, target=target)

    target.refresh_from_db()
    assert target.is_active
    assert ExternalIdentity.objects.filter(pk=identity.pk).exists()


def test_active_slack_link_still_rejects_redeeming_another_members_code() -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    linked = make_membership(workspace=owner.workspace, user=make_user(email="linked@test"))
    code_owner = make_membership(workspace=owner.workspace, user=make_user(email="code@test"))
    identity = link(linked)
    code = slack_identity.issue_link_code(code_owner)

    with pytest.raises(slack_identity.LinkCodeRejected, match="already linked to another member"):
        slack_identity.redeem_link_code(
            code.secret, workspace_id=owner.workspace_id, team_id="T1", user_id="U1"
        )

    assert ExternalIdentity.objects.filter(pk=identity.pk).exists()
    assert slack_identity.linked_identity(code_owner) is None


@pytest.mark.django_db(transaction=True)
def test_migration_removes_only_slack_links_for_inactive_memberships() -> None:
    previous = [("accounts", "0003_workspace_is_demo"), ("connections", "0003_slack_capture")]
    current = [*previous, ("connections", "0004_free_revoked_slack_links")]
    executor = MigrationExecutor(connection)
    executor.migrate(previous)
    try:
        apps = MigrationExecutor(connection).loader.project_state(previous).apps
        Workspace = apps.get_model("accounts", "Workspace")
        User = apps.get_model("accounts", "User")
        MembershipModel = apps.get_model("accounts", "Membership")
        Identity = apps.get_model("connections", "ExternalIdentity")
        active_workspace = Workspace.objects.create(name="Active", slug="active")
        revoked_workspace = Workspace.objects.create(name="Revoked", slug="revoked")
        foreign_workspace = Workspace.objects.create(name="Foreign", slug="foreign")

        def create_link(workspace: Any, email: str, active: bool) -> Any:
            user = User.objects.create(email=email, password="!")
            membership = MembershipModel.objects.create(
                workspace=workspace,
                user=user,
                is_active=active,
                revoked_at=None if active else timezone.now(),
            )
            identity = Identity.objects.create(
                workspace=workspace,
                membership=membership,
                provider="slack",
                provider_team_id="T1",
                provider_user_id=email,
            )
            return identity.pk

        keep = create_link(active_workspace, "active@test", True)
        create_link(revoked_workspace, "revoked@test", False)
        create_link(foreign_workspace, "foreign@test", False)
        MigrationExecutor(connection).migrate(current)
        migrated = MigrationExecutor(connection).loader.project_state(current).apps
        assert list(
            migrated.get_model("connections", "ExternalIdentity").objects.values_list(
                "pk", flat=True
            )
        ) == [keep]
    finally:
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
