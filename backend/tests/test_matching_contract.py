import copy
import json
from typing import Any

import pytest

from matching.contract import (
    MAX_REQUEST_BYTES,
    SCHEMA_DIRECTORY,
    ContractError,
    ErrorCategory,
    MatchRequest,
    SupportedAlgorithm,
    parse_response,
    serialize_request,
)

EXAMPLES = json.loads((SCHEMA_DIRECTORY / "examples.json").read_text(encoding="utf-8"))
SUPPORTED = {
    entry["algorithm_version"]: SupportedAlgorithm(
        version=entry["algorithm_version"],
        config_versions=frozenset(entry["config_versions"]),
        feature_names=frozenset(entry["feature_names"]),
    )
    for entry in EXAMPLES["supported"]
}
REQUESTS: dict[str, Any] = {example["name"]: example for example in EXAMPLES["requests"]}


def _outcome(call: Any) -> str:
    try:
        call()
    except ContractError as error:
        return error.category.value
    return "ok"


@pytest.mark.parametrize("example", EXAMPLES["requests"], ids=lambda example: example["name"])
def test_request_examples(example: dict[str, Any]) -> None:
    assert _outcome(lambda: serialize_request(example["document"], SUPPORTED)) == example["expect"]


@pytest.mark.parametrize("example", EXAMPLES["responses"], ids=lambda example: example["name"])
def test_response_examples(example: dict[str, Any]) -> None:
    request = REQUESTS[example["request"]]["document"]
    raw = json.dumps(example["document"]).encode("utf-8")
    assert _outcome(lambda: parse_response(raw, request, SUPPORTED)) == example["expect"]


def test_request_over_byte_limit_is_rejected_not_truncated() -> None:
    document = copy.deepcopy(REQUESTS["valid"]["document"])
    document["report"]["description"] = "é" * (MAX_REQUEST_BYTES // 2)

    with pytest.raises(ContractError) as raised:
        serialize_request(document, SUPPORTED)

    assert raised.value.category is ErrorCategory.INVALID_REQUEST
    assert "byte limit" in raised.value.detail


def test_serialized_request_is_compact_utf8() -> None:
    document: MatchRequest = REQUESTS["valid"]["document"]

    encoded = serialize_request(document, SUPPORTED)

    assert json.loads(encoded.decode("utf-8")) == document
    assert b": " not in encoded


@pytest.mark.parametrize("raw", [b"", b"not json", b"\xff\xfe", b'{"a": 1}\n{"b": 2}'])
def test_response_must_be_one_json_document(raw: bytes) -> None:
    with pytest.raises(ContractError) as raised:
        parse_response(raw, REQUESTS["valid"]["document"], SUPPORTED)

    assert raised.value.category is ErrorCategory.INVALID_RESPONSE


def test_schema_errors_name_the_field_not_the_text() -> None:
    document = copy.deepcopy(REQUESTS["valid"]["document"])
    document["report"]["title"] = 42

    with pytest.raises(ContractError) as raised:
        serialize_request(document, SUPPORTED)

    assert raised.value.detail == "schema violation at report/title (type)"
