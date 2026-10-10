# Deployment

Run Rescribo on one Docker host with [`compose.prod.yaml`](../compose.prod.yaml).
Provider setup is in [SETTINGS.md](SETTINGS.md). The development stack is in
[LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md).

Checked on 2026-10-07 on `https://localhost` with Caddy's local CA: readiness,
app routes, admin static files, HTTP to HTTPS redirect, sign-in with secure
cookies, worker ping, scheduler start, backup, restore, and owner recovery.
It has not yet run on a public domain.

| Service | Image | Role |
| --- | --- | --- |
| `proxy` | `proxy/Dockerfile` | Caddy. Terminates HTTPS, serves the built frontend, forwards `/api`, `/admin`, `/static`. Only service with published ports. |
| `backend` | `backend/Dockerfile`, `production` target | gunicorn running Django |
| `worker`, `scheduler` | same image | Celery worker and beat |
| `postgres`, `redis` | upstream | Data in named volumes |

## Requirements

- A Linux host with Docker Engine, Compose, and [Task](https://taskfile.dev).
- A DNS record for your domain pointing at the host.
- Ports 80 and 443 reachable from the internet. Caddy needs them to obtain and
  renew certificates.

## First deployment

1. Clone the repository on the host. Images build from source.
2. Create the configuration:

   ```sh
   cp .env.production.example .env.production
   chmod 600 .env.production
   ```

   Set `RESCRIBO_DOMAIN` to the bare host name, for example
   `rescribo.example.com`. Compose derives the allowed host, CSRF origin,
   public base URL, and certificate name from it. Generate the secrets:

   ```sh
   openssl rand -hex 32   # DJANGO_SECRET_KEY
   openssl rand -hex 16   # POSTGRES_PASSWORD
   python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'   # RESCRIBO_CREDENTIAL_KEY (Fernet)
   ```

   Back up `RESCRIBO_CREDENTIAL_KEY` separately from database dumps. Without it,
   stored Slack tokens cannot be decrypted.
3. Build, migrate, and start:

   ```sh
   task prod-up
   curl https://rescribo.example.com/api/health/ready/
   ```

4. Create the first owner. Enter the password at the prompt:

   ```sh
   task prod-manage -- bootstrap_owner --email you@example.com --full-name 'Your Name' --workspace-name 'Acme' --workspace-slug acme
   ```

5. Register the Slack and GitHub Apps against `https://<RESCRIBO_DOMAIN>` and
   add their keys to `.env.production` ([SETTINGS.md](SETTINGS.md)). Run
   `task prod-up` again to apply them.

Optional: `task prod-manage -- seed_demo` adds the fictitious demo workspace.

## HTTPS and the proxy

- Caddy gets and renews certificates from Let's Encrypt. They live in the
  `caddy-data` volume. Keep it: reissuing on every deploy hits rate limits.
- Compose sets `RESCRIBO_NUM_PROXIES=1`, so Django trusts Caddy's
  `X-Forwarded-Proto` and `X-Forwarded-For`. Do not publish the backend port.
  If you add a load balancer in front of Caddy, raise the count and set Caddy's
  `trusted_proxies`.
- Caddy writes no access log, because provider callbacks carry OAuth codes in
  query strings. Keep it that way if you add logging.
- HSTS is not set. Once the domain is settled, add
  `header Strict-Transport-Security "max-age=31536000"` to `proxy/Caddyfile`.
  Browsers keep this setting until it expires, so changing your mind later is slow.

## Operations

| Task | Command |
| --- | --- |
| Update | `task prod-backup`, then `git pull` and `task prod-up` (rebuilds, migrates, restarts) |
| Stop, keeping data | `task prod-stop` |
| Logs | `docker compose -f compose.prod.yaml --env-file .env.production logs -f backend worker` |
| Management command | `task prod-manage -- <command>` |

## Backup and recovery

`task prod-backup` writes a `pg_dump` custom-format file to `backups/`. Copy it
off the host. Retention rules are in [SETTINGS.md](SETTINGS.md#backup-and-restore).

To restore, stop everything except the database, recreate it, and load the dump:

```sh
P='docker compose -f compose.prod.yaml --env-file .env.production'
$P stop backend worker scheduler proxy
$P exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
$P exec -T postgres sh -c 'pg_restore --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < backups/<file>.dump
task prod-up
```

The restored database needs the same `RESCRIBO_CREDENTIAL_KEY` it was written with.

If an owner loses their password, `task prod-manage -- issue_owner_recovery --email <owner>`
prints a one-use reset link on the public origin. Treat it as a credential.

## Development tunnels

Use a tunnel to try live Slack and GitHub against the development stack. Debug
mode stays on, so this is for disposable workspaces only.

The full procedure, including a stable tunnel origin, `RESCRIBO_NUM_PROXIES`,
and both app registrations, is in [Provider app setup](PROVIDER_SETUP.md).
