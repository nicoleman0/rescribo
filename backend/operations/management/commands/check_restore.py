"""Check that a restored database is migrated and serves a report through the API."""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from accounts.models import Membership
from accounts.session import SESSION_GENERATION_KEY
from feedback.models import Report


class Command(BaseCommand):
    help = "Run against a restored database; `task restore-check` sets it up."

    def handle(self, *args: object, **options: Any) -> None:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            raise CommandError(f"Restored database has {len(pending)} unapplied migrations.")
        owner = (
            Membership.objects.select_related("user")
            .filter(
                is_active=True,
                role=Membership.Role.OWNER,
                workspace__reports__isnull=False,
            )
            .first()
        )
        if owner is None:
            raise CommandError("Restored database has no report in a workspace with an owner.")
        report = Report.objects.filter(workspace_id=owner.workspace_id).order_by("id").first()
        assert report is not None
        client = Client()
        client.force_login(owner.user)
        session = client.session
        session[SESSION_GENERATION_KEY] = owner.user.session_generation
        session.save()
        response = client.get(
            f"/api/workspaces/{owner.workspace_id}/reports/{report.pk}/",
            HTTP_HOST=settings.ALLOWED_HOSTS[0],
        )
        if response.status_code != 200 or response.json().get("id") != str(report.pk):
            raise CommandError(
                f"Reading a restored report failed with HTTP {response.status_code}."
            )
        self.stdout.write(f"Restored database is migrated and served report {report.pk}.")
