"""The adapter against the real matcher binary, and fake executables for failure modes."""

import copy
import json
import stat
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings

from matching.adapter import run_matcher
from matching.contract import SCHEMA_DIRECTORY, ContractError, ErrorCategory, MatchRequest
from matching.registry import supported_algorithms

EXAMPLES = json.loads((SCHEMA_DIRECTORY / "examples.json").read_text(encoding="utf-8"))
REQUESTS: dict[str, Any] = {example["name"]: example for example in EXAMPLES["requests"]}


def request(name: str = "valid") -> MatchRequest:
    return copy.deepcopy(REQUESTS[name]["document"])


@pytest.fixture(autouse=True)
def real_binary() -> None:
    path = Path(settings.RESCRIBO_MATCHER_PATH)
    assert path.is_file(), f"{path} is missing; run `task matcher-build`"


def fake(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "matcher"
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def failure(path: Path | str, document: MatchRequest | None = None, **limits: Any) -> str:
    with override_settings(RESCRIBO_MATCHER_PATH=str(path), **limits):
        try:
            run_matcher(document or request(), supported=supported_algorithms())
        except ContractError as error:
            return error.category.value
    return "ok"


def test_real_binary_ranks_the_valid_example() -> None:
    result = run_matcher(request(), supported=supported_algorithms())
    assert result.response["status"] == "ranked"
    assert len(result.build) == 64
    assert result.duration_ms >= 0


def test_real_binary_abstains_on_an_empty_pool() -> None:
    result = run_matcher(request("valid_empty_pool"), supported=supported_algorithms())
    assert result.response == {
        "contract_version": "1",
        "algorithm_version": "lexical-1",
        "config_version": "lexical-1.0",
        "status": "abstain",
        "abstain_reason": "no_candidates",
    }


def test_real_binary_replays_identically() -> None:
    first = run_matcher(request(), supported=supported_algorithms())
    second = run_matcher(request(), supported=supported_algorithms())
    assert json.dumps(first.response) == json.dumps(second.response)


def test_real_binary_rejects_too_many_linked_reports() -> None:
    # Python's contract has no linked-report cap; the matcher enforces the config's.
    document = request()
    document["candidates"][1]["linked_reports"] = [
        {"id": f"00000000-0000-4000-8000-0000000002{n:02x}", "title": "t", "description": ""}
        for n in range(6)
    ]
    assert failure(settings.RESCRIBO_MATCHER_PATH, document) == "invalid_request"


def test_invalid_request_never_starts_the_process(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    path = fake(tmp_path, f"/usr/bin/touch {marker}")
    assert failure(path, request("duplicate_candidate")) == "invalid_request"
    assert not marker.exists()


VERSIONS = {
    "contract_version": "1",
    "algorithm_version": "lexical-1",
    "config_version": "lexical-1.0",
}
ABSTAIN = json.dumps({**VERSIONS, "status": "abstain", "abstain_reason": "below_threshold"})


def ranked(problem_id: str, score: float) -> str:
    """A ranked document; `json.dumps` writes NaN as the non-JSON token Python accepts."""
    suggestion = {
        "problem_id": problem_id,
        "score": score,
        "features": {"title_overlap": 1},
        "evidence": [{"record": "problem", "id": problem_id, "field": "title"}],
    }
    return json.dumps({**VERSIONS, "status": "ranked", "suggestions": [suggestion]})


KNOWN = "00000000-0000-4000-8000-0000000000a1"
UNKNOWN = "00000000-0000-4000-8000-0000000000ff"


@pytest.mark.parametrize(
    ("stdout", "status", "expected"),
    [
        ("", "exit 1", ErrorCategory.PROCESS_FAILED),
        ("", "kill -9 $$", ErrorCategory.PROCESS_FAILED),
        ("not json", "exit 0", ErrorCategory.INVALID_RESPONSE),
        ("not json", "exit 3", ErrorCategory.PROCESS_FAILED),
        (
            '{"contract_version":"1","status":"error","error":"unsupported_version"}',
            "exit 2",
            ErrorCategory.UNSUPPORTED_VERSION,
        ),
        (
            '{"contract_version":"1","status":"error","error":"invalid_request"}',
            "exit 0",
            ErrorCategory.INVALID_RESPONSE,
        ),
        (ABSTAIN, "exit 1", ErrorCategory.PROCESS_FAILED),
        (ranked(KNOWN, float("nan")), "exit 0", ErrorCategory.INVALID_RESPONSE),
        (ranked(UNKNOWN, 1.0), "exit 0", ErrorCategory.INVALID_RESPONSE),
    ],
    ids=[
        "exit_1",
        "killed",
        "malformed_json",
        "malformed_json_nonzero",
        "error_document",
        "error_document_with_exit_0",
        "valid_document_with_nonzero_exit",
        "nan_score",
        "unknown_problem_id",
    ],
)
def test_process_failures_are_typed(
    tmp_path: Path, stdout: str, status: str, expected: ErrorCategory
) -> None:
    output = tmp_path / "stdout"
    output.write_text(stdout)
    assert failure(fake(tmp_path, f"/bin/cat {output}\n{status}")) == expected.value


def test_missing_executable(tmp_path: Path) -> None:
    assert failure(tmp_path / "absent") == "executable_missing"


def test_relative_path_is_refused() -> None:
    assert failure("rust/matcher/target/release/matcher") == "executable_missing"


def test_non_executable_file(tmp_path: Path) -> None:
    path = tmp_path / "matcher"
    path.write_text("#!/bin/sh\n")
    assert failure(path) == "executable_missing"


def test_timeout(tmp_path: Path) -> None:
    path = fake(tmp_path, "exec /bin/sleep 5")
    assert failure(path, RESCRIBO_MATCHER_TIMEOUT_SECONDS=0.2) == "timeout"


def test_oversized_output_is_cut_off_in_the_child(tmp_path: Path) -> None:
    # `yes` would run forever; the file size limit stops it at the cap.
    path = fake(tmp_path, "exec /usr/bin/yes")
    assert failure(path, RESCRIBO_MATCHER_MAX_RESPONSE_BYTES=1024) == "invalid_response"


def test_child_gets_an_empty_environment(tmp_path: Path) -> None:
    output = tmp_path / "stdout"
    output.write_text(ABSTAIN)
    check = '[ -z "$RESCRIBO_DATABASE_URL$HOME$DJANGO_SECRET_KEY" ] || exit 7'
    assert failure(fake(tmp_path, f"{check}\n/bin/cat {output}")) == "ok"
