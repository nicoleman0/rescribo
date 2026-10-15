# Tasks

## 1. Key loader

- [x] 1.1 Add `backend/integrations/github_app/private_key.py` with `load_private_key(value: str) -> str` as in design.md. Verify with new tests in `backend/tests/test_github_private_key.py`, using keys generated at runtime: PKCS#1 and PKCS#8 multi-line keys load; the one-line `\n` form returns the same text as the multi-line form; empty and whitespace-only values return `""`; a truncated first line, random text, an encrypted RSA key, and an EC key each raise `ImproperlyConfigured` whose message names `RESCRIBO_GITHUB_PRIVATE_KEY` and contains no line of the key and no `__cause__`.
- [x] 1.2 Add env-file tests in the same file. For the exact lines documented in task 3.1 and 3.2, and for the unquoted, single-quoted, and double-quoted one-line forms, write a temporary `.env`, read it with `environ.Env.read_env` into a patched `Env.ENVIRON` dict, and assert `load_private_key` returns a key that signs with `create_app_jwt`.

## 2. Startup wiring

- [x] 2.1 In `backend/config/settings.py`, change only the `RESCRIBO_GITHUB_PRIVATE_KEY` line to call `load_private_key` and add its import. Verify `uv run python backend/manage.py check` still passes with no key set.
- [x] 2.2 Add a subprocess test that runs `django.setup()` with `RESCRIBO_GITHUB_PRIVATE_KEY` set to a truncated key. Assert a non-zero exit, `RESCRIBO_GITHUB_PRIVATE_KEY` in stderr, and no key body line in stderr. Add a passing case with a valid one-line key.
- [x] 2.3 Check `test_settings_providers.py` and the other GitHub tests still pass unchanged; they set the key through `override_settings` or mocks and do not go through the loader.

## 3. Docs

- [x] 3.1 In `docs/SETTINGS.md`, replace "(PEM text)" with a short entry for `RESCRIBO_GITHUB_PRIVATE_KEY`: the two accepted forms, a one-line example made with `awk 'NF {printf "%s\\n", $0}' key.pem` (or the equivalent the implementer verifies), the note not to put a multi-line value in `.env`, that empty means not configured, and that a bad value stops startup. Verify by running the documented command on a generated key and loading the result through task 1.2's test.
- [x] 3.2 In `.env.production.example`, show the one-line form as a placeholder, for example `RESCRIBO_GITHUB_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----`, with a one-line comment pointing at `docs/SETTINGS.md`. Verify the line is covered by task 1.2.
- [x] 3.3 In `docs/PROVIDER_SETUP.md` step 7, replace the per-process `$(cat ...)` block and the #168 note with: keep the `.pem` outside the repository with mode 600, set `RESCRIBO_GITHUB_PRIVATE_KEY` in `.env` in the one-line form from `docs/SETTINGS.md`, and run `task api` and `task worker`. In step 8.3, drop "with `RESCRIBO_GITHUB_PRIVATE_KEY` set". Leave `RESCRIBO_GITHUB_PRIVATE_KEY_PATH` in the live check docs alone. Verify with `git grep -n 'cat <path-to-pem>\|#168' docs/` returning nothing.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running. `schema-check` reports no contract change. Record the test counts for the PR.
- [x] 4.3 `task worker-check` passes, since worker startup now runs the loader.

## Workflow follow-up

- Archive this change in the PR that completes #168 (`/opsx:archive`).
- The PR closes #168. Milestone: G. Manual check findings.
- No browser or API change, so no e2e run and no screenshots.
