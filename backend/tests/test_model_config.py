"""The rescribo.toml deployment default: shape, startup failures, and no key in messages."""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from integrations.model.config import DeploymentModel, load_deployment_model

REPO_ROOT = Path(__file__).resolve().parents[2]
KEY = "sk-test-marker-9f3a"
VALID = """
[model]
api_style = "openai"
base_url = "https://api.openai.com/v1/"
model = "gpt-5-mini"
api_key_env = "OPENAI_API_KEY"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "rescribo.toml"
    path.write_text(text)
    return path


def test_no_default_file_means_no_deployment_config(tmp_path: Path) -> None:
    assert load_deployment_model(tmp_path / "rescribo.toml", {}, required=False) is None


def test_file_without_model_table_means_no_deployment_config(tmp_path: Path) -> None:
    assert load_deployment_model(write(tmp_path, ""), {}, required=False) is None


def test_valid_file_returns_values_and_keeps_only_the_variable_name(tmp_path: Path) -> None:
    config = load_deployment_model(write(tmp_path, VALID), {"OPENAI_API_KEY": KEY}, required=True)
    assert config == DeploymentModel(
        api_style="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        api_key_env="OPENAI_API_KEY",
    )
    assert KEY not in repr(config)


def test_local_server_needs_no_key(tmp_path: Path) -> None:
    text = '[model]\napi_style = "openai"\nbase_url = "http://ollama:11434/v1"\nmodel = "llama3"\n'
    config = load_deployment_model(write(tmp_path, text), {}, required=False)
    assert config is not None and config.api_key_env == ""


def test_missing_explicit_path_fails(tmp_path: Path) -> None:
    path = tmp_path / "missing.toml"
    with pytest.raises(ImproperlyConfigured, match=re.escape(str(path))):
        load_deployment_model(path, {}, required=True)


@pytest.mark.parametrize(
    ("text", "field"),
    [
        (VALID + 'api_key = "sk-oops"\n', "api_key"),
        (VALID.replace('"openai"', '"cohere"'), "api_style"),
        (VALID.replace('model = "gpt-5-mini"\n', ""), "model"),
        (VALID.replace("https://api.openai.com/v1/", "ftp://example.test"), "base_url"),
        (VALID.replace("https://api.openai.com/v1/", "https://u:p@example.test"), "base_url"),
        (VALID.replace("https://api.openai.com/v1/", "https://example.test/?a=1"), "base_url"),
        (VALID.replace('"gpt-5-mini"', '""'), "model"),
        (VALID + "[other]\n", "other"),
        ("model = 1\n", "[model]"),
        ("[model\n", "TOML"),
    ],
)
def test_invalid_files_name_the_file_and_field(tmp_path: Path, text: str, field: str) -> None:
    path = write(tmp_path, text)
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_deployment_model(path, {"OPENAI_API_KEY": KEY}, required=True)
    assert str(path) in str(excinfo.value)
    assert field in str(excinfo.value)
    assert KEY not in str(excinfo.value) and "sk-oops" not in str(excinfo.value)


@pytest.mark.parametrize("environ", [{}, {"OPENAI_API_KEY": ""}, {"OPENAI_API_KEY": "  "}])
def test_unset_or_empty_key_variable_fails(tmp_path: Path, environ: dict[str, str]) -> None:
    path = write(tmp_path, VALID)
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_deployment_model(path, environ, required=True)
    assert str(path) in str(excinfo.value) and "OPENAI_API_KEY" in str(excinfo.value)


def uncommented_block(name: str) -> str:
    """One commented block of rescribo.toml.example, uncommented."""
    text = (REPO_ROOT / "rescribo.toml.example").read_text()
    block = text.split(f"# --- {name} ---\n")[1].split("\n\n")[0]
    return "\n".join(line.removeprefix("# ") for line in block.splitlines()) + "\n"


@pytest.mark.parametrize("name", ["OpenAI", "Anthropic", "Ollama"])
def test_documented_examples_load(tmp_path: Path, name: str) -> None:
    environ = {"OPENAI_API_KEY": KEY, "ANTHROPIC_API_KEY": KEY}
    config = load_deployment_model(write(tmp_path, uncommented_block(name)), environ, required=True)
    assert config is not None


def run_django_setup(config_file: str, **extra: str) -> subprocess.CompletedProcess[bytes]:
    env = dict(
        os.environ, DJANGO_SETTINGS_MODULE="config.settings", RESCRIBO_CONFIG_FILE=config_file
    )
    env.pop("OPENAI_API_KEY", None)
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=REPO_ROOT / "backend",
        env=env,
        capture_output=True,
    )


def test_invalid_file_stops_startup_with_the_file_name(tmp_path: Path) -> None:
    path = write(tmp_path, VALID)
    result = run_django_setup(str(path))
    assert result.returncode != 0
    assert str(path) in result.stderr.decode() and "OPENAI_API_KEY" in result.stderr.decode()


def test_valid_file_starts_without_printing_the_key(tmp_path: Path) -> None:
    result = run_django_setup(str(write(tmp_path, VALID)), OPENAI_API_KEY=KEY)
    assert result.returncode == 0
    assert KEY.encode() not in result.stderr + result.stdout


def test_startup_succeeds_without_a_config_file() -> None:
    assert run_django_setup("").returncode == 0
