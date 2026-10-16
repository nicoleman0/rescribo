"""Read `.env` without logging the values of lines django-environ cannot parse."""

import io
import logging
from pathlib import Path

import environ

LIBRARY_MESSAGE = "Invalid line: %s"
MESSAGE = "Skipped invalid line %d in %s. Its value is not logged."


class _RedactInvalidLines(logging.Filter):
    def __init__(self, lines: list[str], file_name: str) -> None:
        super().__init__()
        self._lines = lines
        self._file_name = file_name
        self._next = 0

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg != LIBRARY_MESSAGE:
            return True
        assert isinstance(record.args, tuple) and len(record.args) == 1
        for index in range(self._next, len(self._lines)):
            if self._lines[index] == record.args[0]:
                break
        else:
            raise AssertionError("django-environ reported a line that is not in the file.")
        self._next = index + 1
        record.msg, record.args = MESSAGE, (self._next, self._file_name)
        return True


def read_env_file(path: Path) -> None:
    """Load `path` into the environment without overwriting set variables."""
    try:
        content = path.read_text(encoding="utf8")
    except FileNotFoundError:
        return
    library_logger = logging.getLogger("environ.environ")
    redact = _RedactInvalidLines(content.splitlines(), path.name)
    library_logger.addFilter(redact)
    try:
        environ.Env.read_env(io.StringIO(content), overwrite=False)
    finally:
        library_logger.removeFilter(redact)
