# Provider app setup

Register the GitHub App and Slack App against the development stack behind a
public tunnel: one ordered procedure from an empty `.env` to both apps ready
for workspace Settings. For production, follow steps 7 and 8 with the
production origin and skip the development tunnel steps. The variable
reference is in [SETTINGS.md](SETTINGS.md).

Debug mode stays on, so use disposable resources only: a throwaway Slack
workspace, GitHub account, and repository. Every value below is a placeholder;
never commit credentials, hostnames, or app IDs.

Provider form labels below are quoted from the 10 Oct 2026 manual check,
[issue #139](https://github.com/nicoleman0/rescribo/issues/139); providers may
rename them.

## 1. Install the development stack

Install and migrate as in [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md).
`task install` creates a private `.env` with random local secrets. Do not
start `task web`; the tunnel serves the built bundle instead (step 4).

## 2. Expose a stable HTTPS origin

Slack and GitHub must reach the stack over HTTPS, and the app registrations
keep the origin, so its hostname must survive restarts.

- The 10 Oct 2026 check (#139) used Tailscale Funnel on the frontend port,
  for example `tailscale funnel 5173`. Its hostname took about 20 minutes to
  resolve in public DNS; wait for DNS before registering the apps.
- `task slack-tunnel` opens a cloudflared quick tunnel to port 5173. Its
  hostname changes on every run, so every `.env` value and app URL below must
  be redone each time. Use it only for a throwaway check.

The rest of this guide calls the origin `<origin>` and its host
`<tunnel-host>`, so `<origin>` is `https://<tunnel-host>`.

## 3. Set the base environment

In `.env`, keep the local entries and add the tunnel values:

```sh
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver,backend,frontend,<tunnel-host>
DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://frontend:5173,<origin>
RESCRIBO_PUBLIC_BASE_URL=<origin>
RESCRIBO_NUM_PROXIES=1
```

`RESCRIBO_NUM_PROXIES=1` makes Django trust the tunnel's `X-Forwarded-Proto`
header, so requests keep their HTTPS scheme.

Generate `RESCRIBO_CREDENTIAL_KEY` as described in
[SETTINGS.md](SETTINGS.md#operator-setup), then back it up away from the
database.

## 4. Serve the built bundle

Do not expose the Vite development server through the tunnel. In the 10 Oct
2026 check (#139) a cold page load through the tunnel took 21 to 22 s (110
requests, 14.3 MB) against 0.8 s locally; the built bundle on the same port
took 1.3 s (6 requests, 0.19 MB).

From `frontend/`:

```sh
npm run build
RESCRIBO_TUNNEL_HOST=<tunnel-host> npm run preview -- --port 5173
```

`vite preview` reuses the dev server's `/api` proxy and allowed hosts from
`vite.config.ts`; `RESCRIBO_TUNNEL_HOST` names the tunnel host Vite may serve.

## 5. Start the application processes

In separate terminals from the repository root:

```sh
task api
task worker
task scheduler
```

## 6. Create the owner and read the workspace ID

```sh
task bootstrap-owner
```

Sign in at `<origin>`, then open `<origin>/api/auth/session/` in the same
browser. Each entry in `memberships` carries its workspace as `workspace.id`;
this guide calls it `<workspace-id>`.

## 7. Register the GitHub App

Create the app under **Developer settings > GitHub Apps > New GitHub App**,
fields in form order:

1. **GitHub App name**: any unique name.
2. **Homepage URL**: `<origin>`.
3. **Callback URL**: GitHub labels this field "Redirect URI". Enter
   `<origin>/api/workspaces/<workspace-id>/connections/github/callback/`.
   The path carries the workspace ID, so register the equivalent URL for each
   further workspace.
4. Leave off user authorisation during installation, device flow, and the
   setup URL ("Request user authorization (OAuth) during installation",
   "Enable Device Flow", "Setup URL"). Install the app
   on the repository directly; authorisation starts from workspace Settings.
5. **Webhook**: active, URL `<origin>/api/integrations/github/webhook/`.
   Set a webhook secret, for example from `openssl rand -hex 32`, and copy it
   to `RESCRIBO_GITHUB_WEBHOOK_SECRET` in `.env`. The receiver verifies
   `X-Hub-Signature-256` with it. This URL is shared by every workspace.
6. **Repository permissions**: **Issues: Read and write** and **Contents:
   Read-only**; **Metadata: Read-only** is implicit. Contents read is needed
   for release links. No other permissions.
7. **Subscribe to events**: **Issues**. Installation and installation
   repository events are delivered automatically.
8. **Where can this GitHub App be installed?**: only on this account, for a
   disposable setup.

After creation:

- Copy **App ID** to `RESCRIBO_GITHUB_APP_ID` and **Client ID** to
  `RESCRIBO_GITHUB_CLIENT_ID` in `.env`.
- Generate a **client secret** and copy it to
  `RESCRIBO_GITHUB_CLIENT_SECRET`.
- Generate a **private key**. GitHub downloads a `.pem` file.

Keep the `.pem` outside the repository with mode 600. Pass it per process
with real newlines; only the API and the worker read the key, through
`github_client()` in `backend/integrations/github_app/settings.py`:

```sh
chmod 600 <path-to-pem>
RESCRIBO_GITHUB_PRIVATE_KEY="$(cat <path-to-pem>)" task api
RESCRIBO_GITHUB_PRIVATE_KEY="$(cat <path-to-pem>)" task worker
```

Run these instead of the plain `task api` and `task worker` from step 5; they
also load the new `.env` values. The quoted `\n` form and a multi-line value in
`.env` do not load; [issue
#168](https://github.com/nicoleman0/rescribo/issues/168) owns the fix. The
scheduler never calls GitHub, so it does not need the key.

Install the app on the disposable repository from the app's GitHub
**Install App** page.

## 8. Create the Slack App from the manifest

The manifest route is from the 10 Oct 2026 check (#139).

1. On the [Slack app settings page](https://api.slack.com/apps), under
   **Your App Configuration Tokens**, click **Generate Token**. The token is
   tied to you and the disposable workspace, not to an app.
2. Substitute the origin for the manifest placeholder and call
   `apps.manifest.create`:

   ```sh
   curl -X POST https://slack.com/api/apps.manifest.create \
     -H "Authorization: Bearer <configuration-token>" \
     --data-urlencode "manifest=$(sed 's|https://rescribo.example|<origin>|g' docs/slack-app-manifest.json)"
   ```

   The `apps.manifest.create` reply carries the app ID, client ID, client
   secret, and signing secret.

   Or create the app in the Slack app settings UI from the edited manifest.
   From **Basic Information**, copy the app ID, client ID, client secret, and
   signing secret.

   The manifest registers the redirect URL prefix `<origin>/api/workspaces/`
   (Slack accepts any callback under it, so every workspace is covered), the
   events request URL, and the interactivity request URL. Both request URLs are
   shared by every workspace and resolve the connection from the team ID. Set
   the app ID, client ID, client secret, and signing secret in `.env`:

   ```sh
   RESCRIBO_SLACK_APP_ID=<app-id>
   RESCRIBO_SLACK_CLIENT_ID=<client-id>
   RESCRIBO_SLACK_CLIENT_SECRET=<client-secret>
   RESCRIBO_SLACK_SIGNING_SECRET=<signing-secret>
   ```

3. Restart the API and the worker as in step 7, with
   `RESCRIBO_GITHUB_PRIVATE_KEY` set, to load the values.

Slack cannot verify the events request URL until the signing secret is in
`.env` and the API has restarted. Open **Event Subscriptions** in the Slack
app settings; if the request URL shows as unverified, click **Retry**.

## 9. Connect from workspace Settings

Both apps are now registered. In `/settings`, connect GitHub by selecting the
repository and authorising a user with access, then connect Slack. The
verification and consent rules are in [SETTINGS.md](SETTINGS.md).
