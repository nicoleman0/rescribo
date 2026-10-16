"""seed_test_accounts resets only the test workspace's allowed Slack channels."""

from io import StringIO

import pytest
from builders import make_workspace
from django.core.management import call_command

from accounts.models import Workspace
from connections.models import AllowedChannel, Connection

pytestmark = pytest.mark.django_db


def make_slack_connection(
    workspace: Workspace, external_id: str, channel_id: str, name: str
) -> Connection:
    connection = Connection.objects.create(
        workspace=workspace,
        provider=Connection.Provider.SLACK,
        external_id=external_id,
        status=Connection.Status.ACTIVE,
    )
    AllowedChannel.objects.create(
        connection=connection, channel_id=channel_id, name=name, is_private=False
    )
    return connection


def test_seed_clears_allowed_channels_for_the_e2e_workspace_alone() -> None:
    demo_workspace = make_workspace(name="Northwind (demo)", slug="demo", is_demo=True)
    other_workspace = make_workspace(name="Acme", slug="acme")
    demo_connection = make_slack_connection(demo_workspace, "T0DEMO", "C0DEMO", "demo-channel")
    other_connection = make_slack_connection(other_workspace, "T0ACME", "C0ACME", "acme-channel")

    call_command("seed_test_accounts", stdout=StringIO())
    e2e_connection = Connection.objects.get(
        workspace__slug="e2e-test", provider=Connection.Provider.SLACK
    )
    # A run cut off after "Allow channel" leaves an allowed channel behind.
    AllowedChannel.objects.create(
        connection=e2e_connection, channel_id="C0E2EPUBLIC", name="public", is_private=False
    )

    call_command("seed_test_accounts", stdout=StringIO())

    assert not AllowedChannel.objects.filter(connection=e2e_connection).exists()
    assert AllowedChannel.objects.filter(connection=demo_connection).exists()
    assert AllowedChannel.objects.filter(connection=other_connection).exists()
