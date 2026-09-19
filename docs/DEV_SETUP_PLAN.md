# Development environment implementation plan

**Goal:** Make the approved Python/React stack runnable and testable locally, without implementing the product workflows.

**Architecture:** An isolated new repository with Django/DRF and Celery in `backend`, React/TypeScript in `frontend`, PostgreSQL and Redis in local Docker Compose. Keep the product specification in `docs/MVP_SPEC.md`.

**Scope:** Environment setup only. No live Slack/GitHub app registration, customer data, paid APIs, or product business logic.

## Tasks

- [x] Initialise Git, ignore secrets and generated files, and add repository guidance.
- [x] Create a locked uv environment, Django settings, Celery configuration, health endpoints, and backend tests.
- [x] Create a locked React/Vite environment with routing, query tooling, formatting/linting, component testing, and Playwright.
- [x] Configure PostgreSQL/Redis and optional containerised web/worker/scheduler/frontend services with health checks and loopback-only ports.
- [x] Add environment examples, local bootstrap, Task targets, generated API types, CI, and setup/troubleshooting documentation.
- [x] Install dependencies, run formatting/static checks/tests/build, apply real database migrations, verify the browser/API path and real Celery task execution.

## Verification

Run `task check`, `task test`, `task build`, `task schema-check`, and `task e2e` against the local services. Validate Compose, test backend readiness against PostgreSQL and Redis, and execute a health task through the worker. Record any unavailable checks rather than claiming success.

## Constraints

Use modular, maintainable code and shared typed contracts. Keep secrets in ignored `.env` files. Use supported pinned toolchains and commit lockfiles. Do not implement empty modules for future features. All accounts and integrations are future milestones in the MVP spec.
