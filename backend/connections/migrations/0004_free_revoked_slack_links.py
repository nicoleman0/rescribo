from typing import Any

from django.db import migrations


def free_revoked_slack_links(apps: Any, schema_editor: Any) -> None:
    ExternalIdentity = apps.get_model("connections", "ExternalIdentity")
    ExternalIdentity.objects.filter(provider="slack", membership__is_active=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_workspace_is_demo"),
        ("connections", "0003_slack_capture"),
    ]

    operations = [migrations.RunPython(free_revoked_slack_links, migrations.RunPython.noop)]
