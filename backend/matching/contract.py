"""Matcher contract v1: checks the JSON schemas cannot express.

The schemas in `schemas/v1/` are the authority for document shape. See ADR 0003.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

CONTRACT_VERSION = "1"
MAX_REQUEST_BYTES = 64 * 1024
MAX_CANDIDATES = 10
MAX_SUGGESTIONS = 3

SCHEMA_DIRECTORY = Path(__file__).resolve().parent / "schemas" / "v1"


class LinkedReport(TypedDict):
    id: str
    title: str
    description: str


class Candidate(TypedDict):
    id: str
    version: int
    title: str
    summary: str
    linked_reports: list[LinkedReport]


class RequestReport(TypedDict):
    id: str
    version: int
    title: str
    description: str


class MatchRequest(TypedDict):
    contract_version: str
    algorithm_version: str
    config_version: str
    report: RequestReport
    candidates: list[Candidate]


class EvidenceReference(TypedDict):
    record: Literal["problem", "linked_report"]
    id: str
    field: Literal["title", "summary", "description"]


class Suggestion(TypedDict):
    problem_id: str
    score: float
    features: dict[str, float]
    evidence: list[EvidenceReference]


class RankedResponse(TypedDict):
    contract_version: str
    algorithm_version: str
    config_version: str
    status: Literal["ranked"]
    suggestions: list[Suggestion]


class AbstainResponse(TypedDict):
    contract_version: str
    algorithm_version: str
    config_version: str
    status: Literal["abstain"]
    abstain_reason: Literal["no_candidates", "below_threshold", "insufficient_margin"]


MatchResponse = RankedResponse | AbstainResponse


class ErrorCategory(StrEnum):
    RETRIEVAL_FAILED = "retrieval_failed"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_VERSION = "unsupported_version"
    EXECUTABLE_MISSING = "executable_missing"
    PROCESS_FAILED = "process_failed"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"
    STALE_SNAPSHOT = "stale_snapshot"


class ContractError(Exception):
    """A typed contract failure. `detail` names fields, never customer text."""

    def __init__(self, category: ErrorCategory, detail: str) -> None:
        super().__init__(f"{category}: {detail}")
        self.category = category
        self.detail = detail


@dataclass(frozen=True)
class SupportedAlgorithm:
    version: str
    config_versions: frozenset[str]
    feature_names: frozenset[str]


SupportedAlgorithms = Mapping[str, SupportedAlgorithm]


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIRECTORY / f"{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _check_schema(name: str, document: Any, category: ErrorCategory) -> None:
    error = best_match(_validator(name).iter_errors(document))
    if error is not None:
        # The path names the field; the message could quote customer text.
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        raise ContractError(category, f"schema violation at {location} ({error.validator})")


def _check_versions(document: Mapping[str, Any], supported: SupportedAlgorithms) -> None:
    algorithm = supported.get(document["algorithm_version"])
    if algorithm is None:
        raise ContractError(ErrorCategory.UNSUPPORTED_VERSION, "unknown algorithm_version")
    if document["config_version"] not in algorithm.config_versions:
        raise ContractError(ErrorCategory.UNSUPPORTED_VERSION, "unknown config_version")


def _check_contract_version(document: object, category: ErrorCategory) -> None:
    if not isinstance(document, dict) or "contract_version" not in document:
        raise ContractError(category, "missing contract_version")
    if document["contract_version"] != CONTRACT_VERSION:
        raise ContractError(ErrorCategory.UNSUPPORTED_VERSION, "unknown contract_version")


def serialize_request(document: object, supported: SupportedAlgorithms) -> bytes:
    """Validate a request and return the exact bytes to send on stdin."""
    _check_contract_version(document, ErrorCategory.INVALID_REQUEST)
    _check_schema("request", document, ErrorCategory.INVALID_REQUEST)
    request = cast(MatchRequest, document)
    _check_versions(request, supported)
    candidate_ids = [candidate["id"] for candidate in request["candidates"]]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ContractError(ErrorCategory.INVALID_REQUEST, "duplicate candidate id")
    linked_ids = [
        linked["id"]
        for candidate in request["candidates"]
        for linked in candidate["linked_reports"]
    ]
    if len(set(linked_ids)) != len(linked_ids):
        raise ContractError(ErrorCategory.INVALID_REQUEST, "duplicate linked report id")
    encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ContractError(ErrorCategory.INVALID_REQUEST, "request exceeds byte limit")
    return encoded


def parse_response(
    raw: bytes, request: MatchRequest, supported: SupportedAlgorithms
) -> MatchResponse:
    """Parse matcher stdout and check it against the exact request that produced it."""
    try:
        document = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        raise ContractError(ErrorCategory.INVALID_RESPONSE, "not a UTF-8 JSON document") from None
    _check_contract_version(document, ErrorCategory.INVALID_RESPONSE)
    _check_schema("response", document, ErrorCategory.INVALID_RESPONSE)
    if document["status"] == "error":
        raise ContractError(ErrorCategory(document["error"]), "rejected by matcher")
    for field in ("algorithm_version", "config_version"):
        if document[field] != request[field]:
            raise ContractError(ErrorCategory.INVALID_RESPONSE, f"{field} differs from request")
    _check_versions(document, supported)
    response = cast(MatchResponse, document)
    if response["status"] == "ranked":
        algorithm = supported[response["algorithm_version"]]
        _check_suggestions(response["suggestions"], request, algorithm.feature_names)
    elif (response["abstain_reason"] == "no_candidates") != (not request["candidates"]):
        raise ContractError(ErrorCategory.INVALID_RESPONSE, "no_candidates iff the pool is empty")
    return response


def _check_suggestions(
    suggestions: list[Suggestion], request: MatchRequest, feature_names: frozenset[str]
) -> None:
    candidates = {candidate["id"]: candidate for candidate in request["candidates"]}
    seen: set[str] = set()
    for suggestion in suggestions:
        problem_id = suggestion["problem_id"]
        candidate = candidates.get(problem_id)
        if candidate is None:
            raise ContractError(ErrorCategory.INVALID_RESPONSE, "suggestion is not a candidate")
        if problem_id in seen:
            raise ContractError(ErrorCategory.INVALID_RESPONSE, "duplicate suggestion")
        seen.add(problem_id)
        if not suggestion["features"].keys() <= feature_names:
            raise ContractError(ErrorCategory.INVALID_RESPONSE, "unknown feature name")
        linked_ids = {linked["id"] for linked in candidate["linked_reports"]}
        for reference in suggestion["evidence"]:
            if reference["record"] == "problem":
                valid = reference["id"] == problem_id
            else:
                valid = reference["id"] in linked_ids
            if not valid:
                raise ContractError(ErrorCategory.INVALID_RESPONSE, "evidence outside candidate")
    order = [(-suggestion["score"], suggestion["problem_id"]) for suggestion in suggestions]
    if order != sorted(order):
        raise ContractError(ErrorCategory.INVALID_RESPONSE, "suggestions out of rank order")
