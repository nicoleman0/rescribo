# Design

## Context

- `Connection` (`backend/connections/models.py`) has one row per workspace and provider, Fernet-encrypted `credential`, `status`, `error_code`, `version`, and owner-only services in `connections/services.py`. Slack and GitHub connect through OAuth (`SetupView`, `CallbackView`). A model provider has no OAuth: the owner pastes a key.
- `refuse_demo` already blocks every settings mutation in the demo workspace. `ERROR_DETAILS` maps safe codes to next steps.
- Settings load from env in `backend/config/settings.py`. `load_private_key` is the existing pattern for validating a value at startup with a message that never contains the secret.
- Python 3.14 ships `tomllib`. `httpx` (with `httpcore`) and `jsonschema` are already dependencies.
- Decisions settled in the issue comment of 27 Oct are not restated here. ADR 0010 (`docs/adr/0010-model-provider-clients-and-config.md`) records the client choice and the config-file design (see Decisions 3 and 2).

## Goals / Non-Goals

**Goals:**
- One guarded entry point, `model_client(workspace_id)`, that #266 uses for every model call.
- A connection test that proves structured JSON output, not only a valid key.
- SSRF protection that holds across DNS changes, not only at save time.

**Non-Goals:**
- Listing models from the provider, streaming, retries, token or cost accounting, per-call audit records.
- Background health checks of the model connection. Owners check status by hand, like Slack and GitHub.
- Proxy support for outbound model calls.
- Any feature that sends report content. #266 adds the first one.

## Decisions

### 1. Data model: typed columns on `Connection`

Add `Provider.MODEL = "model"` and four columns: `api_style` (`openai` or `anthropic`, blank for other providers), `base_url` (max 500), `model` (max 200), and `consented_at` (nullable). The key goes in the existing `credential` column. One migration; `SetupState.provider` choices change with no database effect.

When the deployment config sets the provider, the row keeps only status, consent, and timestamps. `api_style`, `base_url`, `model`, and `credential` stay blank and are resolved from the config at call time, so a config change applies to every workspace without a data migration.

Alternative: a JSON `settings` column. Rejected: no type checks, and the payload code would need to parse it. Alternative: reuse `repository` and `external_id` for URL and model. Rejected: misleading names.

### 2. Deployment config file

- Path: `RESCRIBO_CONFIG_FILE`, default `<repo root>/rescribo.toml` (`/app/rescribo.toml` in the image). A missing default file means no deployment config. A missing file at an explicitly set path fails startup.
- Shape, with every field except `api_key_env` required and unknown keys rejected:

  ```toml
  [model]
  api_style = "openai"            # or "anthropic"
  base_url = "https://api.openai.com/v1"
  model = "gpt-5-mini"
  api_key_env = "OPENAI_API_KEY"  # omit for a local server with no key
  ```

- `integrations/model/config.py` has `load_deployment_model(path, environ, *, required)`; `required` is true when `RESCRIBO_CONFIG_FILE` is set. It returns a frozen `DeploymentModel` or `None`, and raises `ImproperlyConfigured` naming the file and field. `settings.py` stores the result as `RESCRIBO_MODEL_DEPLOYMENT`. It stores the env var name, never the key. The client reads the key from the environment at call time, so the key never sits in Django settings or a debug page.
- `base_url` here may be `http` and may point at private hosts (Ollama, LM Studio, vLLM).

Alternative: env vars only (`RESCRIBO_MODEL_BASE_URL`, ...). Rejected by the issue comment. A file also leaves room for later deployment settings without more env vars.

### 3. Clients: `httpx`, no provider SDKs

`integrations/model/clients.py` has one `generate_json(endpoint, key, model, system, user, schema, max_tokens) -> dict` per API style, behind one function that dispatches on `api_style`.

- OpenAI-compatible: `POST {base_url}/chat/completions`, `Authorization: Bearer`, `max_completion_tokens`, `response_format: {"type": "json_schema", "json_schema": {"name", "schema", "strict": true}}`. The base URL includes the version segment (`.../v1`).
- Anthropic: `POST {base_url}/v1/messages`, `x-api-key`, `anthropic-version: 2026-10-21`, `output_config: {"format": {"type": "json_schema", "schema": ...}}`. No `temperature` (rejected on that version) and no forced `tool_choice` (rejected by current Claude models). A `stop_reason` of `refusal` or `max_tokens` is a safe error. The base URL is the API root (`https://api.anthropic.com`).
- Both parse the text output with `json.loads` and validate it with `jsonschema`. A validation failure raises `model_no_structured_output`. The `jsonschema` error message contains model output, so it is never logged or returned.

Why not the SDKs: Decision 4 needs a transport that checks every connection. The Anthropic SDK 1.x runs on `httpx2`, not `httpx`, so it would need a second HTTP stack and a second guarded transport. The SDKs also retry by default and read logging env vars (`OPENAI_LOG`, `ANTHROPIC_LOG`) that can print request bodies. Each API needs one endpoint here. Cost: request shapes are maintained by hand; provider API changes surface as test failures in the connection test.

### 4. Endpoint guard

`integrations/model/endpoint.py`:

- `validate_settings_url(url)`: `https` only, a host, no userinfo, query, or fragment, length ≤ 500. Used for owner input.
- A `GuardedBackend` (an `httpcore` network backend). Its `connect_tcp(host, port)` resolves with `getaddrinfo`, refuses when any address is not `is_global` (this covers loopback, RFC 1918, link-local and metadata `169.254.169.254`, CGNAT, ULA, multicast, unspecified, and IPv4-mapped forms), then connects to a checked address. `httpcore` still sends the original host name for SNI and certificate checks, so TLS stays valid.
- `guarded_client()` builds `httpx.Client` over a small `httpx.BaseTransport` that wraps `httpcore.ConnectionPool(network_backend=GuardedBackend())`. No private attributes. `trust_env=False`, `follow_redirects=False`, timeouts (connect 5 s, read 60 s). `read_limited` enforces the 1 MB response cap and the 60 s total while the clients read the body.
- `config_client()` serves deployment config endpoints: the same transport, flags, and limits over the plain `httpcore` backend, with no address check.
- A blocked address raises `endpoint_blocked`. Its detail never names the resolved address.

Checking inside `connect_tcp` covers DNS rebinding, redirects, and pooled reconnects in one place. Alternative: resolve once and rewrite the URL to the IP with a `Host` header. Rejected: breaks SNI and certificate checks.

### 5. Services, API, and the call guard

- Two modules keep `services.py` from growing and avoid an import cycle with `providers.py`. `connections/model_access.py` holds `model_client`, the row and deployment resolution, and the status check. `connections/model_connection.py` holds `connect_model`.
  - `connect_model(actor, *, api_style, base_url, model, api_key, consent)`: refuses demo and missing consent, refuses `deployment_managed` when the config sets the provider and any field is sent, requires a key when the style or base URL differs from the stored row (`key_required`), runs the connection test **before** taking locks, encrypts a new key after the test passes, then locks the workspace and row, saves, and sets `active`, `consented_at`, `last_success_at`, `version += 1`. A failed test saves nothing.
  - `model_client(workspace_id) -> ModelClient` (in `model_access.py`): refuses demo, a missing or inactive row, or a row without `consented_at`, then resolves deployment config or row values and decrypts the key. This is the only way #266 reaches a model.
  - Consent names a provider. A row connected in Settings always has a base URL; a row enabled for the deployment default has none. When the config file's `[model]` table is added or removed, rows from the other mode are refused (`model_not_connected`) and listed as disconnected until an owner connects again.
  - The connection test is `ModelClient.generate_json` with a fixed prompt and schema `{"status": "ok", "nonce": "<random>"}`; it passes only if the nonce comes back.
- `providers.check_connection` takes the row and gains the `model` branch, so `refresh/` works unchanged. `disconnect/` clears `credential`, `api_style`, `base_url`, `model`, and `consented_at` in addition to the shared steps. A model disconnect or failed model check does not cancel notifications: `cancel_notifications` cancels every pending Slack notification in the workspace, which has nothing to do with the model.
- `SetupView` and `CallbackView` return 404 for `model`.
- New routes: `POST connections/model/connect/` (owner, 204 or `ErrorSerializer`) and `GET connections/model/deployment/` (member, `{managed, api_style, base_url, model}`).
- `ConnectionSerializer` gains `api_style`, `base_url`, `model` (empty for Slack and GitHub; for a managed row, the deployment values). `operations` stays required; the model row returns zeros and the card does not show it.
- New `ERROR_DETAILS`: `model_auth_rejected`, `model_not_found`, `model_rate_limited`, `model_no_structured_output`, `model_refused`, `endpoint_blocked`, `key_required`, `deployment_managed`, `model_not_connected`. HTTP 401/403, 404, and 429 map to the first three. 400 and 422 map to a new `model_request_rejected`, whose detail points at JSON schema support. Network errors, redirects, and other statuses map to the existing `provider_unavailable`.

### 6. Frontend

- `model-provider-settings.tsx` in `features/settings/`, rendered after GitHub in `ConnectionsSection`. Presets live in one frontend constant: OpenAI `https://api.openai.com/v1`, Anthropic `https://api.anthropic.com`, Google `https://generativelanguage.googleapis.com/v1beta/openai`, OpenRouter `https://openrouter.ai/api/v1`, Other (empty, OpenAI style). The backend stores only `api_style` and `base_url`.
- Reuses `ConnectionStatusBadge`, `TechnicalDetails`, `ConfirmAction`, `useSettingsAction`, and the existing check-result pattern. The key input is `type="password"`, `autocomplete="off"`, and is cleared after every submit.
- The demo alert text in `ConnectionsSection` names the model provider too.

### 7. `openspec/config.yaml`

Replace the `context` block with the issue comment's text verbatim, then append the existing two lines (delivery order, architecture and decisions) inside the block. The "Evidence rules" and "MVP is complete" paragraphs go. `schema` and `rules` stay byte for byte.

## Risks / Trade-offs

- [Compatible servers differ in `json_schema` support] → The test fails with `model_no_structured_output` and a detail that says the model must support JSON schema output. That is the intended gate, since #266 needs it.
- [Hand-written request shapes drift from provider APIs] → Each shape lives in one function with mocked tests on recorded response bodies. A live check is listed as optional in tasks.
- [`is_global` edge cases differ across Python versions] → Tests assert each blocked range explicitly, including `::ffff:127.0.0.1` and `169.254.169.254`.
- [Connection test takes up to 60 s in a request] → Run before any lock. The frontend shows a pending state.
- [Operators behind an egress proxy cannot reach a provider] → Out of scope; documented as a known limit.
- [Two open PRs touch `settings.py`, `connections/apps.py`, OpenAPI, and `web-interface`] → Additive edits only; rebase and regenerate the schema after they merge.

## Migration Plan

One additive migration. Existing rows get blank values and no consent. Rollback: revert the commit and the migration; `model` rows are then unused and can be deleted. No data backfill.
