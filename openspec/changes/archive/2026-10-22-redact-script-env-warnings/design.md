# Design

## Context

See proposal.md for the leak. The helper and its reasons are in the archived change `openspec/changes/archive/2026-10-15-redact-env-warnings/design.md`. Facts this design relies on:

- `backend/config/__init__.py` imports `.celery`, which sets `DJANGO_SETTINGS_MODULE` and builds the Celery app. Checked: from `backend`, `import config.env_file` leaves `celery` in `sys.modules`.
- `backend/config/env_file.py` imports only `io`, `logging`, `pathlib`, and `environ`.
- `backend` is on `sys.path` for `manage.py` (its own directory), gunicorn (`--chdir backend`), and Celery (`--workdir=backend`). The image copies `backend/` whole, for pytest (`pythonpath = ["backend", "scripts"]`), and for mypy (`mypy_path = "backend"`). Ruff treats `backend` as first-party (`src`).
- Scripts run as `uv run python scripts/<name>.py`, so `sys.path[0]` is `scripts/`. Five of the eight scripts put `backend` on `sys.path` themselves: `check_github_installation.py`, `check_github_issue_lifecycle.py`, `list_slack_channels.py`, `eval_matcher.py`, and `eval_jev.py` through its import of `eval_matcher`. `eval_baseline.py`, `eval_generate.py`, and `eval_review_model.py` do not.
- The two `check_github_*` scripts read `.env` and `.env.github-feasibility` at module level, before importing `integrations`. `list_slack_channels.py` reads `.env.slack-feasibility` at module level, after its imports. The five eval scripts read `.env` inside `main()`.
- No script uses `environ` for anything but `read_env`.

## Goals / Non-Goals

**Goals:**
- One helper, one home, imported by settings and scripts alike.
- Importing the helper has no side effects.
- Each script reads the same files at the same point as today.

**Non-Goals:**
- Changing the helper's behaviour: `overwrite=False`, a missing file is skipped, the message names the line number and file name.
- Changing `backend/config/__init__.py` or how the Celery app loads.
- Other secret handling in the scripts.

## Decisions

**Move the helper to `backend/env_file.py`.** A top-level module on the path every caller already has. No package `__init__` runs, so importing it loads only `environ`. `git mv` keeps its history. Settings changes one import; no copy and no re-export stays in `config`.

Alternatives:
- A package such as `backend/envfiles/__init__.py`. Same effect, one more directory for one function.
- Make `config/__init__.py` import Celery lazily. That file is shared, the Celery import is how Django loads the worker app, and the worker wiring would need its own checks. Out of the paths this issue owns.
- Put the helper in `scripts/`. The production image copies only `backend/`, so settings could not import it.
- Keep `config/env_file.py` and re-export it from a new module. Two names for one function.

**Scripts put `backend` on `sys.path` before importing the helper.** Each script that imports the helper inserts the path itself, instead of relying on another script's import side effect. `eval_baseline.py`, `eval_generate.py`, `eval_review_model.py`, and `eval_jev.py` add `sys.path.insert(0, str(REPOSITORY_ROOT / "backend"))` after `REPOSITORY_ROOT` is defined or imported, then `from env_file import read_env_file  # noqa: E402`, as the other four scripts already do for backend imports. `eval_jev.py` cannot put the import in its sorted block: isort places `env_file` above `eval_baseline`, before any path insert has run. The repeated insert line is existing practice in six scripts; a shared bootstrap module for it is out of scope.

**Keep each read where it is.** Each `environ.Env.read_env(X, overwrite=False)` becomes `read_env_file(X)` on the same line. In the `check_github_*` scripts, `from env_file import read_env_file  # noqa: E402` goes after the `sys.path` insert and before the two reads, so the reads still run before `integrations` is imported. In `list_slack_channels.py` it joins the backend imports.

**Guard with a test that scans source.** `test_only_the_helper_reads_env_files` in `backend/tests/test_env_file.py` collects every `*.py` under `scripts/` and `backend/`, skips `backend/env_file.py` and `backend/tests/`, and asserts none contains `read_env(`. The failure lists the offending paths. It runs in `task test`, catches both `environ.Env.read_env` and `env.read_env` on an instance, and needs no shared config. Backend tests are excluded because `test_github_private_key.py` calls django-environ directly to test its parsing.

Alternative: ruff `flake8-tidy-imports` banned-api on `environ.Env.read_env` with a per-file ignore for the helper. Prototyped on ruff 0.16.8: it flags `environ.Env.read_env(...)` and `Env.read_env(...)` after `from environ import Env`, and misses `env.read_env(...)` on an instance. It shows in the editor, but needs a `pyproject.toml` change (shared) and misses the instance form. Question 1 in the plan summary.

**Assert the helper's import is side-effect free.** The existing subprocess test changes its import to `from env_file import read_env_file` and also asserts that `config` and `celery` are not in `sys.modules` afterwards. This fails if the helper moves back under `config` or gains a Django or Celery import.

## Risks / Trade-offs

- [A top-level module named `env_file` could clash with an installed distribution of the same name] → None in `uv.lock`. `backend` is first on `sys.path` for the scripts that insert it, and the test checks the import.
- [Text scan is crude: a comment or string containing `read_env(` fails it] → The failure names the file. A false positive costs one rename; a false negative would leak a secret.
- [The leak returns through a new script that calls `os.environ` loading in another way, such as `python-dotenv`] → Out of scope. `python-dotenv` is not a dependency.
- [Script behaviour on read errors changes] → As in #215: a missing file is skipped as before; other `OSError`s now raise instead of being logged at `info` and ignored.
