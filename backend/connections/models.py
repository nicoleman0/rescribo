"""Persistent integration settings. Credentials never appear in API serializers."""

import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Membership, Workspace


class Connection(models.Model):
    class Provider(models.TextChoices):
        SLACK = "slack", "Slack"
        GITHUB = "github", "GitHub"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ERROR = "error", "Needs attention"
        DISCONNECTED = "disconnected", "Disconnected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    provider = models.CharField(max_length=10, choices=Provider.choices)
    external_id = models.CharField(max_length=64, blank=True)
    identity = models.CharField(max_length=200, blank=True)
    credential = models.TextField(blank=True)
    scopes = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DISCONNECTED)
    error_code = models.CharField(max_length=64, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_reconciled_at = models.DateTimeField(null=True, blank=True)
    repository = models.CharField(max_length=200, blank=True)
    repository_id = models.CharField(max_length=64, blank=True)
    visibility = models.CharField(max_length=16, blank=True)
    version = models.PositiveIntegerField(default=1)
    binding_revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "provider"], name="one_workspace_provider"
            ),
            models.UniqueConstraint(
                fields=["provider", "external_id"],
                condition=Q(provider="slack") & ~Q(external_id="") & ~Q(status="disconnected"),
                name="one_active_slack_team",
            ),
        ]


class AllowedChannel(models.Model):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name="channels")
    channel_id = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    is_private = models.BooleanField()
    verified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "channel_id"], name="unique_allowed_channel"
            )
        ]


class SetupState(models.Model):
    token_digest = models.CharField(max_length=64, primary_key=True)
    actor = models.ForeignKey(Membership, on_delete=models.CASCADE)
    session_digest = models.CharField(max_length=64)
    provider = models.CharField(max_length=10, choices=Connection.Provider.choices)
    repository = models.CharField(max_length=200, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class ExternalIdentity(models.Model):
    """A verified provider account, bound to one product membership."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    provider = models.CharField(max_length=10, choices=Connection.Provider.choices)
    provider_team_id = models.CharField(max_length=64)
    provider_user_id = models.CharField(max_length=64)
    linked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "provider", "provider_team_id", "provider_user_id"],
                name="unique_external_identity",
            ),
            models.UniqueConstraint(
                fields=["membership", "provider"], name="one_identity_per_membership"
            ),
        ]


class SlackLinkCode(models.Model):
    token_digest = models.CharField(max_length=64, primary_key=True)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class SlackCaptureContext(models.Model):
    """Server-side state for one open capture modal. Text is blanked once settled."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE)
    team_id = models.CharField(max_length=64)
    channel_id = models.CharField(max_length=64)
    actor_id = models.CharField(max_length=64)
    message_ts = models.CharField(max_length=64)
    thread_ts = models.CharField(max_length=64, blank=True)
    author_external_id = models.CharField(max_length=64, blank=True)
    text = models.TextField(blank=True)
    link_required = models.BooleanField(default=False)
    channel_validated_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at"], name="capture_context_expiry_idx")]
