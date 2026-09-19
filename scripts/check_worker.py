"""Verify a real Celery worker processes a task through the configured broker."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from health.tasks import ping  # noqa: E402

result = ping.delay()
assert result.get(timeout=20) == "pong", "Unexpected worker result"
result.forget()
print("Broker -> worker -> result backend: OK")
