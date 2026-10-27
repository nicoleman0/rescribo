"""Model request shapes and error mapping, against recorded-shape mock responses."""

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from connections.errors import SetupError
from integrations.model.clients import ANTHROPIC_VERSION, Endpoint, generate_json
from integrations.model.endpoint import MAX_RESPONSE_BYTES

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
OPENAI = Endpoint("openai", "https://api.example.test/v1", "gpt-test", private_allowed=False)
ANTHROPIC = Endpoint("anthropic", "https://api.anthropic.com", "claude-test", False)
MARKER = "private-content-marker-71c2"
KEY = "sk-secret-marker-5e1d"


def openai_body(content: Any, **choice: Any) -> dict[str, Any]:
    message = {"role": "assistant", "content": content}
    message.update(choice.pop("message", {}))
    return {"choices": [{"index": 0, "message": message, "finish_reason": "stop"} | choice]}


def anthropic_body(text: str, stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "type": "message",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
    }


def run(
    endpoint: Endpoint,
    respond: Callable[[httpx.Request], httpx.Response],
    seen: list[httpx.Request] | None = None,
) -> dict[str, Any]:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return respond(request)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return generate_json(
        http, endpoint, KEY, system="sys", user=f"user {MARKER}", schema=SCHEMA, max_tokens=99
    )


def code_of(endpoint: Endpoint, respond: Callable[[httpx.Request], httpx.Response]) -> str:
    with pytest.raises(SetupError) as excinfo:
        run(endpoint, respond)
    return excinfo.value.code


def test_openai_request_shape() -> None:
    seen: list[httpx.Request] = []
    result = run(OPENAI, lambda r: httpx.Response(200, json=openai_body('{"answer": "a"}')), seen)
    assert result == {"answer": "a"}
    request = seen[0]
    assert str(request.url) == "https://api.example.test/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body == {
        "model": "gpt-test",
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": f"user {MARKER}"},
        ],
        "max_completion_tokens": 99,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": SCHEMA, "strict": True},
        },
    }


def test_anthropic_request_shape() -> None:
    seen: list[httpx.Request] = []
    result = run(
        ANTHROPIC, lambda r: httpx.Response(200, json=anthropic_body('{"answer":"b"}')), seen
    )
    assert result == {"answer": "b"}
    request = seen[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == KEY
    assert request.headers["anthropic-version"] == ANTHROPIC_VERSION == "2026-10-21"
    assert "authorization" not in request.headers
    body = json.loads(request.content)
    assert body == {
        "model": "claude-test",
        "max_tokens": 99,
        "system": "sys",
        "messages": [{"role": "user", "content": f"user {MARKER}"}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }
    assert "temperature" not in body and "tool_choice" not in body


def test_keyless_local_server_sends_no_auth_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=openai_body('{"answer": "a"}'))

    http = httpx.Client(transport=httpx.MockTransport(handler))
    local = Endpoint("openai", "http://ollama:11434/v1", "llama", private_allowed=True)
    generate_json(http, local, "", system="s", user="u", schema=SCHEMA, max_tokens=5)
    assert "authorization" not in seen[0].headers


@pytest.mark.parametrize(
    ("endpoint", "body", "code"),
    [
        (OPENAI, openai_body("not json"), "model_no_structured_output"),
        (OPENAI, openai_body('{"other": 1}'), "model_no_structured_output"),
        (OPENAI, openai_body('["answer"]'), "model_no_structured_output"),
        (OPENAI, openai_body(None, message={"refusal": "no"}), "model_refused"),
        (OPENAI, openai_body('{"answer"', finish_reason="length"), "model_no_structured_output"),
        (OPENAI, {"unexpected": True}, "provider_unavailable"),
        (ANTHROPIC, anthropic_body("not json"), "model_no_structured_output"),
        (ANTHROPIC, anthropic_body('{"answer": 3}'), "model_no_structured_output"),
        (ANTHROPIC, anthropic_body("", "refusal"), "model_refused"),
        (ANTHROPIC, anthropic_body('{"ans', "max_tokens"), "model_no_structured_output"),
        (ANTHROPIC, ["not", "an", "object"], "provider_unavailable"),
    ],
)
def test_bad_output_maps_to_safe_codes(endpoint: Endpoint, body: Any, code: str) -> None:
    assert code_of(endpoint, lambda r: httpx.Response(200, json=body)) == code


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (400, "model_request_rejected"),
        (401, "model_auth_rejected"),
        (403, "model_auth_rejected"),
        (404, "model_not_found"),
        (429, "model_rate_limited"),
        (500, "provider_unavailable"),
        (503, "provider_unavailable"),
    ],
)
@pytest.mark.parametrize("endpoint", [OPENAI, ANTHROPIC])
def test_http_status_maps_to_safe_codes(endpoint: Endpoint, status: int, code: str) -> None:
    error = {"error": {"message": f"echo {MARKER}"}}
    assert code_of(endpoint, lambda r: httpx.Response(status, json=error)) == code


def test_timeout_and_network_errors_are_provider_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert code_of(OPENAI, timeout) == "provider_unavailable"
    assert code_of(ANTHROPIC, refused) == "provider_unavailable"


def test_response_over_the_cap_is_refused() -> None:
    big = b"x" * (MAX_RESPONSE_BYTES + 1)
    assert code_of(OPENAI, lambda r: httpx.Response(200, content=big)) == "provider_unavailable"


def test_errors_drop_the_model_output_from_the_chain() -> None:
    with pytest.raises(SetupError) as excinfo:
        run(OPENAI, lambda r: httpx.Response(200, json=openai_body(f'{{"x": "{MARKER}"}}')))
    # Tracebacks and logging skip a suppressed context.
    assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__
    assert MARKER not in str(excinfo.value)


def test_no_key_prompt_or_response_reaches_logs(caplog: pytest.LogCaptureFixture) -> None:
    # caplog restores each level afterwards.
    caplog.set_level(logging.DEBUG)
    for name in list(logging.Logger.manager.loggerDict):
        caplog.set_level(logging.DEBUG, logger=name)
    run(OPENAI, lambda r: httpx.Response(200, json=openai_body(f'{{"answer": "{MARKER}"}}')))
    with pytest.raises(SetupError):
        run(ANTHROPIC, lambda r: httpx.Response(401, json={"error": f"bad {KEY} {MARKER}"}))
    with pytest.raises(SetupError):
        run(OPENAI, lambda r: httpx.Response(200, json=openai_body(f"not json {MARKER}")))
    assert caplog.records
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert MARKER not in text and KEY not in text
