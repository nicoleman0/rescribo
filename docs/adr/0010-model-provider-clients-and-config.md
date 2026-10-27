# ADR 0010: Model provider clients and deployment config

Status: accepted. 27 October 2026.

## Clients

Rescribo calls language models through two small `httpx` clients in `backend/integrations/model/`: one for the OpenAI-compatible chat completions API and one for the Anthropic Messages API. It uses no provider SDK and no LiteLLM.

- One OpenAI-compatible client covers OpenAI, OpenRouter, Google's compatible endpoint, Groq, Ollama, LM Studio, and vLLM.
- Every request from a base URL entered in Settings goes through a guarded `httpcore` network backend. It resolves the host on each new connection, refuses any address that is not publicly routable, and connects to the address it checked. This covers DNS rebinding, redirects, and pooled reconnects in one place.
- The Anthropic SDK 1.x runs on `httpx2`, so it would need a second HTTP stack and a second guarded transport. Both SDKs retry by default and read logging env vars that can print request bodies.
- LiteLLM adds a large dependency and its own HTTP and logging behaviour for two endpoints.

Cost: request shapes are kept by hand. A provider API change shows up as a failed connection test.

## Deployment config file

An operator can set one model provider for every workspace in `rescribo.toml`, at `RESCRIBO_CONFIG_FILE`. The `[model]` table names `api_style`, `base_url`, `model`, and `api_key_env`, the environment variable that holds the key. The file never holds the key.

- Every process validates the file at startup and fails with a message naming the file and field.
- Workspace rows keep only status and consent. The values come from the file at call time, so a file change applies to every workspace.
- Only this file may name an `http` URL or a private host, so local servers stay an operator decision.
- Each workspace owner still enables the provider with consent.

A file was chosen over more env vars so later deployment settings have one home.
