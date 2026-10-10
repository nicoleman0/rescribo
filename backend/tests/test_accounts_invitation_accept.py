"""Invitation acceptance over HTTP, for a new account and for one that already exists."""

from typing import Any
from uuid import uuid4

import pytest
from django.conf import settings as django_settings
from django.test import Client

from accounts.models import Invitation, Membership, User
from accounts.services import bootstrap_owner, create_invitation, revoke_membership
from accounts.session import SESSION_GENERATION_KEY

pytestmark = pytest.mark.django_db

PASSWORD = "Harbour-Copper-7628!Quilt"
OWNER_PASSWORD = "Strong-password-928!Cedar"
JSON = "application/json"


@pytest.fixture(autouse=True)
def throttle_cache(settings: Any) -> None:
    # Throttle counts in the shared Redis cache would carry over between tests and runs.
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": uuid4().hex,
        }
    }


def make_owner(slug: str = "example") -> Membership:
    return bootstrap_owner(
        email=f"owner-{slug}@example.test",
        full_name="Owner",
        password=OWNER_PASSWORD,
        workspace_name=slug.title(),
        workspace_slug=slug,
    )[2]


def signed_in(user: User) -> Client:
    client = Client()
    client.force_login(user)
    session = client.session
    session[SESSION_GENERATION_KEY] = user.session_generation
    session.save()
    return client


def post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, body, content_type=JSON)


def accept(client: Client, secret: str, **body: str) -> Any:
    return post(client, "/api/invitations/accept/", {"token": secret, **body})


def login(client: Client, email: str, password: str) -> Any:
    return post(client, "/api/auth/login/", {"email": email, "password": password})


def invite(owner: Membership, email: str) -> str:
    return create_invitation(actor=owner, email=email, role=Membership.Role.MEMBER)[1]


def removed_member(owner: Membership, email: str = "back@example.test") -> User:
    user = User.objects.create_user(email=email, full_name="Back Again", password=PASSWORD)
    membership = Membership.objects.create(workspace=owner.workspace, user=user)
    revoke_membership(actor=owner, target=membership)
    user.refresh_from_db()
    return user


def member_elsewhere(email: str = "elsewhere@example.test") -> tuple[User, Membership]:
    other_owner = make_owner("other")
    user = User.objects.create_user(email=email, full_name="Else Where", password=PASSWORD)
    Membership.objects.create(workspace=other_owner.workspace, user=user)
    return user, other_owner


def workspace_slugs(response: Any) -> list[str]:
    return sorted(item["workspace"]["slug"] for item in response.json()["memberships"])


def assert_unused(secret_owner: Membership, email: str) -> None:
    invitation = Invitation.objects.get(workspace=secret_owner.workspace, email=email)
    assert invitation.used_at is None and invitation.revoked_at is None


def test_new_account_sets_its_name_and_password_and_spends_the_invitation() -> None:
    owner = make_owner()
    secret = invite(owner, "new@example.test")
    client = Client()
    response = accept(client, secret, full_name="New Person", password=PASSWORD)
    assert response.status_code == 200
    user = User.objects.get(email="new@example.test")
    assert user.full_name == "New Person" and user.check_password(PASSWORD)
    assert workspace_slugs(client.get("/api/auth/session/")) == ["example"]
    again = accept(Client(), secret, full_name="Other", password=PASSWORD)
    assert again.status_code == 400
    assert again.json()["reason"] == "invitation_already_used"


def test_removed_member_is_invited_again_and_accepts_with_their_password() -> None:
    owner = make_owner()
    owner_client = signed_in(owner.user)
    invitations = f"/api/workspaces/{owner.workspace_id}/invitations/"
    email = "back@example.test"

    first = post(owner_client, invitations, {"email": email, "role": "member"})
    assert first.status_code == 201
    before = Client()
    joined = accept(
        before,
        first.json()["accept_url"].rsplit("/", 1)[-1],
        full_name="Back Again",
        password=PASSWORD,
    )
    assert joined.status_code == 200
    membership = Membership.objects.get(user__email=email)

    revoke = f"/api/workspaces/{owner.workspace_id}/memberships/{membership.pk}/revoke/"
    assert post(owner_client, revoke, {}).status_code == 204
    assert before.get("/api/auth/session/").status_code == 401
    # The login rule stays: an account with no active membership cannot sign in.
    assert login(Client(), email, PASSWORD).status_code == 401

    second = post(owner_client, invitations, {"email": email, "role": "member"})
    assert second.status_code == 201
    after = Client()
    response = accept(
        after,
        second.json()["accept_url"].rsplit("/", 1)[-1],
        full_name="Renamed",
        password=PASSWORD,
    )

    assert response.status_code == 200
    assert workspace_slugs(response) == ["example"]
    assert response.json()["memberships"][0]["role"] == "member"
    assert workspace_slugs(after.get("/api/auth/session/")) == ["example"]
    membership.refresh_from_db()
    assert membership.is_active and membership.revoked_at is None
    user = User.objects.get(email=email)
    assert user.full_name == "Back Again" and user.check_password(PASSWORD)
    assert not Invitation.objects.filter(email=email, used_at__isnull=True).exists()
    # The session from before the removal stays dead.
    assert before.get("/api/auth/session/").status_code == 401
    assert login(Client(), email, PASSWORD).status_code == 200


@pytest.mark.parametrize("body", [{"password": "wrong"}, {"password": ""}, {}])
def test_wrong_password_starts_no_session_and_keeps_the_invitation(body: dict[str, str]) -> None:
    owner = make_owner()
    user = removed_member(owner)
    secret = invite(owner, user.email)
    client = Client()

    response = accept(client, secret, **body)

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Password is incorrect.",
        "reason": "invalid_credentials",
        "field_errors": {"password": ["Password is incorrect."]},
    }
    assert client.get("/api/auth/session/").status_code == 401
    assert not Membership.objects.get(user=user).is_active
    assert_unused(owner, user.email)
    assert accept(client, secret, password=PASSWORD).status_code == 200


def test_signed_in_as_the_invited_account_accepts_without_a_password() -> None:
    owner = make_owner()
    user, _ = member_elsewhere()
    secret = invite(owner, user.email)
    password_hash = user.password
    client = signed_in(user)

    response = accept(client, secret, full_name="Renamed", password="Another-password-112!Fir")

    assert response.status_code == 200
    assert workspace_slugs(response) == ["example", "other"]
    user.refresh_from_db()
    assert user.full_name == "Else Where" and user.password == password_hash


@pytest.mark.parametrize("password", [None, PASSWORD])
def test_signed_in_as_another_account_is_refused(password: str | None) -> None:
    owner = make_owner()
    user = removed_member(owner)
    _, other_owner = member_elsewhere()
    secret = invite(owner, user.email)
    client = signed_in(other_owner.user)

    response = accept(client, secret, **({} if password is None else {"password": password}))

    assert response.status_code == 400
    assert response.json()["reason"] == "sign_in_required"
    assert response.json()["detail"].startswith("This invitation is for a different account.")
    assert client.get("/api/auth/session/").json()["user"]["email"] == other_owner.user.email
    assert not Membership.objects.filter(workspace=owner.workspace, user=other_owner.user).exists()
    assert not Membership.objects.get(workspace=owner.workspace, user=user).is_active
    assert_unused(owner, user.email)


def test_account_active_in_another_workspace_accepts_with_its_password() -> None:
    owner = make_owner()
    user, other_owner = member_elsewhere()
    secret = invite(owner, user.email)

    assert accept(Client(), secret, password="wrong").status_code == 401
    assert_unused(owner, user.email)
    response = accept(Client(), secret, password=PASSWORD)

    assert response.status_code == 200
    assert workspace_slugs(response) == ["example", "other"]
    elsewhere = Membership.objects.get(workspace=other_owner.workspace, user=user)
    assert elsewhere.is_active and elsewhere.role == Membership.Role.MEMBER


def test_deactivated_account_is_refused_like_a_wrong_password() -> None:
    owner = make_owner()
    user = removed_member(owner)
    User.objects.filter(pk=user.pk).update(is_active=False)
    secret = invite(owner, user.email)
    client = Client()

    response = accept(client, secret, password=PASSWORD)

    assert response.status_code == 401
    assert response.json()["reason"] == "invalid_credentials"
    assert client.get("/api/auth/session/").status_code == 401
    assert_unused(owner, user.email)


def test_password_attempts_on_an_invitation_share_the_login_limit() -> None:
    limit = int(
        django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login_identity"].split("/")[0]
    )
    owner = make_owner()
    user = removed_member(owner)
    secret = invite(owner, user.email)
    other = removed_member(owner, email="other-back@example.test")
    other_secret = invite(owner, other.email)
    client = Client()

    for _ in range(limit):
        assert accept(client, secret, password="wrong").status_code == 401

    assert accept(client, secret, password=PASSWORD).status_code == 429
    assert login(Client(), user.email, PASSWORD).status_code == 429
    assert_unused(owner, user.email)
    # The limit is per account: another invited account and another login still work.
    assert accept(client, other_secret, password=PASSWORD).status_code == 200
    assert login(Client(), owner.user.email, OWNER_PASSWORD).status_code == 200
