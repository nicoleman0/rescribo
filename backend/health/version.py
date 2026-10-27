"""The running release version, read from pyproject.toml.

The project is never installed (`[tool.uv] package = false`), so
importlib.metadata cannot provide the version and pyproject.toml is the
one source of truth. Both image targets copy pyproject.toml beside
backend/, and a dev checkout has the same layout.
"""

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

try:
    with _PYPROJECT.open("rb") as f:
        _pyproject = tomllib.load(f)
    VERSION: str = _pyproject["project"]["version"]
except FileNotFoundError as error:
    raise RuntimeError(f"Cannot find {_PYPROJECT} to read the version") from error
except KeyError as error:
    raise RuntimeError(f"{_PYPROJECT} has no [project] version") from error
