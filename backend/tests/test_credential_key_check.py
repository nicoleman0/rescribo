"""The startup check that guards stored provider credentials."""

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from connections.apps import check_credential_key


@pytest.mark.parametrize("key", ["", "not-a-fernet-key"])
def test_production_without_a_usable_key_fails_the_check(key: str) -> None:
    with override_settings(DEBUG=False, RESCRIBO_CREDENTIAL_KEY=key):
        assert [error.id for error in check_credential_key()] == ["connections.E001"]


def test_production_with_a_valid_key_passes() -> None:
    with override_settings(DEBUG=False, RESCRIBO_CREDENTIAL_KEY=Fernet.generate_key().decode()):
        assert check_credential_key() == []


def test_local_development_does_not_need_a_key() -> None:
    with override_settings(DEBUG=True, RESCRIBO_CREDENTIAL_KEY=""):
        assert check_credential_key() == []
