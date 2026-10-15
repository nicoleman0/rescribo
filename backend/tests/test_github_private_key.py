"""GitHub App private key forms: PEM text with newlines, one line with \\n escapes."""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import environ
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.core.exceptions import ImproperlyConfigured

from integrations.github_app.client import create_app_jwt
from integrations.github_app.private_key import MESSAGE, load_private_key


def generate_pkcs1_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )


def generate_pkcs8_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def generate_encrypted_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"rescribo-test-password"),
    )


def one_line(pem: bytes) -> str:
    return pem.decode().replace("\n", "\\n")


def jwt_verifies(app_id: str, pem_text: str, pem: bytes) -> bool:
    header, payload, signature = create_app_jwt(app_id, pem_text.encode()).split(".")
    signing_input = f"{header}.{payload}".encode("ascii")
    key = serialization.load_pem_private_key(pem, password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    try:
        key.public_key().verify(
            b64url_decode(signature), signing_input, padding.PKCS1v15(), hashes.SHA256()
        )
    except InvalidSignature:
        return False
    return json.loads(b64url_decode(payload))["iss"] == app_id


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def read_env_file(env_file: Path) -> dict[str, str]:
    """Read a .env file with django-environ without touching os.environ."""
    values: dict[str, str] = {}
    env = environ.Env()
    saved = environ.Env.ENVIRON
    environ.Env.ENVIRON = values
    try:
        env.read_env(str(env_file))
    finally:
        environ.Env.ENVIRON = saved
    return values


def test_loads_pkcs1_and_pkcs8_multi_line_keys() -> None:
    for pem in (generate_pkcs1_pem(), generate_pkcs8_pem()):
        assert load_private_key(pem.decode()) == pem.decode().strip()
        assert jwt_verifies("123", load_private_key(pem.decode()), pem)


def test_one_line_form_returns_the_multi_line_text() -> None:
    pem = generate_pkcs8_pem()
    assert load_private_key(one_line(pem)) == pem.decode().strip()


def test_empty_and_whitespace_only_values_mean_not_configured() -> None:
    assert load_private_key("") == ""
    assert load_private_key("   \n ") == ""


@pytest.mark.parametrize(
    "value",
    [
        # Truncated: the first PEM line only, what a multi-line .env value becomes.
        "-----BEGIN RSA PRIVATE KEY-----",
        "not a key at all",
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
    ],
)
def test_bad_values_raise_improperly_configured(value: str) -> None:
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_private_key(value)
    assert str(excinfo.value) == MESSAGE
    assert "RESCRIBO_GITHUB_PRIVATE_KEY" in str(excinfo.value)
    assert "\\n between the PEM lines" in str(excinfo.value)


def test_truncated_key_message_contains_no_key_material() -> None:
    first_line = generate_pkcs1_pem().decode().splitlines()[0]
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_private_key(first_line)
    assert first_line not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_encrypted_rsa_key_is_rejected() -> None:
    pem = generate_encrypted_pem()
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_private_key(pem.decode())
    assert "RESCRIBO_GITHUB_PRIVATE_KEY" in str(excinfo.value)
    pem_body = pem.decode().split("-----")[2].strip().split("\n")[0]
    assert pem_body not in str(excinfo.value)


def test_ec_key_is_rejected() -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_private_key(pem.decode())
    assert "RESCRIBO_GITHUB_PRIVATE_KEY" in str(excinfo.value)
    assert "BEGIN PUBLIC KEY" not in str(excinfo.value)


# Task 1.2: env-file tests against the exact lines documented in
# docs/SETTINGS.md and .env.production.example. The documented line shape is
# `RESCRIBO_GITHUB_PRIVATE_KEY=-----BEGIN ... KEY-----\n...\n-----END ... KEY-----`,
# unquoted, one line, with literal \\n where the PEM has newlines. The
# placeholder body is not a key; each test puts a real generated key into the
# documented shape.


def write_env_file(tmp_path: Path, line: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(line + "\n")
    return env_file


def test_documented_one_line_unquoted_env_file_loads_and_signs(tmp_path: Path) -> None:
    pem = generate_pkcs1_pem()
    env_file = write_env_file(tmp_path, f"RESCRIBO_GITHUB_PRIVATE_KEY={one_line(pem)}")
    value = load_private_key(read_env_file(env_file)["RESCRIBO_GITHUB_PRIVATE_KEY"])
    assert value == pem.decode().strip()
    assert jwt_verifies("123", value, pem)


def test_documented_one_line_single_quoted_env_file_loads_and_signs(tmp_path: Path) -> None:
    pem = generate_pkcs1_pem()
    env_file = write_env_file(tmp_path, f"RESCRIBO_GITHUB_PRIVATE_KEY='{one_line(pem)}'")
    value = load_private_key(read_env_file(env_file)["RESCRIBO_GITHUB_PRIVATE_KEY"])
    assert value == pem.decode().strip()
    assert jwt_verifies("123", value, pem)


def test_documented_one_line_double_quoted_env_file_keeps_escapes_loads_and_signs(
    tmp_path: Path,
) -> None:
    """django-environ keeps \\n escaped inside double quotes; the loader unescapes it."""
    pem = generate_pkcs1_pem()
    env_file = write_env_file(tmp_path, f'RESCRIBO_GITHUB_PRIVATE_KEY="{one_line(pem)}"')
    value = load_private_key(read_env_file(env_file)["RESCRIBO_GITHUB_PRIVATE_KEY"])
    assert value == pem.decode().strip()
    assert jwt_verifies("123", value, pem)


def test_full_pem_text_from_a_shell_can_be_loaded(tmp_path: Path) -> None:
    """Real newlines, as process environments and Compose interpolations carry them."""
    pem = generate_pkcs8_pem()
    assert jwt_verifies("123", load_private_key(pem.decode()), pem)


def run_django_setup(github_key: str) -> subprocess.CompletedProcess[bytes]:
    repo_root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, DJANGO_SETTINGS_MODULE="config.settings")
    if github_key is None:
        env.pop("RESCRIBO_GITHUB_PRIVATE_KEY", None)
    else:
        env["RESCRIBO_GITHUB_PRIVATE_KEY"] = github_key
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=repo_root / "backend",
        env=env,
        capture_output=True,
    )


def test_subprocess_startup_fails_on_a_truncated_key() -> None:
    first_line = generate_pkcs1_pem().decode().splitlines()[0]
    result = run_django_setup(first_line)
    assert result.returncode != 0
    assert "RESCRIBO_GITHUB_PRIVATE_KEY" in result.stderr.decode()
    assert first_line not in result.stderr.decode()


def test_subprocess_startup_fails_on_the_documented_one_line_placeholder() -> None:
    value = "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----"
    result = run_django_setup(value)
    assert result.returncode != 0
    assert "RESCRIBO_GITHUB_PRIVATE_KEY" in result.stderr.decode()


def test_subprocess_startup_succeeds_on_a_valid_one_line_key() -> None:
    result = run_django_setup(one_line(generate_pkcs1_pem()))
    assert result.returncode == 0
    assert b"RESCRIBO_GITHUB_PRIVATE_KEY" not in result.stderr


def test_subprocess_startup_succeeds_without_a_key() -> None:
    result = run_django_setup("")
    assert result.returncode == 0
