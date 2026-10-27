# Proposal

## Why

Issue #265. Rescribo cannot call a language model, and every AI feature planned for v0.1 needs one (#266 drafts issues with structured output first). Sending report and conversation content to a model provider is a data-protection change, so each workspace must opt in before any content leaves the deployment.

## What Changes

- A workspace owner connects one model provider in Settings: pick a provider, enter the model name and API key, accept a consent statement, and pass a connection test. Presets cover OpenAI, Anthropic, Google, and OpenRouter; "Other" takes any public HTTPS OpenAI-compatible base URL.
- The provider is a third `Connection` provider (`model`). It reuses Fernet encryption, status, error codes, owner-only changes, member-readable status, refresh, and disconnect.
- An operator can set a deployment default in `rescribo.toml`. It names the API style, base URL, model, and the env var that holds the key (`api_key_env`). The file never holds the key. When it sets a provider, Settings shows the values locked; each workspace owner still enables it with consent. Only this file may point at local or private endpoints (Ollama, LM Studio, vLLM).
- One integration module, `backend/integrations/model/`, holds an OpenAI-compatible client and a native Anthropic adapter over `httpx`. No LiteLLM and no provider SDKs.
- The connection test sends a fixed synthetic prompt and passes only if the model returns JSON that validates against a small schema.
- Endpoint safety: base URLs entered in Settings must be public HTTPS. Every connection resolves the host, rejects non-public addresses, and connects to the checked address. Proxy env vars and redirects are not followed.
- Changing the API style or base URL requires a new key, so a stored key is never sent to a new host.
- Model calls are refused in the demo workspace and without an active, consented connection. #266 calls models only through this guard.
- New ADR 0010 records the client choice and the config-file design.
- `openspec/config.yaml`: the `context` block is replaced with the text from the issue comment. The delivery-order and architecture lines, schema, and rules stay.
- Docs: `docs/SETTINGS.md`, `docs/DEVELOPMENT.md`, `rescribo.toml.example`, `.env.example`.

## Capabilities

### New Capabilities

- `model-connection`: connecting a workspace to a language model provider, the deployment default, consent, the structured-output test, endpoint safety, key handling, and the guard every model call passes.

### Modified Capabilities

- `web-interface`: adds a requirement for the model provider card in Settings. The existing "Integration status cards" requirement is not changed.

## Impact

- `backend/connections/`: new provider value, new fields on `Connection` with a migration, connect service and view, payload changes, error details.
- `backend/integrations/model/`: new module (config, endpoint guard, two clients, connection test).
- `backend/config/`: loads and validates `rescribo.toml` at startup; new URL route.
- API: new connect endpoint and new fields on `Connection`. OpenAPI and TypeScript contracts regenerate.
- `frontend/src/features/settings/`: new model provider card in Connections.
- No new Python dependency. `tomllib` is in the standard library; `httpx` and `jsonschema` are already used.
- Expected rebase against open PRs #262 (settings, credential key startup check) and #264 (OpenAPI, `web-interface` spec).
