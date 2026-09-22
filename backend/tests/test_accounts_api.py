import pytest
from builders import make_membership, make_user, make_workspace
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
