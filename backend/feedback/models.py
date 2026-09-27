"""Workspace-scoped customer feedback domain records."""

import uuid
from typing import Any

from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Membership, Workspace
from connections.models import Connection


class Problem(models.Model):
    class State(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        FIX_AVAILABLE = "fix_available", "Fix available"
        NOT_PLANNED = "not_planned", "Not planned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="problems")
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="owned_problems"
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.OPEN)
    not_planned_reason = models.TextField(blank=True, default="")
    resolution_revision = models.PositiveIntegerField(default=0)
    fix_note = models.TextField(blank=True, default="")
    fix_confirmed_at = models.DateTimeField(null=True, blank=True)
    fix_confirmed_by = models.ForeignKey(
        Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    needs_review = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(state="not_planned") | ~Q(not_planned_reason=""),
                name="problem_not_planned_reason_required",
            ),
            models.CheckConstraint(
                condition=~Q(state="fix_available") | Q(resolution_revision__gte=1),
                name="problem_fix_revision_required",
            ),
        ]
        indexes = [models.Index(fields=["workspace", "state"], name="problem_ws_state_idx")]


class Report(models.Model):
    class TriageState(models.TextChoices):
        NEW = "new", "New"
        LINKED = "linked", "Linked"
        DISMISSED = "dismissed", "Dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    customer_label = models.CharField(max_length=200, blank=True, default="")
    customer_contact_reference = models.CharField(max_length=200, blank=True, default="")
    affected_version = models.CharField(max_length=100, blank=True, default="")
    submitted_by = models.ForeignKey(
        Membership, on_delete=models.PROTECT, related_name="submitted_reports"
    )
    assignee = models.ForeignKey(
        Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_reports"
    )
    problem = models.ForeignKey(
        Problem, null=True, blank=True, on_delete=models.PROTECT, related_name="reports"
    )
    triage_state = models.CharField(
        max_length=12, choices=TriageState.choices, default=TriageState.NEW
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(triage_state="linked", problem__isnull=False)
                | (~Q(triage_state="linked") & Q(problem__isnull=True)),
                name="report_link_state_matches_problem",
            )
        ]
        indexes = [
            models.Index(
                fields=["workspace", "triage_state", "created_at"],
                name="report_ws_triage_created_idx",
            ),
            models.Index(fields=["workspace", "assignee"], name="report_ws_assignee_idx"),
            models.Index(fields=["workspace", "problem"], name="report_ws_problem_idx"),
        ]


class ReportSource(models.Model):
    class Kind(models.TextChoices):
        MANUAL = "manual", "Manual"
        SLACK = "slack", "Slack"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.OneToOneField(Report, on_delete=models.CASCADE, related_name="source")
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="report_sources"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    submission_key = models.UUIDField(null=True, blank=True)
    external_workspace_id = models.CharField(max_length=64, blank=True, default="")
    external_channel_id = models.CharField(max_length=64, blank=True, default="")
    external_message_id = models.CharField(max_length=64, blank=True, default="")
    permalink = models.URLField(max_length=500, blank=True, default="")
    author_external_id = models.CharField(max_length=64, blank=True, default="")
    author_display_name = models.CharField(max_length=200, blank=True, default="")
    snapshot_text = models.TextField(blank=True, default="")
    captured_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workspace",
                    "kind",
                    "external_workspace_id",
                    "external_channel_id",
                    "external_message_id",
                ],
                condition=~Q(kind="manual"),
                name="unique_external_report_source",
            ),
            models.UniqueConstraint(
                fields=["workspace", "submission_key"],
                condition=Q(kind="manual", submission_key__isnull=False),
                name="unique_manual_report_submission",
            ),
            models.CheckConstraint(
                condition=Q(kind="manual") | Q(submission_key__isnull=True),
                name="submission_key_only_for_manual",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="manual",
                        external_workspace_id="",
                        external_channel_id="",
                        external_message_id="",
                    )
                    | (
                        ~Q(kind="manual")
                        & ~Q(external_workspace_id="")
                        & ~Q(external_channel_id="")
                        & ~Q(external_message_id="")
                    )
                ),
                name="report_source_external_ids_match_kind",
            ),
        ]


class Activity(models.Model):
    class Action(models.TextChoices):
        REPORT_DELETED = "report.deleted", "Report deleted"
        REPORT_CREATED = "report.created", "Report created"
        REPORT_UPDATED = "report.updated", "Report updated"
        REPORT_ASSIGNED = "report.assigned", "Report assigned"
        REPORT_LINKED = "report.linked", "Report linked"
        REPORT_UNLINKED = "report.unlinked", "Report unlinked"
        REPORT_DISMISSED = "report.dismissed", "Report dismissed"
        REPORT_RESTORED = "report.restored", "Report restored"
        PROBLEM_CREATED = "problem.created", "Problem created"
        PROBLEM_UPDATED = "problem.updated", "Problem updated"
        PROBLEM_STATE_CHANGED = "problem.state_changed", "Problem state changed"
        PROBLEM_FIX_CONFIRMED = "problem.fix_confirmed", "Problem fix confirmed"
        ENGINEERING_ISSUE_LINKED = "engineering_issue.linked", "Engineering issue linked"
        ENGINEERING_ISSUE_CREATED = "engineering_issue.created", "Engineering issue created"
        ENGINEERING_ISSUE_UNLINKED = "engineering_issue.unlinked", "Engineering issue unlinked"

    class RecordType(models.TextChoices):
        REPORT = "report", "Report"
        PROBLEM = "problem", "Problem"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="activities")
    actor_membership = models.ForeignKey(
        Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    actor_system = models.CharField(max_length=32, blank=True, default="")
    action = models.CharField(max_length=64, choices=Action.choices)
    record_type = models.CharField(max_length=10, choices=RecordType.choices)
    record_id = models.UUIDField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(actor_membership__isnull=False, actor_system="")
                    | Q(actor_membership__isnull=True) & ~Q(actor_system="")
                ),
                name="activity_exactly_one_actor",
            )
        ]
        indexes = [
            models.Index(
                fields=["workspace", "record_type", "record_id", "created_at"],
                name="activity_record_idx",
            )
        ]


class ReportNotificationOperation(models.Model):
    """One prepared employee notification for a report, as captured at preparation time.

    This is the persisted record later delivery work extends. Rows are never retargeted:
    triage changes cancel or invalidate them, and a fresh preview creates a new row.
    """

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"

    class InvalidationReason(models.TextChoices):
        DISCONNECTED = "disconnected", "Connection disconnected"
        REASSIGNED = "reassigned", "Report reassigned"
        MOVED = "moved", "Report moved to another problem"
        UNLINKED = "unlinked", "Report ungrouped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="report_notification_operations"
    )
    # History outlives triage changes, so referenced rows cannot be deleted from under it.
    report = models.ForeignKey(
        Report, on_delete=models.PROTECT, related_name="notification_operations"
    )
    problem = models.ForeignKey(Problem, on_delete=models.PROTECT, related_name="+")
    recipient = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    resolution_revision = models.PositiveIntegerField()
    report_version = models.PositiveIntegerField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT)
    remote_conversation_id = models.CharField(max_length=64, blank=True, default="")
    remote_message_id = models.CharField(max_length=64, blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    invalidation_reason = models.CharField(
        max_length=16, choices=InvalidationReason.choices, blank=True, default=""
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(state="sent", sent_at__isnull=False)
                & ~Q(remote_conversation_id="")
                & ~Q(remote_message_id="")
                | ~Q(state="sent") & Q(sent_at__isnull=True),
                name="notification_sent_has_remote_result",
            ),
            models.CheckConstraint(
                condition=Q(invalidated_at__isnull=True, invalidation_reason="")
                | Q(invalidated_at__isnull=False) & ~Q(invalidation_reason=""),
                name="notification_invalidation_complete",
            ),
            # Only cancelled or uncertain rows carry an invalidation. An uncertain send keeps
            # its state because the remote write may have happened.
            models.CheckConstraint(
                condition=Q(state="cancelled", invalidated_at__isnull=False)
                | Q(state="uncertain")
                | ~Q(state__in=["cancelled", "uncertain"]) & Q(invalidated_at__isnull=True),
                name="notification_invalidation_matches_state",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "report", "state"], name="notification_ws_report_idx")
        ]


class EngineeringIssue(models.Model):
    """A GitHub issue linked to a problem. Superseding a link keeps the old row for history."""

    class State(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    class Access(models.TextChoices):
        OK = "ok", "OK"
        ACCESS_LOST = "access_lost", "Access lost"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="engineering_issues"
    )
    problem = models.ForeignKey(
        Problem, on_delete=models.PROTECT, related_name="engineering_issues"
    )
    connection = models.ForeignKey(Connection, on_delete=models.PROTECT, related_name="+")
    repository_id = models.CharField(max_length=64)
    issue_id = models.CharField(max_length=64)
    number = models.PositiveIntegerField()
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=256)
    state = models.CharField(max_length=10, choices=State.choices)
    state_reason = models.CharField(max_length=32, blank=True, default="")
    access = models.CharField(max_length=16, choices=Access.choices, default=Access.OK)
    provider_updated_at = models.DateTimeField()
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_error = models.CharField(max_length=200, blank=True, default="")
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    unlinked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["problem"], condition=Q(active=True), name="one_active_issue_per_problem"
            ),
            models.UniqueConstraint(
                fields=["workspace", "repository_id", "issue_id"],
                condition=Q(active=True),
                name="one_active_problem_per_issue",
            ),
        ]
        indexes = [models.Index(fields=["workspace", "active"], name="eng_issue_ws_active_idx")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Cross-table invariants cannot be expressed as a PostgreSQL CHECK constraint.
        assert self.workspace_id == self.problem.workspace_id, (
            "An engineering issue must share its problem's workspace."
        )
        super().save(*args, **kwargs)
