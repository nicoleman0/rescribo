"""Existing manual provenance remains unkeyed when upgrading."""

import pytest
from builders import make_membership
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_manual_submission_migration_preserves_legacy_rows() -> None:
    previous = [("feedback", "0002_report_notification_operation")]
    current = [("feedback", "0003_manual_submission_key")]
    actor = make_membership()
    executor = MigrationExecutor(connection)
    executor.migrate(previous)
    try:
        apps = executor.loader.project_state(previous).apps
        report = apps.get_model("feedback", "Report").objects.create(
            workspace_id=actor.workspace_id, submitted_by_id=actor.pk, title="Legacy report"
        )
        source = apps.get_model("feedback", "ReportSource").objects.create(
            report_id=report.pk, workspace_id=actor.workspace_id, kind="manual"
        )
        before = apps.get_model("feedback", "ReportSource").objects.values().get(pk=source.pk)
        executor = MigrationExecutor(connection)
        executor.migrate(current)
        apps = executor.loader.project_state(current).apps
        after = apps.get_model("feedback", "ReportSource").objects.values().get(pk=source.pk)
        assert after.pop("submission_key") is None
        assert after == before
        assert (
            apps.get_model("feedback", "Report").objects.get(pk=report.pk).title == "Legacy report"
        )
    finally:
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        MigrationExecutor(connection).migrate(latest)
