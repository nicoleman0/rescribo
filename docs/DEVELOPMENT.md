# Architecture and development conventions

## Repository layout

```text
backend/config/       Django settings, routes, ASGI/WSGI, Celery bootstrap
backend/feedback/     Workspace-scoped reports, problems, and activity
backend/health/       Dependency checks and worker smoke task
backend/tests/        Backend tests
frontend/src/api/     API calls and generated TypeScript contract
frontend/src/features/ Product screens grouped by feature (inbox first)
frontend/src/test/    Component test setup
frontend/e2e/         Browser tests against the real local API
scripts/              Local bootstrap and service verification
docs/MVP_SPEC.md      Product scope, architecture, and acceptance criteria
```

Other business modules will be added as their workflows are implemented. The spec defines their responsibilities; empty placeholder applications are not needed to establish the boundaries.

## Accounts boundary

`accounts.tokens` owns framework-free secret generation, digest checks, and expiry. `accounts.services` owns transactions and invariants. HTTP views and Celery tasks pass an explicitly resolved active `Membership` to every mutating use case; they never pass a bare user or workspace ID. Workspace permissions resolve membership on each request and hide foreign workspaces with 404. Workers must resolve and pass the actor membership too.

Use management commands for reading or writing product rows. Use `scripts/` CLIs for credential handling and provider checks that do not use the product ORM. Sessions remain in PostgreSQL. Membership is rechecked per workspace request; `session_generation` revokes all sessions after password changes or the last membership is revoked. Browser writes use CSRF tokens; `SameSite=Lax` applies to both session and CSRF cookies.

## Feedback boundary

`feedback` owns report and problem records, transitions, provenance, and activity. Mutations take a resolved active `Membership`, scope reads and references to its workspace, and check row versions under a transaction. HTTP handlers and workers should call these use cases. Activity metadata records field names and state or ID changes, not customer content.

`feedback.inbox` owns inbox reads. It applies the workspace filter before search and filters, so a foreign report is never counted or matched. Manual capture calls `submit_report` with no source snapshot, the same use case Slack capture uses.

## Shared contracts

DRF serializers and drf-spectacular define the API contract. `task schema` generates `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`. Frontend callers import those types and validate untrusted response values where needed. The browser uses relative `/api/` URLs; Vite proxies to Django without requiring permissive CORS settings.

Future mutating browser calls must send the CSRF token with session cookies. The current readiness request is read-only and does not establish a product login flow.

## Runtime boundaries

- Django owns permissions, validation, transactions, and domain state.
- React owns presentation and interaction. TanStack Query owns server-state caching; React Router owns navigation.
- Celery executes background work; Redis is its broker/result backend. PostgreSQL remains the future business-operation source of truth.
- Provider SDKs and HTTP clients live behind integration modules. Do not put provider payloads into the core workflow API.
- Use shared application functions for operations invoked by both web requests and workers.

The environment includes Slack SDK, HTTPX, and cryptography dependencies for the next milestone. No provider app is registered and no live outbound business action exists yet.

## Version choices

- Python 3.14, Django 5.2 LTS, and Node.js 24.
- Host development workers use Celery's `solo` pool. The macOS/Python 3.14 process pool failed the task round-trip check during setup; Linux container workers are verified separately with the configured process pool.
- React and Vite versions are resolved in the npm lockfile.
- TypeScript 5.9 is intentional: the selected OpenAPI type generator currently declares a TypeScript 5 peer requirement. Upgrade them together after checking compatibility.
- Ruff, mypy, Oxlint, TypeScript, and Prettier run locally and in CI.
- PostgreSQL 17 and Redis 7 images are development dependencies; the image tags track their series. Lockfiles pin application packages. A production deployment needs a separate reviewed image/update policy.

## Test boundaries

The readiness test uses real PostgreSQL and Redis. Failure tests inject dependency errors and assert that responses do not expose internals. Component tests isolate browser presentation. Playwright checks the real browser -> Vite proxy -> Django -> PostgreSQL/Redis path. The worker smoke script exercises Redis and an actual worker separately.

This environment does not implement the full MVP's tenant isolation, durable operations, provider authentication, AI evaluation, or production hardening. Those requirements remain in the spec and must be tested with their corresponding features.

## Frontend screenshots

The shell screenshots capture the Problems placeholder so live inbox data
cannot change them. The UI foundation screenshot baselines are generated with Playwright Chromium
at 1280px desktop and 375px mobile widths. The macOS files are the reviewed
local baselines. Linux files are also committed because Playwright includes
the host platform in snapshot names and CI runs on Ubuntu.

Update the local baselines only after reviewing the rendered shell and gallery
at both sizes:

```sh
cd frontend
npx playwright test e2e/ui-foundation.spec.ts --update-snapshots
```

The Linux files must match the CI runner's font rendering and browser build.
When a Linux screenshot check fails in CI, the run uploads a
`playwright-screenshot-diffs` artifact with the rendered `-actual.png` files.
Review those images before committing them as the new baselines.
