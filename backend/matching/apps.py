from typing import Any

from django.apps import AppConfig
from django.core import checks
from django.core.exceptions import ImproperlyConfigured


class MatchingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "matching"

    def ready(self) -> None:
        checks.register(check_matcher_config)


def check_matcher_config(**kwargs: Any) -> list[checks.CheckMessage]:
    """Fail at startup, not during report capture, when the active config is unusable."""
    from matching.registry import active_config, supported_algorithms

    try:
        supported_algorithms()
        active_config()
    except (ImproperlyConfigured, KeyError, ValueError) as error:
        return [checks.Error(str(error), id="matching.E001")]
    return []
