# Tasks

Delivers #215. Tooling; `skip_specs: true`. Backend only. Change only `backend/config/env_file.py` (new), `backend/config/settings.py`, and `backend/tests/test_env_file.py` (new). Do not touch `scripts/`, `docs/`, `backend/integrations/github_app/private_key.py`, the frontend, or `openspec/specs/`.

Run backend tests with `task test-backend` (it builds the matcher first).

## 1. Tests first

Shared fixture for the file: one file-level constant, written to `tmp_path / "test.env"` by each test that needs it. The secret markers are unique strings that appear only in the invalid lines.

```python
ENV_TEXT = (
    "GOOD=kept\n"
    'RESCRIBO_GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n'
    "MIIE+secret/bodymarker==\n"
    '-----END RSA PRIVATE KEY-----secretendmarker"\n'
    "# a comment\n"
    "\n"
    "ALSO_GOOD=kept too\n"
)
```

Isolate the environment with `monkeypatch.setattr(environ.Env, "ENVIRON", {})` (django-environ writes to `Env.ENVIRON`, which is `os.environ` by default) and read it back from that dict.

- [x] 1.1 Create `backend/tests/test_env_file.py` with these tests, importing `read_env_file` from `config.env_file`:
  - `test_invalid_lines_warn_with_their_number_and_no_value(tmp_path, monkeypatch, caplog)`: inside `caplog.at_level(logging.WARNING, logger="environ.environ")`, read the file. Assert `caplog.messages == ["Skipped invalid line 3 in test.env. Its value is not logged.", "Skipped invalid line 4 in test.env. Its value is not logged."]`, and that `"secretbodymarker"`, `"secretendmarker"`, and `"END RSA"` are not in `caplog.text`. Assert `GOOD == "kept"` and `ALSO_GOOD == "kept too"` in the patched dict.
  - `test_redacted_warning_reaches_stderr_without_logging_config(tmp_path)`: write the file, then run `[sys.executable, "-c", "import sys; from pathlib import Path; from config.env_file import read_env_file; read_env_file(Path(sys.argv[1]))", str(path)]` with `cwd` set to the repository's `backend` directory (as `test_github_private_key.py` does), `capture_output=True`, `text=True`. Assert return code 0, `"Skipped invalid line 3 in test.env." in stderr`, and none of the three secret strings in stderr. This is the `lastResort` path settings use today.
  - `test_repeated_invalid_lines_get_their_own_numbers(tmp_path, monkeypatch, caplog)`: file `"A=1\nsame\nB=2\nsame\n"`. Assert the messages name lines 2 and 4.
  - `test_set_variables_are_not_overwritten(tmp_path, monkeypatch)`: patched dict `{"GOOD": "from environment"}`. After the read, `GOOD` is still `"from environment"`.
  - `test_missing_file_is_ignored(tmp_path, monkeypatch)`: reading `tmp_path / "absent.env"` returns and leaves the patched dict empty.
  - `test_filter_is_removed_after_reading(tmp_path, monkeypatch)`: after a read, `logging.getLogger("environ.environ").filters == []`.
- [x] 1.2 Temporarily remove `backend/config/env_file.py` and run `uv run pytest backend/tests/test_env_file.py`. Verify pytest-django stops at startup with `ImportError: No module named 'config.env_file'`; the module-level import prevents test collection and the subprocess test from running in this fail-first check.
- [x] 1.3 Confirm the leak on the current code: run `uv run python -c "import environ, sys; environ.Env.read_env(sys.argv[1])" <file>` on a copy of `ENV_TEXT` in a temporary directory. Verify stderr shows `Invalid line: MIIE+secret/bodymarker==`. Delete the file.

## 2. Fix

- [x] 2.1 Create `backend/config/env_file.py` following the module shape in design.md. Run `uv run pytest backend/tests/test_env_file.py`. Verify 6 passed.
- [x] 2.2 `backend/config/settings.py`: import `read_env_file` from `config.env_file` and replace `environ.Env.read_env(BASE_DIR / ".env", overwrite=False)` with `read_env_file(BASE_DIR / ".env")`. Keep `import environ`; `env = environ.Env(...)` still uses it.
- [x] 2.3 Verify the backend reads `.env` through the helper only: `grep -rn "read_env(" backend --include='*.py'` shows the call in `env_file.py` and the `read_env_file` uses only (tests excluded).
- [x] 2.4 Verify startup still loads `.env`: `uv run python backend/manage.py check` passes in this worktree, which has no `DJANGO_SECRET_KEY` outside `.env`.

## 3. Repository checks

- [x] 3.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 3.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 3.3 `RESCRIBO_E2E_API_PORT=8215 RESCRIBO_E2E_FRONTEND_PORT=5215 task e2e` passes. Record the counts for the PR.
- [x] 3.4 `task worker-check` passes: the worker loads settings, so it reads `.env` through the new helper.
- [x] 3.5 No dev server is left on 8215 or 5215.

## Workflow follow-up

- Archive this change in the PR that completes #215 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": the filter rewrites django-environ's own record instead of copying its parse rule; line number and file name only, no variable name; read errors other than a missing file now raise.
- PR Checks: the fix is covered by local tests, including a subprocess that checks real stderr. No provider is involved.
- PR Screenshots: "Not applicable: backend only".
