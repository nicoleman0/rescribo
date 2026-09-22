import pytest
from builders import make_membership, make_user, make_workspace
from django.core.management import CommandError, call_command
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY

pytestmark = pytest.mark.django_db


def test_login_sets_session_and_invalid_credentials_are_identical(client: Client) -> None:
    user = make_user(password="Strong-pass-482!x")
    workspace = make_workspace()
    Membership.objects.create(user=user, workspace=workspace, role=Membership.Role.OWNER)
    good = client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "Strong-pass-482!x"},
        content_type="application/json",
    )
    assert good.status_code == 200
    assert "sessionid" in client.cookies
    client.post("/api/auth/logout/", {}, content_type="application/json")
    wrong = client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "wrong"},
        content_type="application/json",
    )
    unknown = client.post(
        "/api/auth/login/",
        {"email": "absent@example.test", "password": "wrong"},
        content_type="application/json",
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.content == unknown.content


def test_foreign_workspace_is_hidden_from_member(client: Client) -> None:
    member = make_membership(role=Membership.Role.MEMBER)
    other_workspace = make_workspace(slug="other")
    client.force_login(member.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = member.user.session_generation
    session.save()
    response = client.get(f"/api/workspaces/{other_workspace.pk}/invitations/")
    assert response.status_code == 404
    assert b"other" not in response.content


def test_superuser_without_membership_has_no_product_access(client: Client) -> None:
    user = make_user(email="root@example.test", is_superuser=True, is_staff=True)
    workspace = make_workspace()
    client.force_login(user)
    session = client.session
    session[SESSION_GENERATION_KEY] = user.session_generation
    session.save()
    assert client.get(f"/api/workspaces/{workspace.pk}/invitations/").status_code == 404


def test_non_owner_cannot_list_invitations(client: Client) -> None:
    member = make_membership(role=Membership.Role.MEMBER)
    client.force_login(member.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = member.user.session_generation
    session.save()
    assert client.get(f"/api/workspaces/{member.workspace_id}/invitations/").status_code == 403


def test_last_owner_revoke_is_a_400(client: Client) -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    client.force_login(owner.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = owner.user.session_generation
    session.save()
    response = client.post(
        f"/api/workspaces/{owner.workspace_id}/memberships/{owner.pk}/revoke/",
        {},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "last_active_owner"


def test_last_owner_demotion_is_400_and_member_promotion_works(client: Client) -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    client.force_login(owner.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = owner.user.session_generation
    session.save()
    response = client.post(
        f"/api/workspaces/{owner.workspace_id}/memberships/{owner.pk}/role/",
        {"role": "member"},
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["reason"] == "last_active_owner"
    member_user = make_user(email="promoted@example.test")
    member = make_membership(
        user=member_user, role=Membership.Role.MEMBER, workspace=owner.workspace
    )
    response = client.post(
        f"/api/workspaces/{owner.workspace_id}/memberships/{member.pk}/role/",
        {"role": "owner"},
        content_type="application/json",
    )
    assert response.status_code == 200


@pytest.mark.parametrize("case", ["owner", "multi", "inactive"])
def test_owner_password_reset_ineligible_target_is_hidden_as_404(client: Client, case: str) -> None:
    actor = make_membership(role=Membership.Role.OWNER)
    target = make_membership(
        user=make_user(email="target@example.test"),
        role=Membership.Role.MEMBER,
        workspace=actor.workspace,
    )
    if case == "owner":
        target.role = Membership.Role.OWNER
        target.save(update_fields=["role"])
    elif case == "multi":
        make_membership(
            user=target.user,
            role=Membership.Role.MEMBER,
            workspace=make_workspace(slug="second-workspace"),
        )
    else:
        target.user.is_active = False
        target.user.save(update_fields=["is_active"])
    client.force_login(actor.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = actor.user.session_generation
    session.save()
    response = client.post(
        f"/api/workspaces/{actor.workspace_id}/memberships/{target.pk}/password-reset/",
        {},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_login_without_csrf_returns_expected_failure() -> None:
    client = Client(enforce_csrf_checks=True)
    response = client.post(
        "/api/auth/login/",
        {"email": "x@example.test", "password": "x"},
        content_type="application/json",
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "csrf_failed"


@pytest.mark.parametrize(
    "path", ["/api/auth/login/", "/api/invitations/preview/", "/api/password-resets/preview/"]
)
def test_json_array_request_returns_400(client: Client, path: str) -> None:
    response = client.post(path, "[]", content_type="application/json")
    assert response.status_code == 400


def test_bootstrap_owner_weak_password_raises_command_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESCRIBO_BOOTSTRAP_PASSWORD", "weak")
    with pytest.raises(CommandError):
        call_command(
            "bootstrap_owner",
            email="new@example.test",
            full_name="New",
            workspace_name="New",
            workspace_slug="new",
            non_interactive=True,
        )


def test_issue_owner_recovery_weak_password_raises_command_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_membership(role=Membership.Role.OWNER)
    monkeypatch.setattr(
        "accounts.management.commands.issue_owner_recovery.getpass.getpass",
        lambda _prompt: "weak",
    )
    with pytest.raises(CommandError):
        call_command("issue_owner_recovery", email=owner.user.email, set_password=True)
