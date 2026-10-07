import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def live_status(num_proxies: str, forwarded_proto: str) -> int:
    """Production settings load once per process, so each case runs in a child."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "DJANGO_DEBUG": "False",
        "DJANGO_SECRET_KEY": "proxy-settings-test-secret",
        "DJANGO_ALLOWED_HOSTS": "testserver",
        "RESCRIBO_NUM_PROXIES": num_proxies,
    }
    code = (
        "import django; django.setup()\n"
        "from django.test import Client\n"
        "response = Client().get('/api/health/live/', "
        f"HTTP_X_FORWARDED_PROTO={forwarded_proto!r})\n"
        "print(response.status_code)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return int(result.stdout.strip())


def test_https_behind_a_trusted_proxy_is_served() -> None:
    assert live_status("1", "https") == 200


@pytest.mark.parametrize(("num_proxies", "forwarded_proto"), [("0", "https"), ("1", "http")])
def test_plain_or_untrusted_https_redirects(num_proxies: str, forwarded_proto: str) -> None:
    assert live_status(num_proxies, forwarded_proto) == 301
