import json
from pathlib import Path

import pytest

import eval_cases


@pytest.fixture
def eval_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(eval_cases, "BATCHES_ROOT", tmp_path / "batches")
    monkeypatch.setattr(eval_cases, "GATES_PATH", tmp_path / "gates.json")
    (tmp_path / "gates.json").write_text(json.dumps({"spot_check_sample_size": 4}))
    return tmp_path
