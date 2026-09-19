# Architecture and development conventions

## Repository layout

```text
backend/config/       Django settings, routes, ASGI/WSGI, Celery bootstrap
backend/health/       Dependency checks and worker smoke task
backend/tests/        Backend tests
frontend/src/api/     API calls and generated TypeScript contract
frontend/src/test/    Component test setup
frontend/e2e/         Browser tests against the real local API
scripts/              Local bootstrap and service verification
docs/MVP_SPEC.md      Product scope, architecture, and acceptance criteria
```

Business modules will be added as their workflows are implemented. The spec defines their responsibilities; empty placeholder applications are not needed to establish the boundaries.

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
