# ADR 0007: Single-host Compose deployment behind Caddy

Status: accepted. Issue [#89](https://github.com/nicoleman0/rescribo/issues/89).

Rescribo deploys as one Docker Compose project on one host
([`compose.prod.yaml`](../../compose.prod.yaml)). Caddy terminates HTTPS, serves
the built frontend, and forwards `/api`, `/admin`, and `/static` to gunicorn.
The worker and scheduler run from the backend image. PostgreSQL and Redis run
beside them in named volumes.

The product is self-hosted, and no requirement yet calls for more than one
machine. Load has not been measured. Compose is already the development runtime, so production differs only
in images and settings. Kubernetes or a managed platform would add operations
work with no requirement behind it yet. The images are portable, so moving later
does not need code changes.

Caddy obtains and renews certificates itself, which removes a separate ACME
setup. Serving the frontend from the proxy keeps Node out of the runtime. Django
trusts forwarded headers only when `RESCRIBO_NUM_PROXIES` is set, so the
backend port must stay unpublished.

Open: HSTS, an image update policy for PostgreSQL, Redis, and Caddy, structured
logs, and off-host backups. A hosted multi-tenant service is a separate decision
(#92).
