# Proposal

Delivers GitHub issue #215 (milestone G. Manual check findings). Found while planning #168.

## Why

`backend/config/settings.py` loads `.env` with `environ.Env.read_env`. django-environ logs each line it cannot parse with `logger.warning('Invalid line: %s', line)`. Settings load before any logging is configured, and the project has no `LOGGING` setting, so Python's `lastResort` handler prints the whole line to stderr. Every process that loads settings does this: the API, the Celery worker and beat, and `manage.py` commands.

A quoted multi-line value is the common case. Its first line parses; every later line is reported. Reproduced on django-environ 0.14.0 with a three-line quoted value:

```
Invalid line: secretline
Invalid line: -----END"
```

For a PEM key in `RESCRIBO_GITHUB_PRIVATE_KEY`, that prints the key body. The rule applies to every variable.

## What Changes

- New module `backend/config/env_file.py` with `read_env_file(path)`. It is the one place the backend reads a `.env` file.
- `read_env_file` calls `environ.Env.read_env` as today (`overwrite=False`). For the duration of that call, a logging filter on django-environ's logger rewrites each invalid-line warning to `Skipped invalid line <n> in <file name>. Its value is not logged.` One warning per invalid line remains.
- `settings.py` calls `read_env_file(BASE_DIR / ".env")` in place of `environ.Env.read_env(...)`.
- New tests in `backend/tests/test_env_file.py`, including one that runs the read in a subprocess with no logging configured and checks stderr, which is where the warning goes today.
- A missing `.env` is still ignored. Other read errors now raise instead of being logged at `info` and ignored.

No frontend, API contract, migration, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Startup logging is tooling, not product behaviour.

## Impact

- `backend/config/env_file.py` (new), `backend/config/settings.py` (one call).
- `backend/tests/test_env_file.py` (new).
- Not changed: `backend/integrations/github_app/private_key.py` and its startup validation from #218.
- Not changed here: ten `environ.Env.read_env` calls in eight `scripts/` files have the same leak (question 1 in the plan summary).
