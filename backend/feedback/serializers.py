"""API contracts for feedback reads, manual capture, and triage."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Membership
from accounts.views import ErrorSerializer
from connections.errors import ERROR_DETAILS
from feedback.follow_ups import BUCKETS
from feedback.inbox import InboxFilters
from feedback.models import (
    Activity,
    EngineeringIssue,
    FollowUp,
    Problem,
    Report,
    ReportNotificationOperation,
    ReportSource,
)
from feedback.problem_reads import ActivityReferences
from feedback.submissions import ReportSubmission
from matching.models import MatchRun
from operations.models import ExternalOperation

UNASSIGNED = "unassigned"


class MemberSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    # Members see names only; email addresses stay with owners.
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, membership: Membership) -> str:
        return membership.user.full_name or "Unnamed member"


class ProblemSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    state = serializers.ChoiceField(choices=Problem.State.choices)


class ReportProvenanceSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ReportSource.Kind.choices)
    permalink = serializers.CharField()
    permalink_error = serializers.CharField()
    author_display_name = serializers.CharField()
    snapshot_text = serializers.CharField()
    captured_at = serializers.DateTimeField()


class ReportListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    customer_label = serializers.CharField()
    triage_state = serializers.ChoiceField(choices=Report.TriageState.choices)
    source_kind = serializers.ChoiceField(source="source.kind", choices=ReportSource.Kind.choices)
    assignee = MemberSummarySerializer(allow_null=True)
    problem = ProblemSummarySerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    # Latest match run state; `failed` means suggestions are unavailable.
    match_state = serializers.ChoiceField(choices=MatchRun.State.choices, allow_null=True)


class ReportDetailSerializer(serializers.Serializer):
    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_follow_up_revision(self, report: Report) -> int | None:
        if report.problem_id is None:
            return None
        follow_ups = getattr(report, "active_follow_ups", None)
        if follow_ups is not None:
            follow_up = next(
                (item for item in follow_ups if item.problem_id == report.problem_id), None
            )
        else:
            follow_up = (
                report.follow_ups.filter(problem_id=report.problem_id)
                .order_by("-resolution_revision")
                .first()
            )
        return follow_up.resolution_revision if follow_up is not None else None

    follow_up_revision = serializers.SerializerMethodField()
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    customer_label = serializers.CharField()
    customer_contact_reference = serializers.CharField()
    affected_version = serializers.CharField()
    triage_state = serializers.ChoiceField(choices=Report.TriageState.choices)
    provenance = ReportProvenanceSerializer(source="source")
    submitted_by = MemberSummarySerializer()
    assignee = MemberSummarySerializer(allow_null=True)
    problem = ProblemSummarySerializer(allow_null=True)
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ManualReportSerializer(serializers.Serializer):
    submission_key = serializers.UUIDField()
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    customer_label = serializers.CharField(max_length=200, required=False, allow_blank=True)
    customer_contact_reference = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )
    affected_version = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def to_submission(self) -> ReportSubmission:
        data = self.validated_data
        return ReportSubmission(
            title=data["title"],
            description=data.get("description", ""),
            customer_label=data.get("customer_label", ""),
            customer_contact_reference=data.get("customer_contact_reference", ""),
            affected_version=data.get("affected_version", ""),
            source=None,
            submission_key=data["submission_key"],
        )


class AssigneeFilterField(serializers.CharField):
    """Accept a membership ID or the literal ``unassigned``."""

    def to_internal_value(self, data: Any) -> str:
        value = super().to_internal_value(data)
        if value == UNASSIGNED:
            return value
        try:
            return str(UUID(value))
        except ValueError:
            raise serializers.ValidationError(
                f"Use a member ID or '{UNASSIGNED}'.", code="invalid"
            ) from None


class InboxFilterSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200, required=False, allow_blank=True)
    customer = serializers.CharField(max_length=200, required=False, allow_blank=True)
    triage_state = serializers.ChoiceField(choices=Report.TriageState.choices, required=False)
    assignee = AssigneeFilterField(required=False)
    source_kind = serializers.ChoiceField(choices=ReportSource.Kind.choices, required=False)

    def to_filters(self) -> InboxFilters:
        data = self.validated_data
        assignee = data.get("assignee")
        return InboxFilters(
            text=data.get("q", ""),
            customer=data.get("customer", ""),
            triage_state=data.get("triage_state"),
            assignee_id=UUID(assignee) if assignee not in (None, UNASSIGNED) else None,
            unassigned=assignee == UNASSIGNED,
            source_kind=data.get("source_kind"),
        )


SUMMARY_EXCERPT_LENGTH = 160


class ProblemFilterSerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200, required=False, allow_blank=True)


class ExternalOperationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=ExternalOperation.State.choices)
    destination = serializers.CharField()
    remote_issue_id = serializers.CharField()
    remote_number = serializers.IntegerField(allow_null=True)
    remote_url = serializers.CharField()
    safe_error = serializers.CharField()
    recovery_requested = serializers.BooleanField()
    error_detail = serializers.SerializerMethodField()

    def get_error_detail(self, operation: ExternalOperation) -> str:
        return OPERATION_ERROR_DETAILS.get(
            operation.safe_error,
            "Check the GitHub repository and connection before trying again."
            if operation.safe_error
            else "",
        )

    created_at = serializers.DateTimeField()
    approved_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)


class EngineeringIssueSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.IntegerField()
    url = serializers.CharField()
    title = serializers.CharField()
    state = serializers.ChoiceField(choices=EngineeringIssue.State.choices)
    state_reason = serializers.CharField()
    access = serializers.ChoiceField(choices=EngineeringIssue.Access.choices)
    repository = serializers.CharField(source="connection.repository")
    provider_updated_at = serializers.DateTimeField()
    last_synced_at = serializers.DateTimeField(source="last_successful_sync_at", allow_null=True)
    last_attempted_sync_at = serializers.DateTimeField(allow_null=True)
    refresh_status = serializers.SerializerMethodField()
    access_reason = serializers.SerializerMethodField()
    access_detail = serializers.SerializerMethodField()
    sync_error = serializers.CharField()
    stale = serializers.SerializerMethodField()
    stale_after = serializers.SerializerMethodField()

    def get_refresh_status(self, issue: EngineeringIssue) -> str:
        if issue.sync_lease_token is not None:
            return "running"
        if issue.sync_requested_generation > issue.sync_completed_generation:
            return "pending"
        return "idle"

    def get_access_reason(self, issue: EngineeringIssue) -> str:
        return issue.access_reason

    def get_access_detail(self, issue: EngineeringIssue) -> str:
        reason = issue.access_reason
        return ERROR_DETAILS.get(
            reason, "Check the GitHub connection and refresh this issue." if reason else ""
        )

    def get_stale_after(self, issue: EngineeringIssue) -> Any:
        if issue.last_successful_sync_at is None:
            return None
        return issue.last_successful_sync_at + timedelta(
            seconds=2 * settings.RESCRIBO_GITHUB_RECONCILIATION_INTERVAL_SECONDS
        )

    def get_stale(self, issue: EngineeringIssue) -> bool:
        stale_after = self.get_stale_after(issue)
        return stale_after is None or stale_after < timezone.now()


class ProblemIssueSerializer(serializers.Serializer):
    engineering_issue = serializers.SerializerMethodField()

    @extend_schema_field(EngineeringIssueSerializer(allow_null=True))
    def get_engineering_issue(self, problem: Problem) -> Any:
        active = getattr(problem, "active_issues", None)
        issue = active[0] if active else None
        return EngineeringIssueSerializer(issue).data if issue is not None else None


class ProblemListItemSerializer(ProblemIssueSerializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    summary_excerpt = serializers.SerializerMethodField()
    state = serializers.ChoiceField(choices=Problem.State.choices)
    owner = MemberSummarySerializer(allow_null=True)
    report_count = serializers.IntegerField()
    needs_review = serializers.BooleanField()
    created_at = serializers.DateTimeField()

    def get_summary_excerpt(self, problem: Problem) -> str:
        summary = " ".join(problem.summary.split())
        if len(summary) <= SUMMARY_EXCERPT_LENGTH:
            return summary
        return summary[: SUMMARY_EXCERPT_LENGTH - 1].rstrip() + "…"


class ProblemDetailSerializer(ProblemIssueSerializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    summary = serializers.CharField()
    state = serializers.ChoiceField(choices=Problem.State.choices)
    owner = MemberSummarySerializer(allow_null=True)
    report_count = serializers.IntegerField()
    needs_review = serializers.BooleanField()
    resolution_revision = serializers.IntegerField()
    fix_note = serializers.CharField()
    fix_version = serializers.CharField()
    fix_evidence_url = serializers.URLField(allow_blank=True)
    fix_confirmed_at = serializers.DateTimeField(allow_null=True)
    fix_confirmed_by = MemberSummarySerializer(allow_null=True)
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    current_create_operation = serializers.SerializerMethodField()

    @extend_schema_field(ExternalOperationSerializer(allow_null=True))
    def get_current_create_operation(self, problem: Problem) -> Any:
        operation = (
            ExternalOperation.objects.filter(
                workspace_id=problem.workspace_id,
                problem_id=problem.pk,
                kind=ExternalOperation.Kind.GITHUB_ISSUE_CREATE,
            )
            .exclude(state__in=["draft", "cancelled"])
            .order_by("-created_at")
            .first()
        )
        return ExternalOperationSerializer(operation).data if operation is not None else None


class RecordReferenceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()


class ProblemActivitySerializer(serializers.Serializer):
    """Activity with its ID references resolved to names the member may already read."""

    id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=Activity.Action.choices)
    actor = MemberSummarySerializer(source="actor_membership", allow_null=True)
    actor_system = serializers.CharField()
    created_at = serializers.DateTimeField()
    report = serializers.SerializerMethodField()
    from_problem = serializers.SerializerMethodField()
    to_problem = serializers.SerializerMethodField()
    from_assignee = serializers.SerializerMethodField()
    to_assignee = serializers.SerializerMethodField()
    changed_fields = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()

    @property
    def references(self) -> ActivityReferences:
        return self.context["references"]

    def _record(self, table: dict[str, Any], activity: Activity, key: str) -> Any:
        value = activity.metadata.get(key)
        record = table.get(str(value)) if value else None
        return None if record is None else {"id": record.pk, "title": record.title}

    def _member(self, activity: Activity, key: str) -> Any:
        value = activity.metadata.get(key)
        member = self.references.members.get(str(value)) if value else None
        return None if member is None else MemberSummarySerializer(member).data

    @extend_schema_field(RecordReferenceSerializer(allow_null=True))
    def get_report(self, activity: Activity) -> Any:
        return self._record(self.references.reports, activity, "report_id")

    @extend_schema_field(RecordReferenceSerializer(allow_null=True))
    def get_from_problem(self, activity: Activity) -> Any:
        return self._record(self.references.problems, activity, "from_problem_id")

    @extend_schema_field(RecordReferenceSerializer(allow_null=True))
    def get_to_problem(self, activity: Activity) -> Any:
        return self._record(self.references.problems, activity, "to_problem_id")

    @extend_schema_field(MemberSummarySerializer(allow_null=True))
    def get_from_assignee(self, activity: Activity) -> Any:
        return self._member(activity, "from_assignee_id")

    @extend_schema_field(MemberSummarySerializer(allow_null=True))
    def get_to_assignee(self, activity: Activity) -> Any:
        return self._member(activity, "to_assignee_id")

    def get_changed_fields(self, activity: Activity) -> list[str]:
        return [str(name) for name in activity.metadata.get("fields", [])]

    @extend_schema_field(serializers.ChoiceField(choices=Problem.State.choices, allow_null=True))
    def get_state(self, activity: Activity) -> str | None:
        return activity.metadata.get("state")


class VersionedSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)


class LinkReportSerializer(VersionedSerializer):
    problem_id = serializers.UUIDField()


class CreateProblemForReportSerializer(VersionedSerializer):
    title = serializers.CharField(max_length=200)
    summary = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)


class AssignReportSerializer(VersionedSerializer):
    assignee_id = serializers.UUIDField(allow_null=True)


class ProblemEditSerializer(VersionedSerializer):
    title = serializers.CharField(max_length=200, required=False)
    summary = serializers.CharField(max_length=10000, required=False, allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "title" not in attrs and "summary" not in attrs:
            raise serializers.ValidationError(
                {"title": ["Change the title or the summary."]}, code="required"
            )
        return attrs


class ProblemOwnerSerializer(VersionedSerializer):
    owner_id = serializers.UUIDField(allow_null=True)


class FixApplicabilitySerializer(VersionedSerializer):
    expected_resolution_revision = serializers.IntegerField(min_value=1)


class FixConfirmationSerializer(VersionedSerializer):
    fix_note = serializers.CharField(max_length=10000, allow_blank=False)
    fix_version = serializers.CharField(max_length=100, allow_blank=False)
    evidence_url = serializers.URLField(max_length=500, required=False, allow_blank=True)


class LinkIssueSerializer(VersionedSerializer):
    reference = serializers.CharField(max_length=500)
    replace = serializers.BooleanField(required=False, default=False)


class IssuePreviewSerializer(serializers.Serializer):
    title = serializers.CharField()
    body = serializers.CharField()


class IssueDraftSerializer(serializers.Serializer):
    draft_id = serializers.UUIDField(required=False)
    expected_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(
        max_length=ExternalOperation.TITLE_LIMIT, required=False, allow_blank=False
    )
    body = serializers.CharField(
        max_length=ExternalOperation.BODY_LIMIT, required=False, allow_blank=True
    )


class IssueDraftResultSerializer(serializers.Serializer):
    marker = serializers.CharField()
    id = serializers.UUIDField()
    draft_version = serializers.IntegerField()
    expires_at = serializers.DateTimeField()
    title = serializers.CharField()
    body = serializers.CharField()
    repository = serializers.CharField()
    visibility = serializers.CharField()


class IssueApproveSerializer(serializers.Serializer):
    draft_id = serializers.UUIDField()
    draft_version = serializers.IntegerField(min_value=1)
    approved = serializers.BooleanField()


class IssueRecoverySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=500, required=False, allow_blank=False)


class IssueRefreshSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField()


class IssueRefreshStatusSerializer(serializers.Serializer):
    issue_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["pending", "running", "idle"])


class IssueRecoveryResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=ExternalOperation.State.choices)


class ReportConflictSerializer(ErrorSerializer):
    current = ReportDetailSerializer()


class ProblemConflictSerializer(ErrorSerializer):
    current = ProblemDetailSerializer()


class IssueLinkConflictSerializer(ProblemConflictSerializer):
    problem_id = serializers.UUIDField(required=False)


class IssueAbandonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, allow_blank=False)


OPERATION_ERROR_DETAILS = {
    "marker_not_found": (
        "No matching issue was found. Check the repository before stopping recovery."
    ),
    "multiple_marker_matches": (
        "Several issues match this request. Enter the issue reference you want to recover."
    ),
    "recovered_binding_conflict": (
        "The issue exists, but the selected repository or problem link "
        "changed. Review the issue before stopping recovery."
    ),
    "rate_limited": "GitHub asked us to wait. Creation retries after the delay, up to a limit.",
    "recovery_unavailable": "GitHub could not be checked. Retry after checking the connection.",
    "worker_lease_expired": (
        "The worker stopped before recording the result. Check whether GitHub created the issue."
    ),
    "write_outcome_unknown": "GitHub did not confirm the result. Check whether the issue exists.",
    "disconnected": (
        "GitHub refused the connection before the issue was created. Reconnect GitHub, "
        "then approve again."
    ),
    "manually_resolved": "Recovery was stopped after a member reviewed the result.",
}


class FollowUpNotificationSerializer(serializers.Serializer):
    """The one non-cancelled notification row, or null when not yet prepared."""

    id = serializers.UUIDField()
    send_in_progress = serializers.SerializerMethodField()
    state = serializers.ChoiceField(choices=ReportNotificationOperation.State.choices)
    message = serializers.CharField()
    draft_version = serializers.IntegerField()
    safe_error = serializers.CharField()
    attempts = serializers.IntegerField()
    approved_by = MemberSummarySerializer(allow_null=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    sent_at = serializers.DateTimeField(allow_null=True)
    delivery_confirmed_by = MemberSummarySerializer(allow_null=True)
    delivery_confirmed_at = serializers.DateTimeField(allow_null=True)
    invalidated_at = serializers.DateTimeField(allow_null=True)
    invalidation_reason = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    @extend_schema_field(serializers.BooleanField())
    def get_send_in_progress(self, operation: ReportNotificationOperation) -> bool:
        return operation.lease_token is not None


class FollowUpListItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    report_title = serializers.CharField(source="report.title")
    customer_label = serializers.CharField(source="report.customer_label")
    recipient = MemberSummarySerializer()
    contact_state = serializers.ChoiceField(choices=FollowUp.ContactState.choices)
    delivery_state = serializers.ChoiceField(
        source="active_notification_state",
        choices=ReportNotificationOperation.State.choices,
        allow_null=True,
    )
    resolution_revision = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class FollowUpFilterSerializer(serializers.Serializer):
    bucket = serializers.ChoiceField(choices=BUCKETS, required=False)

    def to_filters(self) -> Any:
        bucket: str | None = self.validated_data.get("bucket")
        return {"bucket": bucket} if bucket is not None else {"bucket": None}


class FollowUpReportSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    customer_label = serializers.CharField()
    triage_state = serializers.ChoiceField(choices=Report.TriageState.choices)
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class FollowUpProblemSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    fix_note = serializers.CharField()
    fix_version = serializers.CharField()
    resolution_revision = serializers.IntegerField()


class FollowUpRecipientSerializer(serializers.Serializer):
    member = MemberSummarySerializer(source="recipient")
    has_slack_link = serializers.SerializerMethodField()

    def get_has_slack_link(self, follow_up: FollowUp) -> bool:
        from feedback.follow_ups import has_slack_identity

        return has_slack_identity(follow_up)


class FollowUpOutcomeSerializer(serializers.Serializer):
    state = serializers.ChoiceField(source="contact_state", choices=FollowUp.ContactState.choices)
    note = serializers.CharField(source="outcome_note")
    at = serializers.DateTimeField(source="outcome_at", allow_null=True)
    by = MemberSummarySerializer(source="outcome_by", allow_null=True)


class FollowUpHistoryItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=Activity.Action.choices)
    actor = MemberSummarySerializer(source="actor_membership", allow_null=True)
    actor_system = serializers.CharField()
    created_at = serializers.DateTimeField()


class FollowUpDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    report = FollowUpReportSummarySerializer()
    problem = FollowUpProblemSummarySerializer()
    recipient = FollowUpRecipientSerializer(source="*")
    notification = serializers.SerializerMethodField()
    outcome = FollowUpOutcomeSerializer(source="*")
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    history = serializers.SerializerMethodField()

    def get_notification(self, follow_up: FollowUp) -> Any:
        from feedback.follow_ups import current_notification

        operation = current_notification(follow_up)
        return FollowUpNotificationSerializer(operation).data if operation else None

    def get_history(self, follow_up: FollowUp) -> Any:
        from feedback.follow_ups import follow_up_history

        return FollowUpHistoryItemSerializer(
            follow_up_history(workspace_id=follow_up.workspace_id, follow_up=follow_up)[:50],
            many=True,
        ).data


class FollowUpNotificationEditSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=10000, allow_blank=False)
    notification_id = serializers.UUIDField()
    draft_version = serializers.IntegerField(min_value=1)


class FollowUpNotificationApproveSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField()
    draft_version = serializers.IntegerField(min_value=1)


class FollowUpNotificationActionSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField()
    draft_version = serializers.IntegerField(min_value=1)


class FollowUpNotificationSendAgainSerializer(FollowUpNotificationActionSerializer):
    checked_slack = serializers.BooleanField()


class FollowUpOutcomeRecordSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=FollowUp.ContactState.choices)
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    expected_version = serializers.IntegerField(min_value=1)


class FollowUpOutcomeCorrectSerializer(FollowUpOutcomeRecordSerializer):
    reason = serializers.CharField(max_length=2000, allow_blank=True)


class FollowUpRecipientChangeSerializer(serializers.Serializer):
    new_recipient_id = serializers.UUIDField()
