# Tasks

Delivers #219. Tooling; `skip_specs: true`. Change only `backend/config/env_file.py` (moved), `backend/env_file.py`, `backend/config/settings.py`, `backend/tests/test_env_file.py`, and the eight scripts named in proposal.md. Do not touch `backend/config/__init__.py`, `pyproject.toml`, `backend/tests/test_github_private_key.py`, `docs/`, the frontend, or `openspec/specs/`.

Run backend tests with `task test-backend` (it builds the matcher first), or `uv run pytest backend/tests/test_env_file.py` for this file alone.

## 1. Move the helper

- [x] 1.1 In `backend/tests/test_env_file.py`, change both imports of `config.env_file` to `env_file` (the module import and the one inside the subprocess command). In the subprocess command, after the read, add `assert 'config' not in sys.modules and 'celery' not in sys.modules`. Run `uv run pytest backend/tests/test_env_file.py` and verify it fails at collection with `ModuleNotFoundError: No module named 'env_file'`.
- [x] 1.2 `git mv backend/config/env_file.py backend/env_file.py`. Do not change its contents. In `backend/config/settings.py`, change `from config.env_file import read_env_file` to `from env_file import read_env_file`. Run `uv run pytest backend/tests/test_env_file.py` and verify 6 passed.
- [x] 1.3 Verify the subprocess assert bites: temporarily add `import config` to the top of `backend/env_file.py`, run the subprocess test, and verify it fails on the `sys.modules` assert. Revert.
- [x] 1.4 Verify settings still load `.env` through the helper: `uv run python backend/manage.py check` passes (this worktree has no `DJANGO_SECRET_KEY` outside `.env`).

## 2. Guard

- [x] 2.1 Add `test_only_the_helper_reads_env_files()` to `backend/tests/test_env_file.py`. Find the repository root as `Path(__file__).resolve().parents[2]`. Collect every `*.py` under `scripts/` and `backend/`, skipping `backend/env_file.py` and anything under `backend/tests/`. Assert the list of paths (relative to the root) whose text contains `read_env(` is empty. Run it and verify it fails, listing the eight scripts and nothing else.

## 3. Scripts

Replace each `environ.Env.read_env(<path>, overwrite=False)` with `read_env_file(<path>)` on the same line, and remove `import environ`. Do not move any read.

- [x] 3.1 `check_github_installation.py` and `check_github_issue_lifecycle.py`: add `from env_file import read_env_file  # noqa: E402` after the `sys.path.insert` line and before the two reads. The reads stay before `from integrations...`.
- [x] 3.2 `list_slack_channels.py`: add `from env_file import read_env_file  # noqa: E402` with the other backend imports after the `sys.path.insert` line. The read stays at module level after the imports.
- [x] 3.3 `eval_matcher.py`: add `from env_file import read_env_file  # noqa: E402` with its other backend imports.
- [x] 3.4 `eval_baseline.py`, `eval_generate.py`, `eval_review_model.py`: add `import sys` if missing, then directly after the `REPOSITORY_ROOT = ...` line add `sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))` and `from env_file import read_env_file  # noqa: E402`.
- [x] 3.5 `eval_jev.py`: add `import sys`. After its import block (it imports `REPOSITORY_ROOT` from `eval_baseline`), add `sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))` and `from env_file import read_env_file  # noqa: E402`. Inside the sorted import block, ruff's isort would put `env_file` above `eval_baseline`, before anything has put `backend` on the path.
- [x] 3.6 Run the guard test and verify it passes. Run `grep -rn "import environ" scripts` and verify no output.
- [x] 3.7 Verify every script still imports: `uv run python scripts/<name>.py --help` exits 0 for `check_github_installation`, `check_github_issue_lifecycle`, `eval_baseline`, `eval_generate`, `eval_jev`, `eval_matcher`, and `eval_review_model`.
- [x] 3.8 Verify `list_slack_channels.py` imports and reads: `test ! -e .env.slack-feasibility` first (stop and ask if it exists), then `env -u RESCRIBO_SLACK_BOT_TOKEN uv run python scripts/list_slack_channels.py` exits with `Set RESCRIBO_SLACK_BOT_TOKEN before running this check.` and no traceback.
- [x] 3.9 Verify the redaction end to end in a script: `test ! -e .env.github-feasibility` first (stop and ask if it exists). Write `.env.github-feasibility` in the worktree root with the `ENV_TEXT` value from `test_env_file.py`. Run `uv run python scripts/check_github_installation.py --help`. Verify stderr has `Skipped invalid line 3 in .env.github-feasibility. Its value is not logged.` and line 4, and none of `secretbodymarker`, `secretendmarker`, `END RSA`. Delete the file. Record the two lines for the PR.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.switchyard/brief.md`; do not start or stop services). Record the test counts. `schema-check` reports no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8219 RESCRIBO_E2E_FRONTEND_PORT=5219 task e2e` passes. Record the counts.
- [x] 4.4 `task worker-check` passes: the worker loads settings, which now import the helper from its new home.
- [x] 4.5 No dev server is left on 8219 or 5219, and `.env.github-feasibility` does not exist in the worktree.

## Workflow follow-up

- Archive this change in the PR that completes #219 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": helper moved to top-level `backend/env_file.py` instead of changing `config/__init__.py`; four eval scripts gain a `sys.path` insert; the guard is a source-scan test, not a ruff rule.
- PR Checks: local tests plus the end-to-end script run from 3.9. No provider is involved.
- PR Screenshots: "Not applicable: backend and scripts only".
