"""Matcher config files as Python reads them."""

import json
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from matching import registry
from matching.apps import check_matcher_config


def test_shipped_config_is_supported_and_active() -> None:
    supported = registry.supported_algorithms()
    assert supported["lexical-1"].config_versions == frozenset({"lexical-1.0"})
    assert supported["lexical-1"].feature_names == frozenset(
        {"title_overlap", "summary_overlap", "linked_overlap"}
    )
    assert registry.active_config().max_linked_reports == 5
    assert check_matcher_config() == []


def test_unknown_active_config_fails_the_startup_check() -> None:
    with override_settings(RESCRIBO_MATCHER_CONFIG_VERSION="lexical-9.9"):
        assert [error.id for error in check_matcher_config()] == ["matching.E001"]


def test_file_name_must_match_config_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = registry.CONFIG_DIRECTORY / "lexical-1.0.json"
    (tmp_path / "renamed.json").write_text(source.read_text())
    monkeypatch.setattr(registry, "CONFIG_DIRECTORY", tmp_path)
    registry.configs.cache_clear()
    try:
        with pytest.raises(ImproperlyConfigured):
            registry.configs()
    finally:
        registry.configs.cache_clear()


def test_configs_of_one_algorithm_must_share_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = json.loads((registry.CONFIG_DIRECTORY / "lexical-1.0.json").read_text())
    (tmp_path / "lexical-1.0.json").write_text(json.dumps(data))
    data["config_version"] = "lexical-1.1"
    data["weights"] = {"title_overlap": 1.0}
    (tmp_path / "lexical-1.1.json").write_text(json.dumps(data))
    monkeypatch.setattr(registry, "CONFIG_DIRECTORY", tmp_path)
    registry.configs.cache_clear()
    registry.supported_algorithms.cache_clear()
    try:
        with pytest.raises(ImproperlyConfigured):
            registry.supported_algorithms()
    finally:
        registry.configs.cache_clear()
        registry.supported_algorithms.cache_clear()
