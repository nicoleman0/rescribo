"""Demo workspace: seeding, isolation, provider guards, and the nightly reset."""

import pytest
from builders import make_workspace

from accounts.demo import is_demo_workspace

pytestmark = pytest.mark.django_db


def test_workspaces_are_not_demos_by_default() -> None:
    workspace = make_workspace()
    assert workspace.is_demo is False
    assert is_demo_workspace(workspace.pk) is False
    assert is_demo_workspace(make_workspace(slug="demo", is_demo=True).pk) is True
