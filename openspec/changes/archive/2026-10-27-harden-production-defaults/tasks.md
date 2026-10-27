# Tasks

## 1. Python dependencies

- [x] 1.1 In `pyproject.toml`, change only the `cryptography` line to `>=46,<51`. Run `uv lock --upgrade-package djangorestframework==3.18.2 --upgrade-package certifi --upgrade-package cryptography`. Verify `git diff uv.lock` changes only those three packages and the `cryptography` specifier.
- [x] 1.2 Run `uv export --frozen --no-hashes --no-emit-project --all-groups` into a scratch file and `uvx pip-audit -r <file> --no-deps --disable-pip`. Verify no vulnerabilities remain.

## 2. Frontend dependencies

- [x] 2.1 From `frontend`, run `npm audit fix --package-lock-only`, then `npm ci`. Verify `git diff --stat` touches only `frontend/package-lock.json` and `npm audit` reports 0 vulnerabilities.

## 3. Proxy headers

- [x] 3.1 In `proxy/Caddyfile`, add a site-level `header` block setting `Strict-Transport-Security "max-age=31536000"`, `X-Content-Type-Options nosniff`, `X-Frame-Options DENY`, and `Referrer-Policy same-origin`, with a short comment saying they match Django's API headers. Remove `/admin` and `/admin/*` from the `@backend` matcher. Verify with `docker run --rm -v "$PWD/proxy/Caddyfile:/etc/caddy/Caddyfile:ro" -e RESCRIBO_SITE_ADDRESS=localhost caddy:2.11-alpine caddy validate --config /etc/caddy/Caddyfile`.
- [x] 3.2 In `backend/config/settings.py`, set `SILENCED_SYSTEM_CHECKS = ["security.W004"]` with a one-line reason.
- [x] 3.3 In `docs/DEPLOYMENT.md`, update only the HSTS bullet and the proxy row's `/admin` mention. In ADR 0007, drop `/admin` from the forwarded paths and HSTS from the open list.

## 4. Credential key check

- [x] 4.1 Add `backend/connections/apps.py` with a system check, `connections.E001`, that fails when debug is off and `RESCRIBO_CREDENTIAL_KEY` is not a valid Fernet key. Reuse `connections.credentials.cipher`.
- [x] 4.2 Test an empty key, an invalid key, a valid key, and debug on.

## 5. Repository checks

- [x] 5.1 `task check test build schema-check` passes with PostgreSQL and Redis running.
- [x] 5.2 `RESCRIBO_E2E_API_PORT=8257 RESCRIBO_E2E_FRONTEND_PORT=5257 task e2e` passes.
- [x] 5.3 `npx @fission-ai/openspec validate --all --strict` passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
- Put the review tables from `design.md` in the PR body under Decisions to review.
