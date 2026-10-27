"""The deployment's model provider, read from rescribo.toml once at startup.

Imported by settings, so it must not import Django models or app modules.
"""

import re
import tomllib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

API_STYLES = ("openai", "anthropic")
MAX_BASE_URL = 500
MAX_MODEL = 200
REQUIRED = ("api_style", "base_url", "model")
ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True)
class DeploymentModel:
    api_style: str
    base_url: str
    model: str
    # The name of the variable that holds the key. Blank for a local server with no key.
    api_key_env: str


def base_url_problem(url: str, schemes: Collection[str]) -> str | None:
    """Why `url` cannot be a base URL, or None. Never echoes the URL."""
    if len(url) > MAX_BASE_URL:
        return f"is longer than {MAX_BASE_URL} characters"
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises on a bad port
    except ValueError:
        return "is not a valid URL"
    if parts.scheme not in schemes:
        return f"must start with {' or '.join(f'{scheme}://' for scheme in schemes)}"
    if not parts.hostname:
        return "has no host"
    if parts.username is not None or parts.password is not None:
        return "must not contain credentials"
    if parts.query or parts.fragment or url.endswith(("?", "#")):
        return "must not contain a query or fragment"
    return None


def load_deployment_model(
    path: Path, environ: Mapping[str, str], *, required: bool
) -> DeploymentModel | None:
    """Return the `[model]` table, None without one, or fail naming the file and field.

    `required` is true when the operator set the path, so a missing file is an error.
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf8"))
    except FileNotFoundError:
        if required:
            raise ImproperlyConfigured(
                f"{path}: RESCRIBO_CONFIG_FILE names a file that does not exist."
            ) from None
        return None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ImproperlyConfigured(f"{path}: not a readable TOML file ({error}).") from None

    def fail(problem: str) -> ImproperlyConfigured:
        return ImproperlyConfigured(f"{path}: {problem}. See rescribo.toml.example.")

    unknown = sorted(set(data) - {"model"})
    if unknown:
        raise fail(f"unknown table or key {', '.join(unknown)}")
    table = data.get("model")
    if table is None:
        return None
    if not isinstance(table, dict):
        raise fail("[model] must be a table")
    unknown = sorted(set(table) - {*REQUIRED, "api_key_env"})
    if unknown:
        raise fail(f"[model] has unknown key {', '.join(unknown)}")
    for field in (*REQUIRED, "api_key_env"):
        value = table.get(field)
        if field in REQUIRED and value is None:
            raise fail(f"[model] {field} is missing")
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise fail(f"[model] {field} must be a non-empty string")
    if table["api_style"] not in API_STYLES:
        raise fail(f"[model] api_style must be one of {', '.join(API_STYLES)}")
    problem = base_url_problem(table["base_url"], ("http", "https"))
    if problem:
        raise fail(f"[model] base_url {problem}")
    if len(table["model"]) > MAX_MODEL:
        raise fail(f"[model] model is longer than {MAX_MODEL} characters")
    key_env = table.get("api_key_env", "")
    if key_env and not ENV_NAME.fullmatch(key_env):
        raise fail("[model] api_key_env must be an environment variable name")
    if key_env and not environ.get(key_env, "").strip():
        raise fail(f"[model] api_key_env names {key_env}, which is unset or empty")
    return DeploymentModel(
        api_style=table["api_style"],
        base_url=table["base_url"].rstrip("/"),
        model=table["model"],
        api_key_env=key_env,
    )
