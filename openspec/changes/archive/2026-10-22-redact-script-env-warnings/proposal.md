# Proposal

Delivers GitHub issue #219 (milestone G. Manual check findings). Follows #215.

## Why

Ten `environ.Env.read_env` calls in eight `scripts/` files print every `.env` line django-environ cannot parse, value included. Two of the scripts read `RESCRIBO_GITHUB_PRIVATE_KEY`, so a multi-line key prints its body. #215 fixed this for `backend/config/settings.py` with `config.env_file.read_env_file`, but the scripts cannot import it: importing `config` runs `config/__init__.py`, which builds the Celery app.

## What Changes

- Move the helper from `backend/config/env_file.py` to `backend/env_file.py`, a top-level module with no package `__init__` to run. Its behaviour does not change.
- `backend/config/settings.py` imports `read_env_file` from `env_file`.
- All ten script calls use `read_env_file`, with the same files and in the same place in each script. The four eval scripts that do not put `backend` on `sys.path` themselves gain that line. `import environ` leaves all eight scripts.
- `backend/tests/test_env_file.py` imports from the new home, checks that importing the helper loads neither `config` nor Celery, and fails if `read_env(` appears in `scripts/` or in backend code outside the helper.

No frontend, API contract, migration, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. How scripts log `.env` parse errors is tooling, not product behaviour.

## Impact

- `backend/env_file.py` (moved from `backend/config/env_file.py`), `backend/config/settings.py` (one import).
- `scripts/check_github_installation.py`, `check_github_issue_lifecycle.py`, `eval_baseline.py`, `eval_generate.py`, `eval_jev.py`, `eval_matcher.py`, `eval_review_model.py`, `list_slack_channels.py`.
- `backend/tests/test_env_file.py`.
- Not changed: `backend/config/__init__.py`, `pyproject.toml`, `backend/tests/test_github_private_key.py` (it calls django-environ directly on purpose, to test parsing), any other secret handling in the scripts.
