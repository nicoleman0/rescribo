# Proposal

Delivers #257.

## Why

Nobody has reviewed the production setup as a whole before the first public self-hosted release. The review found vulnerable dependencies in the lockfiles and gaps in the proxy's response headers.

## What Changes

- Bump `djangorestframework`, `certifi`, and `cryptography` in `uv.lock` to versions that fix known advisories. Raise the `cryptography` cap in `pyproject.toml` to `<51`.
- Refresh `frontend/package-lock.json` within the existing `package.json` ranges so `npm audit` reports no vulnerabilities.
- Set `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` in `proxy/Caddyfile` for every response, so the built frontend gets the same headers Django already sends for the API.
- Add HSTS to `proxy/Caddyfile` and silence Django's `security.W004`.
- Stop proxying `/admin`.
- Add a system check that fails a production start without a valid `RESCRIBO_CREDENTIAL_KEY`.
- Record each check and its finding in `design.md`, with follow-ups.

No requirement changes. `skip_specs: true`. HSTS, the unproxied `/admin`, and the new deploy check are operator-facing; no product requirement covers them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `pyproject.toml` (the `cryptography` line), `uv.lock`, `frontend/package-lock.json`, `proxy/Caddyfile`, `backend/config/settings.py`, `backend/connections/apps.py`, `docs/DEPLOYMENT.md`, ADR 0007.
- No API, schema, or migration changes. `marketing` and `rust/matcher` have no known advisories and do not change.
