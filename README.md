# Rescribo

An internal inbox connecting customer feedback, engineering issues, and employee follow-up.

**Current state:** development environment only. Slack/GitHub integrations and product workflows are specified but not implemented.

- [MVP specification](docs/MVP_SPEC.md)
- [Development setup plan](docs/DEV_SETUP_PLAN.md)
- [Architecture and conventions](docs/DEVELOPMENT.md)

## Requirements

- Python 3.14 and uv.
- Node.js 24 and npm.
- Docker Desktop or Docker Engine with Compose.
- [Task](https://taskfile.dev) (`brew install go-task`).
- ShellCheck (`brew install shellcheck`), used by `task check`.

Toolchain versions are recorded in `.python-version` and `.node-version`. Python dependencies are locked in `uv.lock`; frontend dependencies in `frontend/package-lock.json`.

## Start developing

From the repository root:

```sh
task install
task services
task migrate
task browsers
```

`task install` creates a private `.env` with random local secrets if one does not exist. It preserves existing configuration. Do not copy real credentials into `.env.example`.

Run these in separate terminals:

```sh
task api
task web
task worker
task scheduler
```

Open [the frontend](http://127.0.0.1:5173). Its status page checks the API, PostgreSQL, and Redis through Vite's same-origin proxy. `task worker-check` separately verifies a real Celery task round trip.

The host worker uses Celery's single-process `solo` pool for portable local debugging. The container worker uses a two-process pool. The scheduler has no business schedules yet. It is wired for the reconciliation jobs described in the spec.

## Checks

```sh
task check          # Python lint/types, Django checks, frontend lint/types/format
task test           # Backend tests use real PostgreSQL and Redis; frontend component tests
task build          # Type-check and build frontend assets
task schema-check   # Verify committed OpenAPI and generated TS types are current
task e2e            # Start test web servers and check the browser-to-database path
task worker-check   # Requires a running worker
```

`task e2e` reuses local servers if they are already running. CI starts fresh servers. `task format` applies formatting. `task schema` regenerates API contracts.

## Containers for the whole stack

The normal workflow keeps Python and Node on the host for editor/debugger support and uses containers for PostgreSQL and Redis. To run the application processes in containers instead, stop any host API/frontend/worker processes first:

```sh
task app
task app-stop
```

`task app` builds images, applies migrations, and starts the API, frontend, worker, and scheduler. The Dockerfiles and development servers are for local development only. Rebuild after changing dependencies or frontend configuration; backend source and frontend `src`/`public` are mounted for editing.

## Configuration and data

| Service | Local address |
| --- | --- |
| Frontend | `http://127.0.0.1:5173` |
| API | `http://127.0.0.1:8000` |
| PostgreSQL | `127.0.0.1:55432` |
| Redis | `127.0.0.1:56379` |

All published container ports bind to loopback. The database credentials are generated in `.env`. Connections use `RESCRIBO_DATABASE_URL` and `RESCRIBO_REDIS_URL` to avoid inherited settings from other projects. PostgreSQL and Redis use named volumes. `task stop` / `task app-stop` preserve data. `docker compose down --volumes` deletes that data; use it only when intentionally resetting the environment.

Liveness is `/api/health/live/`. Readiness is `/api/health/ready/`; it reports availability without returning connection details. Future API routes default to authenticated access. The development health routes intentionally allow anonymous checks.

No app account is created by setup. For Django's development admin, run `uv run python backend/manage.py createsuperuser`. Product invitations and workspaces are not implemented yet.

Slack, GitHub, and model keys are not needed to start. The first product milestone is live integration feasibility using test apps and disposable data. Follow section 12 of the spec before claiming provider support.

Milestone A work is split by the issues in the [GitHub milestone](https://github.com/nicoleman0/rescribo/milestone/1). The opt-in [GitHub App installation check](docs/GITHUB_INSTALLATION_CHECK.md) covers the first issue without adding credentials to the application or repository.

## Troubleshooting

- **Docker unavailable:** start Docker Desktop, then run `task services` again.
- **Node engine mismatch:** select Node 24 with your version manager before installing dependencies. `.npmrc` rejects unsupported Node versions rather than silently accepting them.
- **Readiness fails:** check `docker compose ps`, run migrations, and check `.env` host/port values. Confirm no stale API process is using a different environment.
- **Port occupied:** stop the conflicting service or change the database/Redis ports and corresponding URLs in `.env`. Application ports are fixed in the initial Vite/Playwright/Compose setup; update those together if changing them.
- **Worker task times out:** run `task worker`, ensure its environment uses the same Redis URL, then retry `task worker-check`.
- **Dependency edits:** run `uv lock && uv sync`, or `npm install` inside `frontend`, then commit the changed manifests and lockfiles. Do not bypass peer-dependency errors with `--force`.
- **API type drift:** run `task schema` and review both generated files.
- **Browser missing:** run `task browsers`; Linux hosts may also need `npx playwright install --with-deps chromium` from `frontend`.

The project uses Django 5.2 LTS and a Vite React/TypeScript app. See the [Django release documentation](https://docs.djangoproject.com/en/5.2/releases/5.2/), [Vite guide](https://vite.dev/guide/), and [Celery's Django integration](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).
