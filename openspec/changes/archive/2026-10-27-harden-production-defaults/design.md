# Design

## Context

Production runs from `compose.prod.yaml` behind Caddy ([ADR 0007](../../../docs/adr/0007-single-host-deployment.md)). `compose.prod.yaml` and the Dockerfiles belong to #252, so findings there are described, not fixed.

## Review findings

Configuration, checked against `backend/config/settings.py`, `compose.prod.yaml`, `.env.production.example`, and `proxy/Caddyfile`.

| Check | Finding | Action |
| --- | --- | --- |
| Debug | `DJANGO_DEBUG` defaults to false; compose forces `"False"`. | None |
| Secret key | Placeholder rejected when debug is off; empty key fails in Django. | None |
| `manage.py check --deploy` | With production-shaped placeholder values, only `security.W004` (HSTS) is raised. | Silence W004; Caddy sets HSTS |
| Session cookie | HTTP-only, `Lax`, secure when debug is off. | None |
| CSRF cookie | Readable by the SPA by design, `Lax`, secure when debug is off. | None |
| SSL redirect | On when debug is off. Caddy also redirects HTTP. | None |
| HSTS | Not set. ADR 0007 and `docs/DEPLOYMENT.md` leave it open. | Set in Caddyfile, `max-age=31536000`, no `includeSubDomains` or `preload` |
| Other headers | Django sends nosniff, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` on API responses. The SPA served by Caddy gets none. | Fix in Caddyfile |
| Content-Security-Policy | None anywhere. | Follow-up #259 |
| Allowed hosts, CSRF origins | Compose derives both from `RESCRIBO_DOMAIN`. | None |
| Proxy trust | `RESCRIBO_NUM_PROXIES=1`; `SECURE_PROXY_SSL_HEADER` only set when it is. Caddy replaces client `X-Forwarded-*` because no `trusted_proxies` is set. | None |
| Published ports | Only Caddy. Postgres and Redis stay on the compose network. | None |
| Database password | Compose requires `POSTGRES_PASSWORD`. | None |
| Admin | `/admin` is proxied publicly. No models are registered and `bootstrap_owner` creates no staff user. The admin login has no throttle. | Drop `/admin` from the Caddy matcher; removing the app is #258 |
| Credential key | Empty or invalid `RESCRIBO_CREDENTIAL_KEY` passes startup; Slack connect fails later with an operator message. | System check `connections.E001` when debug is off |
| Secrets in images | `.dockerignore` excludes `.env` and `.env.*`. Backend runs as uid 10001. | None |
| Access logs | Caddy writes none, by design (OAuth codes in query strings). | None |
| `.env.production.example` | Lists every secret the docs require. No real values. | None |
| Public schema | `/api/schema/` is unauthenticated. The project is open source, so it reveals nothing new. | None |

Dependencies, audited on 2026-10-26.

| Ecosystem | Tool | Finding | Action |
| --- | --- | --- | --- |
| Python | `pip-audit` 2.10.1 on `uv export --all-groups` | `djangorestframework` 3.18.1: GHSA-33wh-fxxf-88vv (Accept header DoS), GHSA-3547-9m27-7rxg (memory amplification), GHSA-xw6w-gcfp-cf8m (TokenProxy, not used). Fixed in 3.18.2. | Lock 3.18.2 |
| Python | same | `certifi` 2026.7.22: GHSA-6q48-6c7w-9gw2 (compromised eMudhra intermediates). Fixed in 2026.10.18. | Lock latest |
| Python | same | `cryptography` 48.0.1: GHSA-m2h6-j472-rp4c, GHSA-jwv3-5hgf-82ww (X.509 verification, fixed 49.0.0), GHSA-g6cj-pr64-35w5 (PKCS7 decrypt, fixed 50.0.0). Rescribo uses Fernet and RSA signing only, so none is reachable. `pyproject.toml` caps it at `<49`. | Raise cap to `<51`, lock 50.x |
| npm, `frontend` | `npm audit` | 12 (7 high, 5 moderate): vite, shadcn, zod, undici, source-map-js, body-parser, hono, fast-uri, ip-address, `@modelcontextprotocol/sdk`, vitest, `@vitest/mocker`. All are build or dev tools; production ships only the static `dist`. All fixable within current ranges. | `npm audit fix --package-lock-only` |
| npm, `marketing` | `npm audit` | 0 | None |
| Rust, `rust/matcher` | `cargo audit` is not installed. Queried the OSV batch API for all 11 crates.io packages in `Cargo.lock`. | 0 | None |

## Goals / Non-Goals

**Goals:** clear known advisories with the smallest lockfile bumps, give the SPA the headers the API already has plus HSTS, stop proxying the admin, and fail deploys that have no usable credential key.

**Non-Goals:** general upgrades, `package.json` edits and `pyproject.toml` edits beyond the `cryptography` line (#254 owns their version fields), compose or Dockerfile edits (#252), a CSP, removing the admin app (#258).

## Decisions

- **Headers live in Caddy at site level.** One place covers the SPA and the API. Values match Django's (`nosniff`, `DENY`, `same-origin`), so proxied API responses do not change. Alternative: scope to the SPA `handle` only. Rejected because two homes for the same rule drift.
- **`certifi` goes to the latest release, not the minimum fix.** It is a CA bundle, and each release only removes or adds trust data. `djangorestframework` takes the minimum fix, 3.18.2.
- **npm fixes are lockfile-only.** `npm audit fix --package-lock-only` stays within `package.json` ranges, so `package.json` is untouched.
- **Rust audited through OSV.** Installing `cargo-audit` compiles a tool for 11 crates. OSV includes the RustSec database.
- **HSTS lives in Caddy, and Django's W004 is silenced.** Caddy answers every request, including the SPA, which Django never sees. Without `includeSubDomains` or `preload`, the header binds only this host and expires after a year.
- **`/admin` is no longer proxied; the app stays installed.** No models are registered and no staff user exists. Removing the app touches settings, URLs, and static handling, so it is #258.
- **The credential key check is an error only when debug is off.** It reuses `connections.credentials.cipher`, so one function decides what a valid key is. `.env.example` has no key and local setups without Slack must keep working, the same rule `DJANGO_SECRET_KEY` follows. `migrate` runs system checks, so `task prod-up` stops before the containers restart.
- **`cryptography` cap raised to `<51`.** 50.x fixes all three advisories. Only that dependency line in `pyproject.toml` changes.

## Risks / Trade-offs

- [`Referrer-Policy: same-origin` on the SPA stops sending the Rescribo origin to GitHub and Slack links] → Nothing in Rescribo depends on it. It matches the API today.
- [Lockfile bumps change build tooling (vite, vitest)] → `task check test build` and `task e2e` run on the result.

## Follow-ups

Opened by the coordinator:

1. #258 Remove `django.contrib.admin`.
2. #259 Content-Security-Policy for the SPA.
3. #260 Dependency audit in CI.
4. #261 Run `manage.py check --deploy` before production starts.
