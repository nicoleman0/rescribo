"""The Slack feasibility script fails clearly before any API call when unconfigured."""

import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_channel_list_script_reports_missing_token_without_django_settings() -> None:
    env = {**os.environ, "RESCRIBO_SLACK_BOT_TOKEN": ""}
    env.pop("DJANGO_SETTINGS_MODULE", None)
    result = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts/list_slack_channels.py")],
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Set RESCRIBO_SLACK_BOT_TOKEN before running this check." in result.stderr
    assert "ImproperlyConfigured" not in result.stderr
