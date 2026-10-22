import logging
import subprocess
import sys
from pathlib import Path

import environ
import pytest

from env_file import read_env_file

ENV_TEXT = (
    "GOOD=kept\n"
    'RESCRIBO_GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n'
    "MIIE+secret/bodymarker==\n"
    '-----END RSA PRIVATE KEY-----secretendmarker"\n'
    "# a comment\n"
    "\n"
    "ALSO_GOOD=kept too\n"
)


def write_env_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.env"
    path.write_text(ENV_TEXT)
    return path


def test_invalid_lines_warn_with_their_number_and_no_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    values: dict[str, str] = {}
    monkeypatch.setattr(environ.Env, "ENVIRON", values)
    path = write_env_file(tmp_path)

    with caplog.at_level(logging.WARNING, logger="environ.environ"):
        read_env_file(path)

    assert caplog.messages == [
        "Skipped invalid line 3 in test.env. Its value is not logged.",
        "Skipped invalid line 4 in test.env. Its value is not logged.",
    ]
    assert "secretbodymarker" not in caplog.text
    assert "secretendmarker" not in caplog.text
    assert "END RSA" not in caplog.text
    assert values["GOOD"] == "kept"
    assert values["ALSO_GOOD"] == "kept too"


def test_redacted_warning_reaches_stderr_without_logging_config(tmp_path: Path) -> None:
    path = write_env_file(tmp_path)
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "from env_file import read_env_file; "
            "read_env_file(Path(sys.argv[1])); "
            "assert 'config' not in sys.modules and 'celery' not in sys.modules",
            str(path),
        ],
        cwd=backend,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Skipped invalid line 3 in test.env." in result.stderr
    assert "secretbodymarker" not in result.stderr
    assert "secretendmarker" not in result.stderr
    assert "END RSA" not in result.stderr


def test_repeated_invalid_lines_get_their_own_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(environ.Env, "ENVIRON", {})
    path = tmp_path / "test.env"
    path.write_text("A=1\nsame\nB=2\nsame\n")

    with caplog.at_level(logging.WARNING, logger="environ.environ"):
        read_env_file(path)

    assert caplog.messages == [
        "Skipped invalid line 2 in test.env. Its value is not logged.",
        "Skipped invalid line 4 in test.env. Its value is not logged.",
    ]


def test_set_variables_are_not_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values: dict[str, str] = {"GOOD": "from environment"}
    monkeypatch.setattr(environ.Env, "ENVIRON", values)
    read_env_file(write_env_file(tmp_path))
    assert values["GOOD"] == "from environment"


def test_missing_file_is_ignored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values: dict[str, str] = {}
    monkeypatch.setattr(environ.Env, "ENVIRON", values)
    read_env_file(tmp_path / "absent.env")
    assert values == {}


def test_filter_is_removed_after_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environ.Env, "ENVIRON", {})
    read_env_file(write_env_file(tmp_path))
    assert logging.getLogger("environ.environ").filters == []
