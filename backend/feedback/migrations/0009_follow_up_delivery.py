# Notification rows predate the follow-up link; deletion clears the way for the required FK.

import django.db.models.deletion
import django.utils.timezone
from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def delete_notification_rows(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ReportNotificationOperation = apps.get_model("feedback", "ReportNotificationOperation")
    ReportNotificationOperation.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("feedback", "0008_report_source_permalink_state"),
    ]

    operations = [
        migrations.RunPython(
            delete_notification_rows, migrations.RunPython.noop, hints={"target_db": "default"}
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="follow_up",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="notifications",
                to="feedback.followup",
            ),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="message",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="draft_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="approved_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="accounts.membership",
            ),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="delivery_confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="accounts.membership",
            ),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="delivery_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="due_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="lease_token",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="lease_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reportnotificationoperation",
            name="safe_error",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="followup",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RemoveConstraint(
            model_name="reportnotificationoperation",
            name="notification_sent_has_remote_result",
        ),
        migrations.AddConstraint(
            model_name="reportnotificationoperation",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("sent_at__isnull", False),
                        ("state", "sent"),
                        models.Q(
                            models.Q(("remote_message_id", ""), _negated=True),
                            ("delivery_confirmed_at__isnull", False),
                            _connector="OR",
                        ),
                    ),
                    models.Q(models.Q(("state", "sent"), _negated=True), ("sent_at__isnull", True)),
                    _connector="OR",
                ),
                name="notification_sent_has_remote_result",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="reportnotificationoperation",
            name="notification_invalidation_matches_state",
        ),
        migrations.AddConstraint(
            model_name="reportnotificationoperation",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("invalidated_at__isnull", False), ("state", "cancelled")),
                    ("state__in", ["uncertain", "sent"]),
                    models.Q(
                        models.Q(("state__in", ["cancelled", "uncertain", "sent"]), _negated=True),
                        ("invalidated_at__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="notification_invalidation_matches_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="reportnotificationoperation",
            constraint=models.UniqueConstraint(
                condition=~models.Q(state="cancelled"),
                fields=["follow_up"],
                name="one_active_notification_per_follow_up",
            ),
        ),
        migrations.AlterField(
            model_name="activity",
            name="action",
            field=models.CharField(
                choices=[
                    ("report.deleted", "Report deleted"),
                    ("report.created", "Report created"),
                    ("report.updated", "Report updated"),
                    ("report.assigned", "Report assigned"),
                    ("report.linked", "Report linked"),
                    ("report.unlinked", "Report unlinked"),
                    ("report.dismissed", "Report dismissed"),
                    ("report.restored", "Report restored"),
                    ("problem.created", "Problem created"),
                    ("problem.updated", "Problem updated"),
                    ("problem.state_changed", "Problem state changed"),
                    ("problem.fix_confirmed", "Problem fix confirmed"),
                    ("engineering_issue.linked", "Engineering issue linked"),
                    ("engineering_issue.created", "Engineering issue created"),
                    ("engineering_issue.unlinked", "Engineering issue unlinked"),
                    ("follow_up.notification_approved", "Notification approved"),
                    ("follow_up.notification_sent", "Notification sent"),
                    ("follow_up.notification_failed", "Notification failed"),
                    ("follow_up.notification_cancelled", "Notification cancelled"),
                    ("follow_up.outcome_recorded", "Outcome recorded"),
                    ("follow_up.outcome_corrected", "Outcome corrected"),
                    ("follow_up.recipient_changed", "Recipient changed"),
                ],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="reportnotificationoperation",
            name="invalidation_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("disconnected", "Connection disconnected"),
                    ("reassigned", "Report reassigned"),
                    ("moved", "Report moved to another problem"),
                    ("unlinked", "Report ungrouped"),
                    ("issue_reopened", "Linked GitHub issue reopened"),
                    ("issue_relinked", "GitHub issue link replaced"),
                    ("stale", "Approval no longer matched the report"),
                    ("member_cancelled", "Cancelled by a member"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="activity",
            name="record_type",
            field=models.CharField(
                choices=[("report", "Report"), ("problem", "Problem"), ("follow_up", "Follow up")],
                max_length=10,
            ),
        ),
    ]
