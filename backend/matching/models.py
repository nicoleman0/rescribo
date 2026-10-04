"""Workspace-scoped match runs and the suggestions members decide on."""

import uuid
from typing import Any

from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Membership, Workspace
from feedback.models import Problem, Report
from matching.contract import ErrorCategory


class MatchRun(models.Model):
    """One ranking of a report version. Stores IDs and versions, never report text."""

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        RANKED = "ranked", "Ranked"
        ABSTAINED = "abstained", "Abstained"
        FAILED = "failed", "Failed"
        STALE = "stale", "Stale"

    ACTIVE_STATES = (State.PENDING, State.RUNNING)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="+")
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="match_runs")
    report_version = models.PositiveIntegerField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    failure = models.CharField(
        max_length=24,
        choices=[(category.value, category.value) for category in ErrorCategory],
        blank=True,
        default="",
    )
    abstain_reason = models.CharField(max_length=24, blank=True, default="")
    contract_version = models.CharField(max_length=16)
    algorithm_version = models.CharField(max_length=64)
    config_version = models.CharField(max_length=64)
    matcher_build = models.CharField(max_length=64, blank=True, default="")
    # Ordered [{"id", "version", "linked_reports": [{"id", "version"}]}]; null until retrieved.
    candidates = models.JSONField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    due_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    retrieval_ms = models.PositiveIntegerField(null=True, blank=True)
    ranking_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["report"],
                condition=Q(state__in=["pending", "running"]),
                name="one_active_match_run_per_report",
            ),
            models.CheckConstraint(
                condition=Q(state="stale", failure="stale_snapshot")
                | Q(state="failed") & ~Q(failure="") & ~Q(failure="stale_snapshot")
                | ~Q(state__in=["failed", "stale"]) & Q(failure=""),
                name="match_run_failure_matches_state",
            ),
            models.CheckConstraint(
                condition=Q(state="abstained") & ~Q(abstain_reason="")
                | ~Q(state="abstained") & Q(abstain_reason=""),
                name="match_run_abstain_reason_matches_state",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "report", "created_at"], name="match_run_report_idx"),
            models.Index(fields=["state", "due_at"], name="match_run_due_idx"),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.workspace_id != self.report.workspace_id:
            raise ValueError("A match run must share its report's workspace.")
        super().save(*args, **kwargs)


class MatchSuggestion(models.Model):
    class Decision(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="+")
    run = models.ForeignKey(MatchRun, on_delete=models.CASCADE, related_name="suggestions")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    rank = models.PositiveSmallIntegerField()
    # A ranking signal, not a probability.
    score = models.FloatField()
    features = models.JSONField()
    # [{"record", "id", "field"}], validated against the run's request.
    evidence = models.JSONField()
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    decided_by = models.ForeignKey(
        Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["run", "rank"], name="unique_match_suggestion_rank"),
            models.UniqueConstraint(
                fields=["run", "problem"], name="unique_match_suggestion_problem"
            ),
            models.CheckConstraint(
                condition=Q(decision="pending", decided_by__isnull=True, decided_at__isnull=True)
                | ~Q(decision="pending") & Q(decided_by__isnull=False, decided_at__isnull=False),
                name="match_suggestion_decision_has_actor",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if (
            self.workspace_id != self.run.workspace_id
            or self.workspace_id != self.problem.workspace_id
            or (self.decided_by is not None and self.workspace_id != self.decided_by.workspace_id)
        ):
            raise ValueError("A suggestion, its run, problem, and decider share a workspace.")
        super().save(*args, **kwargs)
