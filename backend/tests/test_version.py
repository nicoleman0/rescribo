"""The version endpoint and the version read from pyproject.toml."""

import tomllib
from pathlib import Path

import pytest
from django.test import Client

from accounts.services import bootstrap_owner
from accounts.session import SESSION_GENERATION_KEY
from health.version import VERSION

PASSWORD = "Harbour-Copper-7628!Quilt"
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def version_from_pyproject() -> str:
    with PYPROJECT.open("rb") as f:
        pyproject = tomllib.load(f)
    return pyproject["project"]["version"]


def test_version_matches_pyproject_toml() -> None:
    assert VERSION == version_from_pyproject()


@pytest.mark.django_db
def test_member_gets_the_pyproject_version() -> None:
    membership = bootstrap_owner(
        email="owner@example.test",
        full_name="Owner",
        password=PASSWORD,
        workspace_name="Example",
        workspace_slug="example",
    )[2]
    client = Client()
    client.force_login(membership.user)
    session = client.session
    session[SESSION_GENERATION_KEY] = membership.user.session_generation
    session.save()
    response = client.get("/api/version/")
    assert response.status_code == 200
    assert response.json() == {"version": version_from_pyproject()}


def test_signed_out_request_is_refused() -> None:
    response = Client().get("/api/version/")
    assert response.status_code == 401
    assert "version" not in response.json()
