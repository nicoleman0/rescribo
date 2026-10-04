"""Runs the matcher executable on one validated request. See ADR 0003."""

import hashlib
import resource
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from django.conf import settings

from matching.contract import (
    ContractError,
    ErrorCategory,
    MatchRequest,
    MatchResponse,
    SupportedAlgorithms,
    parse_response,
    serialize_request,
)

# Categories a matcher error document may carry, with a nonzero exit.
MATCHER_REJECTIONS = frozenset({ErrorCategory.INVALID_REQUEST, ErrorCategory.UNSUPPORTED_VERSION})


@dataclass(frozen=True)
class MatcherResult:
    response: MatchResponse
    build: str
    duration_ms: int


def run_matcher(request: MatchRequest, *, supported: SupportedAlgorithms) -> MatcherResult:
    """Validate, invoke, and validate again. Every failure is a ContractError."""
    payload = serialize_request(request, supported)
    path = Path(settings.RESCRIBO_MATCHER_PATH)
    if not path.is_absolute():
        raise ContractError(ErrorCategory.EXECUTABLE_MISSING, "matcher path is not absolute")
    build = _build_id(path)
    limit = settings.RESCRIBO_MATCHER_MAX_RESPONSE_BYTES
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout:
        try:
            completed = subprocess.run(
                [str(path)],
                input=payload,
                stdout=stdout,
                # Diagnostics may quote input; they are dropped rather than logged.
                stderr=subprocess.DEVNULL,
                env={},
                cwd="/",
                timeout=settings.RESCRIBO_MATCHER_TIMEOUT_SECONDS,
                preexec_fn=_cap_file_writes(limit + 1),
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise ContractError(ErrorCategory.TIMEOUT, "matcher timed out") from None
        except OSError:
            raise ContractError(ErrorCategory.EXECUTABLE_MISSING, "matcher did not start") from None
        duration_ms = round((time.monotonic() - started) * 1000)
        stdout.seek(0)
        raw = stdout.read(limit + 1)
    if len(raw) > limit:
        raise ContractError(ErrorCategory.INVALID_RESPONSE, "response exceeds byte limit")
    if completed.returncode != 0:
        _raise_for_exit(raw, completed.returncode, request, supported)
    try:
        response = parse_response(raw, request, supported)
    except ContractError as error:
        # With exit 0, any contract failure, even an error document, is invalid output.
        raise ContractError(ErrorCategory.INVALID_RESPONSE, error.detail) from None
    return MatcherResult(response=response, build=build, duration_ms=duration_ms)


def _raise_for_exit(
    raw: bytes, returncode: int, request: MatchRequest, supported: SupportedAlgorithms
) -> None:
    try:
        parse_response(raw, request, supported)
    except ContractError as error:
        if error.category in MATCHER_REJECTIONS and returncode > 0:
            raise
    raise ContractError(ErrorCategory.PROCESS_FAILED, f"exit status {returncode}")


def _cap_file_writes(limit: int) -> Callable[[], None]:
    """Bound stdout in the child: past the limit, the kernel stops the write with SIGXFSZ."""

    def apply() -> None:
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))

    return apply


def _build_id(path: Path) -> str:
    try:
        stat = path.stat()
    except OSError:
        raise ContractError(ErrorCategory.EXECUTABLE_MISSING, "matcher not found") from None
    return _digest(path, stat.st_mtime_ns, stat.st_size)


@cache
def _digest(path: Path, modified_ns: int, size: int) -> str:
    """SHA-256 of the binary, recorded with each run. Cached per file version."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
