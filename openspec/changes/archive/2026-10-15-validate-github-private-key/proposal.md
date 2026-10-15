# Proposal

## Why

Issue #168. `RESCRIBO_GITHUB_PRIVATE_KEY` has no documented format. The one-line forms that fit in an env file arrive with literal `\n`, so the key fails to parse. The `ValueError` comes from `load_pem_private_key` in `create_app_jwt`, at the first GitHub call, not at startup. A multi-line value in `.env` loads as its first line only.

## What Changes

- The key setting accepts PEM text with real newlines, or one line with literal `\n` between the PEM lines. Settings turn the escapes into newlines.
- When the key is set and is not an unencrypted RSA private key in PEM format, the API, worker, scheduler, and management commands fail at startup. The message names `RESCRIBO_GITHUB_PRIVATE_KEY` and the accepted forms. It never contains the key.
- An empty or whitespace-only value still means the GitHub App is not configured.
- `docs/SETTINGS.md` documents the accepted forms once. `.env.production.example` shows the one-line form. `docs/PROVIDER_SETUP.md` points at `docs/SETTINGS.md` and drops the per-process `$(cat ...)` workaround and the #168 note.
- No key-file variable. `RESCRIBO_GITHUB_PRIVATE_KEY_PATH` in the live check docs stays as it is; it belongs to the check scripts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-connection`: adds a requirement for the accepted key forms and the startup failure on a key that cannot be parsed.

## Impact

- `backend/integrations/github_app/`: a new private key loader and its tests.
- `backend/config/settings.py`: the GitHub key line calls the loader.
- Docs: `docs/SETTINGS.md`, `docs/PROVIDER_SETUP.md`, `.env.production.example`.
- Operators with a bad key that used to load now see a startup failure. That is the point of the change. No API, schema, or migration change.
