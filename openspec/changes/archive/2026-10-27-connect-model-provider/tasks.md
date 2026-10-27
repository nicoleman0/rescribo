# Tasks

## 1. Project context and ADR

- [x] 1.1 In `openspec/config.yaml`, replace the `context` block as in design.md Decision 7. Verify `git diff openspec/config.yaml` touches only the `context` block and `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 1.2 Add `docs/adr/0010-model-provider-clients-and-config.md`: `httpx` clients over provider SDKs and LiteLLM, the guarded transport, and the `rescribo.toml` design with `api_key_env`, in the style of ADR 0008. Verify design.md links it and does not restate it beyond one line.

## 2. Deployment config

- [x] 2.1 Add `backend/integrations/model/config.py` with `DeploymentModel` and `load_deployment_model(path, environ)` (design.md Decision 2). Verify with `backend/tests/test_model_config.py`: no default file returns `None`; a valid file returns the values; a missing explicit path, unknown key, unknown `api_style`, missing field, bad `base_url`, and an unset or empty `api_key_env` each raise `ImproperlyConfigured` naming the file and field; a set key value never appears in the message or `repr`.
- [x] 2.2 Wire it in `backend/config/settings.py` as `RESCRIBO_MODEL_DEPLOYMENT`, reading `RESCRIBO_CONFIG_FILE`. Verify with a subprocess startup test (like the private key test) that an invalid file fails `django.setup()` with the file name in stderr, and `uv run python backend/manage.py check` passes with no file.
- [x] 2.3 Add `rescribo.toml.example` with the commented shape for OpenAI, Anthropic, and a local Ollama server, and a commented `RESCRIBO_CONFIG_FILE` line in `.env.example`. Verify the example loads through `load_deployment_model` in a test after uncommenting one block.

## 3. Endpoint guard

- [x] 3.1 Add `backend/integrations/model/endpoint.py` with `validate_settings_url`, `GuardedBackend`, `guarded_client()`, and `config_client()` (design.md Decision 4). Verify with `backend/tests/test_model_endpoint.py`, patching `socket.getaddrinfo`: `http`, userinfo, query, fragment, and no host are rejected; `127.0.0.1`, `10.0.0.1`, `172.16.0.1`, `192.168.1.1`, `169.254.169.254`, `100.64.0.1`, `::1`, `fc00::1`, `fe80::1`, `::ffff:127.0.0.1`, and `0.0.0.0` raise `endpoint_blocked` at connect; a host resolving to one public and one private address is refused; a public address connects to that exact address; the error text never contains the address.
- [x] 3.2 Verify redirects are not followed and proxy env vars are ignored: with `HTTPS_PROXY` set, both clients have `trust_env` false and `follow_redirects` false, and a client call that gets a 302 raises `provider_unavailable` without a second request.

## 4. Clients and connection test

- [x] 4.1 Add `backend/integrations/model/clients.py` with the OpenAI-compatible and Anthropic `generate_json` (design.md Decision 3) and the HTTP-status-to-code mapping. Verify with `backend/tests/test_model_clients.py` using `httpx.MockTransport`: exact request path, headers, and body for each style (Anthropic has `anthropic-version: 2026-10-21`, `output_config.format`, no `temperature`, no `tool_choice`); valid JSON returns a dict; non-JSON, schema-invalid JSON, `refusal`, and `max_tokens` raise the right codes; 401, 403, 404, 429, 500, and timeout map to the right codes; a response over 1 MB is refused.
- [x] 4.2 Verify no secrets or content reach logs: with `caplog` at DEBUG for all loggers, run a failing and a passing call whose prompt and response hold a marker string and whose key is a marker; assert neither marker appears in any record.

## 5. Connection model and services

- [x] 5.1 Add `Provider.MODEL` and the four columns to `Connection`, with a migration (design.md Decision 1). Verify `uv run python backend/manage.py makemigrations --check` reports nothing after it.
- [x] 5.2 Add `backend/connections/model_connection.py` with `connect_model`, `model_client`, and the connection test (design.md Decision 5); extend `providers.check_connection`, `disconnect`, `connection_payload`, and `ERROR_DETAILS`. Verify with `backend/tests/test_model_connection.py` (client mocked at the transport): connect succeeds and stores an encrypted key; no consent, demo workspace, non-owner, and failed test each save nothing; changing base URL or style without a key is refused before any request; changing only the model reuses the key; managed deployment refuses owner fields and accepts consent only; refresh moves an active row to `error` with the right code; disconnect clears key, settings, and consent.
- [x] 5.3 Verify the call guard: `model_client` refuses the demo workspace, a missing row, an inactive row, and a row without consent with no request made (assert the mock transport saw zero requests), and returns a client using deployment values for a managed row. Add a cross-workspace test: an owner of workspace A cannot connect, refresh, or disconnect workspace B's model row.

## 6. API

- [x] 6.1 Add `POST connections/model/connect/` and `GET connections/model/deployment/` in `connections/views.py` and `config/urls.py`; return 404 for `model` on `setup/` and `callback/`; add the new fields to `ConnectionSerializer`. Verify with API tests in `backend/tests/test_model_connection.py` for status codes, `reason` values, and that no response body contains the key.
- [x] 6.2 Run `task schema` and verify `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts` change only for the new routes and fields.

## 7. Settings UI

- [x] 7.1 Add `frontend/src/features/settings/model-provider-settings.tsx` and render it in `ConnectionsSection`; update the demo alert text; add API helpers in `frontend/src/api/settings.ts` (design.md Decision 6). Verify with component tests in `settings-page.test.tsx`: not connected, active, error, member view, managed view, preset fills base URL, connect disabled without consent, key cleared after a failed submit.
- [x] 7.2 Add e2e cases to `frontend/e2e/settings.spec.ts`: the owner sees the model card and form; submitting `https://127.0.0.1/v1` with consent shows the endpoint error; the member view has no form; axe passes on the card. Verify with `RESCRIBO_E2E_API_PORT=8265 RESCRIBO_E2E_FRONTEND_PORT=5265 task e2e`.
- [x] 7.3 Take after screenshots with `switchyard/scripts/shots.mjs` into `.switchyard/shots/after` and build `.switchyard/shots/compare.html`. Verify the Connections page shows the model card in both themes.

## 8. Docs

- [x] 8.1 Update `docs/SETTINGS.md`: model provider setup in Settings, the consent, the key-per-endpoint rule, `rescribo.toml` with `RESCRIBO_CONFIG_FILE` and `api_key_env`, private endpoints only from the file, the startup failure, no proxy support, and that model tests are mocked. Verify every env var and file name it mentions exists in code with `git grep`.
- [x] 8.2 Update `docs/DEVELOPMENT.md` module map with `backend/integrations/model/` and the model connection in `backend/connections/`. Verify the listed paths exist.

## 9. Repository checks

- [x] 9.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 9.2 `task check test build schema-check` passes with PostgreSQL and Redis running. Record the test counts for the PR.
- [x] 9.3 `RESCRIBO_E2E_API_PORT=8265 RESCRIBO_E2E_FRONTEND_PORT=5265 task e2e` passes. Record the counts.
- [x] 9.4 `task worker-check` passes, since worker startup now loads the config file.

## Workflow follow-up

- Archive this change in the PR that completes #265 (`/opsx:archive`).
- The PR closes #265. Milestone: I. First release.
- Rebase on #262 and #264 if they merge first; regenerate the schema after the rebase.
