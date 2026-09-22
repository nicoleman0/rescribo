"""Workspace-scoped customer feedback domain records."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Membership, Workspace


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
