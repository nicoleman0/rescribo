"""Structured JSON from a model over the OpenAI-compatible or the Anthropic API.

Nothing here logs. Errors carry a safe code only, because provider bodies and
schema errors can echo the prompt or the output.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import jsonschema

from connections.errors import known_error
from integrations.model import endpoint as endpoints

ANTHROPIC_VERSION = "2026-10-21"
STATUS_CODES = {
    400: "model_request_rejected",
    401: "model_auth_rejected",
    403: "model_auth_rejected",
    404: "model_not_found",
    422: "model_request_rejected",
    429: "model_rate_limited",
}

JSON = dict[str, Any]


@dataclass(frozen=True)
class Endpoint:
    api_style: str
    base_url: str
    model: str
    # True only for the operator's config file, which may name local or private hosts.
    private_allowed: bool


@dataclass(frozen=True)
class ModelClient:
    endpoint: Endpoint
    key: str = field(repr=False)

    def generate_json(self, *, system: str, user: str, schema: JSON, max_tokens: int) -> JSON:
        open_http = (
            endpoints.config_client if self.endpoint.private_allowed else endpoints.guarded_client
        )
        with open_http() as http:
            return generate_json(
                http,
                self.endpoint,
                self.key,
                system=system,
                user=user,
                schema=schema,
                max_tokens=max_tokens,
            )


def openai_request(
    endpoint: Endpoint, key: str, system: str, user: str, schema: JSON, max_tokens: int
) -> tuple[str, dict[str, str], JSON]:
    body = {
        "model": endpoint.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_completion_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": schema, "strict": True},
        },
    }
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return f"{endpoint.base_url}/chat/completions", headers, body


def anthropic_request(
    endpoint: Endpoint, key: str, system: str, user: str, schema: JSON, max_tokens: int
) -> tuple[str, dict[str, str], JSON]:
    # No temperature: this API version rejects it. No forced tool_choice: current models reject it.
    body = {
        "model": endpoint.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    headers = {"anthropic-version": ANTHROPIC_VERSION} | ({"x-api-key": key} if key else {})
    return f"{endpoint.base_url}/v1/messages", headers, body


def openai_text(envelope: JSON) -> str:
    try:
        choice = envelope["choices"][0]
        message = choice["message"]
    except KeyError, IndexError, TypeError:
        raise known_error("provider_unavailable") from None
    if message.get("refusal"):
        raise known_error("model_refused")
    content = message.get("content")
    if choice.get("finish_reason") == "length" or not isinstance(content, str):
        raise known_error("model_no_structured_output")
    return content


def anthropic_text(envelope: JSON) -> str:
    stop_reason = envelope.get("stop_reason")
    if stop_reason == "refusal":
        raise known_error("model_refused")
    if stop_reason == "max_tokens":
        raise known_error("model_no_structured_output")
    blocks = envelope.get("content")
    if not isinstance(blocks, list):
        raise known_error("provider_unavailable")
    return "".join(
        str(block.get("text", ""))
        for block in blocks
        if isinstance(block, dict) and block.get("type") == "text"
    )


STYLES: dict[
    str,
    tuple[
        Callable[[Endpoint, str, str, str, JSON, int], tuple[str, dict[str, str], JSON]],
        Callable[[JSON], str],
    ],
] = {
    "openai": (openai_request, openai_text),
    "anthropic": (anthropic_request, anthropic_text),
}


def generate_json(
    http: httpx.Client,
    endpoint: Endpoint,
    key: str,
    *,
    system: str,
    user: str,
    schema: JSON,
    max_tokens: int,
) -> JSON:
    build, text_of = STYLES[endpoint.api_style]
    url, headers, body = build(endpoint, key, system, user, schema, max_tokens)
    started = time.monotonic()
    try:
        with http.stream("POST", url, headers=headers, json=body) as response:
            raw = endpoints.read_limited(response, started)
    except httpx.HTTPError:
        raise known_error("provider_unavailable") from None
    if response.status_code in STATUS_CODES:
        raise known_error(STATUS_CODES[response.status_code])
    if response.status_code != 200:
        # Includes redirects, which are never followed.
        raise known_error("provider_unavailable")
    try:
        envelope = json.loads(raw)
    except ValueError:
        raise known_error("provider_unavailable") from None
    if not isinstance(envelope, dict):
        raise known_error("provider_unavailable")
    return validated(text_of(envelope), schema)


def validated(text: str, schema: JSON) -> JSON:
    try:
        value = json.loads(text)
        jsonschema.validate(value, schema)
    except ValueError, jsonschema.ValidationError:
        # `from None`: the validation message quotes the model output.
        raise known_error("model_no_structured_output") from None
    if not isinstance(value, dict):
        raise known_error("model_no_structured_output")
    return value
