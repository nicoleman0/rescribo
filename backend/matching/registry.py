"""Matcher configs from `configs/`. The Rust build embeds the same files."""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from matching.contract import SupportedAlgorithm, SupportedAlgorithms

CONFIG_DIRECTORY = Path(__file__).resolve().parent / "configs"


@dataclass(frozen=True)
class MatcherConfig:
    algorithm_version: str
    config_version: str
    max_linked_reports: int
    feature_names: frozenset[str]


@cache
def configs() -> dict[str, MatcherConfig]:
    """Every config file by config version. Weights and thresholds are Rust's concern."""
    loaded: dict[str, MatcherConfig] = {}
    for path in sorted(CONFIG_DIRECTORY.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        config = MatcherConfig(
            algorithm_version=data["algorithm_version"],
            config_version=data["config_version"],
            max_linked_reports=data["max_linked_reports"],
            feature_names=frozenset(data["weights"]),
        )
        if path.stem != config.config_version or config.config_version in loaded:
            raise ImproperlyConfigured(f"{path.name}: file name must be its unique config_version")
        if not isinstance(config.max_linked_reports, int) or config.max_linked_reports < 0:
            raise ImproperlyConfigured(f"{path.name}: max_linked_reports must be a count")
        loaded[config.config_version] = config
    return loaded


@cache
def supported_algorithms() -> SupportedAlgorithms:
    grouped: dict[str, list[MatcherConfig]] = {}
    for config in configs().values():
        grouped.setdefault(config.algorithm_version, []).append(config)
    supported: dict[str, SupportedAlgorithm] = {}
    for algorithm, members in grouped.items():
        features = {config.feature_names for config in members}
        if len(features) != 1:
            raise ImproperlyConfigured(f"{algorithm}: configs disagree on feature names")
        supported[algorithm] = SupportedAlgorithm(
            version=algorithm,
            config_versions=frozenset(config.config_version for config in members),
            feature_names=features.pop(),
        )
    return supported


def active_config() -> MatcherConfig:
    """The config new runs use, chosen by RESCRIBO_MATCHER_CONFIG_VERSION."""
    version = settings.RESCRIBO_MATCHER_CONFIG_VERSION
    config = configs().get(version)
    if config is None:
        raise ImproperlyConfigured(f"No matcher config file for {version}.")
    return config
