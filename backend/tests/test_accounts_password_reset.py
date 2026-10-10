"""Password reset redemption over HTTP."""

from typing import Any
from uuid import uuid4

import pytest
from django.conf import settings as django_settings
from django.test import Client

from accounts.models import Membership, PasswordReset, User
from accounts.services import bootstrap_owner, create_password_reset

pytestmark = pytest.mark.django_db

PASSWORD = "Harbour-Copper-7628!Quilt"
NEW_PASSWORD = "Cobalt-Window-9264!Birch"
OWNER_PASSWORD = "Strong-password-928!Cedar"
JSON = "application/json"
UNCHANGED = {
    "detail": "Choose a different password.",
    "reason": "password_unchanged",
    "field_errors": {"password": ["This is your current password."]},
}


@pytest.fixture(autouse=True)
def throttle_cache(settings: Any) -> None:
    # Throttle counts in the shared Redis cache would carry over between tests and runs.
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": uuid4().hex,
        }
    }


def make_owner() -> Membership:
    return bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password=OWNER_PASSWORD,
        workspace_name="Example",
        workspace_slug="example",
    )[2]


def make_member(owner: Membership, email: str = "member@example.test") -> Membership:
    user = User.objects.create_user(email=email, full_name="Member", password=PASSWORD)
    return Membership.objects.create(workspace=owner.workspace, user=user)


def post(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.post(path, body, content_type=JSON)


def redeem(client: Client, secret: str, password: str) -> Any:
    return post(client, "/api/password-resets/redeem/", {"token": secret, "password": password})


def login(client: Client, email: str, password: str) -> Any:
    return post(client, "/api/auth/login/", {"email": email, "password": password})


def assert_untouched(reset: PasswordReset, user: User, password: str) -> None:
    generation = user.session_generation
    reset.refresh_from_db()
    user.refresh_from_db()
    assert reset.used_at is None and reset.revoked_at is None
    assert user.session_generation == generation
    assert user.check_password(password)


def test_current_password_is_refused_and_the_link_stays_usable() -> None:
    owner = make_owner()
    member = make_member(owner)
    user = member.user
    session = Client()
    assert login(session, user.email, PASSWORD).status_code == 200
    reset, secret = create_password_reset(actor=owner, target=member)
    client = Client()

    response = redeem(client, secret, PASSWORD)

    assert response.status_code == 400
    assert response.json() == UNCHANGED
    assert_untouched(reset, user, PASSWORD)
    assert client.get("/api/auth/session/").status_code == 401
    assert session.get("/api/auth/session/").status_code == 200

    assert redeem(client, secret, NEW_PASSWORD).status_code == 200
    reset.refresh_from_db()
    user.refresh_from_db()
    assert reset.used_at is not None
    assert user.check_password(NEW_PASSWORD)
    assert session.get("/api/auth/session/").status_code == 401
    assert client.get("/api/auth/session/").status_code == 200


def test_operator_issued_link_refuses_the_owner_current_password() -> None:
    owner = make_owner()
    reset, secret = create_password_reset(actor=owner, target=owner, issued_by_operator=True)
    client = Client()

    response = redeem(client, secret, OWNER_PASSWORD)

    assert response.status_code == 400
    assert response.json() == UNCHANGED
    assert_untouched(reset, owner.user, OWNER_PASSWORD)
    assert redeem(client, secret, NEW_PASSWORD).status_code == 200


def test_weak_password_keeps_its_own_reason() -> None:
    owner = make_owner()
    member = make_member(owner)
    reset, secret = create_password_reset(actor=owner, target=member)

    response = redeem(Client(), secret, "weak")

    assert response.status_code == 400
    assert response.json()["reason"] == "password_rejected"
    assert response.json()["detail"] == "Choose a stronger password."
    assert response.json()["field_errors"]["password"]
    assert_untouched(reset, member.user, PASSWORD)


def test_password_attempts_on_a_reset_link_share_the_login_limit() -> None:
    limit = int(
        django_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login_identity"].split("/")[0]
    )
    owner = make_owner()
    member = make_member(owner)
    reset, secret = create_password_reset(actor=owner, target=member)
    client = Client()

    for _ in range(limit):
        assert redeem(client, secret, PASSWORD).status_code == 400

    assert redeem(client, secret, NEW_PASSWORD).status_code == 429
    assert login(Client(), member.user.email, PASSWORD).status_code == 429
    assert_untouched(reset, member.user, PASSWORD)
    # The limit is per account: another account still signs in.
    assert login(Client(), owner.user.email, OWNER_PASSWORD).status_code == 200
