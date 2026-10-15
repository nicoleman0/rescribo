# Design

## Context

See proposal.md for the leak. Facts the approach relies on, read from django-environ 0.14.0 (`environ/environ.py`, the version in `uv.lock`):

- `read_env` accepts a path or a file-like object. With a file-like object it calls `.read()` once.
- It iterates `content.splitlines()` in order. A line is valid if it matches `\A(?:export )?([A-Za-z_0-9]+)=(.*)\Z`. Empty lines and lines starting with `#` are skipped silently. Every other line is logged with `logger.warning('Invalid line: %s', line)` on the logger `environ.environ`. Valid lines are still loaded.
- A record logged on a logger passes that logger's own filters before any handler, including `lastResort`.

**Prototyped before planning** (scratchpad, not in the repository). A filter on `environ.environ` that rewrites the record, applied to a file with `GOOD=1` and a three-line quoted value, printed:

```
Invalid line 3 in t.env; its value is not logged.
Invalid line 4 in t.env; its value is not logged.
GOOD 1
```

## Goals / Non-Goals

**Goals:**
- One warning per invalid line, with its line number and the file name, and no part of the line.
- The validity rule stays django-environ's. We change only what is logged.
- The `.env` read has one home in the backend.

**Non-Goals:**
- Scripts in `scripts/` (question 1).
- Configuring Django `LOGGING`.
- Supporting multi-line values in `.env`. `docs/SETTINGS.md` already says to use the one-line form.
- `RESCRIBO_GITHUB_PRIVATE_KEY` validation (#218).

## Decisions

**Rewrite django-environ's record with a scoped logging filter.** `read_env_file` reads the file once, adds a filter to `logging.getLogger("environ.environ")`, calls `environ.Env.read_env(io.StringIO(content), overwrite=False)`, and removes the filter in `finally`. The filter leaves every other record alone. For a record whose `msg` is `"Invalid line: %s"`, it finds the line number and replaces `msg` and `args`. The record keeps its logger name and `WARNING` level, so it reaches the same handlers as today.

Alternatives:
- Pre-scan the file with our own copy of the regex, blank invalid lines, and log our own warning. It copies django-environ's validity rule. If the library's rule changes, the two disagree: we drop a line it would accept, or it warns with the value again.
- Silence `environ.environ` and log nothing. Ruled out by the brief: a warning per invalid line stays.
- Configure Django `LOGGING`. Settings are still loading when the warning fires, so it would not apply.
- Patch or wrap `read_env`. Ruled out by the brief.

**Line number and file name, no variable name.** An invalid line by definition did not match `NAME=value`, so there is no name to read. Taking text before an `=` would be unsafe: a base64 PEM body line can end in `=` or `==`, so its "name" is key material. The line number is enough to find the line in the file. The file name (`path.name`, not the full path) tells `.env` apart from other files if the helper is reused.

**Find the line number by walking forward.** `read_env` reports invalid lines in file order, so the filter keeps a cursor and moves it forward until a line equals the reported one. Equal lines (two `-----END` lines) then get their own numbers. If the line is not found, the filter raises `AssertionError("django-environ reported a line that is not in the file.")`. It does not use `list.index`, whose `ValueError` message quotes the missing value. The exception propagates out of `logger.warning` and stops startup, which is the right outcome for a "can't happen" case.

**Read the file ourselves.** The filter needs the same text `read_env` parses, so `read_env_file` reads it once with `path.read_text(encoding="utf8")` (django-environ's default encoding) and passes a `StringIO`. A missing file returns early, as today: production gets its environment from `env_file: .env.production` in `compose.prod.yaml`, and no `.env` exists there. Any other `OSError` now propagates. Today django-environ logs it at `info`, which `lastResort` drops, and starts without the file.

**Match django-environ's message literally.** The filter compares `record.msg` with `"Invalid line: %s"`. If a later django-environ release changes the message, the filter stops matching and the test that expects the new message fails. `uv.lock` pins the version until then.

Module shape (the implementer may adjust names, not behaviour):

```python
"""Read `.env` without logging the values of lines django-environ cannot parse."""

import io
import logging
from pathlib import Path

import environ

# django-environ 0.14's message; test_env_file fails if it changes.
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
        # read_env reports lines in file order. list.index would quote the line on failure.
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
```

## Risks / Trade-offs

- [The filter depends on django-environ's message text and logger name] → The redaction tests assert the rewritten message, so an upgrade that changes either fails `task test-backend` before it ships.
- [A body line made only of `[A-Za-z0-9_]` followed by `=` matches django-environ's assignment rule] → It is parsed as an assignment and is not logged; this change leaves that behavior alone.
- [A filter on a shared logger could affect other code] → It is added and removed around one call at settings import, before any thread starts.
- [Debug record `Read environment variables from: <StringIO ...>` no longer names the path] → Debug level, never shown by `lastResort`, holds no values.
- [`scripts/` still leak] → Question 1. Same leak; the scripts cannot import `config.env_file` without importing `config/__init__.py`, which builds the Celery app.
