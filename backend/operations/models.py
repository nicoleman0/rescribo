import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class InboundReceipt(models.Model):
    class Provider(models.TextChoices):
        GITHUB = "github", "GitHub"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=16, choices=Provider.choices)
    delivery_id = models.CharField(max_length=128)
    event = models.CharField(max_length=64)
    action = models.CharField(max_length=64, blank=True)
    installation_id = models.CharField(max_length=64, blank=True)
    repository_id = models.CharField(max_length=64, blank=True)
    issue_id = models.CharField(max_length=64, blank=True)
    normalized = models.JSONField(default=dict)
    received_at = models.DateTimeField(default=timezone.now)
    provider_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    safe_error = models.CharField(max_length=64, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "delivery_id"], name="unique_inbound_delivery"
            )
        ]
        indexes = [models.Index(fields=["status", "retry_at"], name="receipt_due_idx")]


class ExternalOperation(models.Model):
    class Kind(models.TextChoices):
        GITHUB_ISSUE_CREATE = "github_issue_create", "Create GitHub issue"

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain"
        CANCELLED = "cancelled", "Cancelled"

    UNRESOLVED_STATES = (State.QUEUED, State.RUNNING, State.UNCERTAIN)
    TITLE_LIMIT = 256
    BODY_LIMIT = 10000

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    workspace = models.ForeignKey("accounts.Workspace", on_delete=models.CASCADE)
    connection = models.ForeignKey("connections.Connection", on_delete=models.PROTECT)
    problem = models.ForeignKey("feedback.Problem", on_delete=models.CASCADE)
    requester = models.ForeignKey("accounts.Membership", on_delete=models.PROTECT)
    action_key = models.UUIDField()
    state = models.CharField(max_length=16, choices=State.choices, default=State.DRAFT)
    title = models.CharField(max_length=TITLE_LIMIT)
    body = models.TextField(max_length=BODY_LIMIT)
    destination = models.CharField(max_length=200)
    repository_id = models.CharField(max_length=64, blank=True, default="")
    problem_version = models.PositiveIntegerField()
    binding_revision = models.PositiveIntegerField()
    draft_version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    due_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    remote_issue_id = models.CharField(max_length=64, blank=True)
    remote_number = models.PositiveIntegerField(null=True, blank=True)
    remote_url = models.URLField(max_length=500, blank=True)
    safe_error = models.CharField(max_length=64, blank=True)
    recovery_requested = models.BooleanField(default=False)
    recovery_attempts = models.PositiveIntegerField(default=0)
    resolved_by = models.ForeignKey(
        "accounts.Membership",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="resolved_issue_operations",
    )
    resolution_reason = models.TextField(blank=True, max_length=2000)
    recovery_reference = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "action_key"], name="operation_workspace_action_key"
            ),
            models.UniqueConstraint(
                fields=["problem"],
                condition=Q(state__in=["queued", "running", "uncertain"]),
                name="one_unresolved_issue_create_per_problem",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "due_at"], name="external_operation_due_idx"),
            models.Index(fields=["workspace", "problem", "state"], name="external_op_problem_idx"),
        ]
