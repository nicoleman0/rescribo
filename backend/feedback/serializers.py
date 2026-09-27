"""API contracts for feedback reads, manual capture, and triage."""

from typing import Any
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import Membership
from accounts.views import ErrorSerializer
from feedback.inbox import InboxFilters
from feedback.models import Activity, EngineeringIssue, Problem, Report, ReportSource
from feedback.problem_reads import ActivityReferences
from feedback.submissions import ReportSubmission

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


class ReportDetailSerializer(serializers.Serializer):
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


class ProblemListItemSerializer(serializers.Serializer):
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


class EngineeringIssueSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    number = serializers.IntegerField()
    url = serializers.CharField()
    title = serializers.CharField()
    state = serializers.ChoiceField(choices=EngineeringIssue.State.choices)
    state_reason = serializers.CharField()
    access = serializers.ChoiceField(choices=EngineeringIssue.Access.choices)
    provider_updated_at = serializers.DateTimeField()
    last_synced_at = serializers.DateTimeField(allow_null=True)
    sync_error = serializers.CharField()


class ProblemDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    summary = serializers.CharField()
    state = serializers.ChoiceField(choices=Problem.State.choices)
    owner = MemberSummarySerializer(allow_null=True)
    report_count = serializers.IntegerField()
    needs_review = serializers.BooleanField()
    resolution_revision = serializers.IntegerField()
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    engineering_issue = serializers.SerializerMethodField()

    @extend_schema_field(EngineeringIssueSerializer(allow_null=True))
    def get_engineering_issue(self, problem: Problem) -> Any:
        active = getattr(problem, "active_issues", None)
        issue = active[0] if active else None
        return EngineeringIssueSerializer(issue).data if issue is not None else None


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


class LinkIssueSerializer(VersionedSerializer):
    reference = serializers.CharField(max_length=500)


class ReportConflictSerializer(ErrorSerializer):
    current = ReportDetailSerializer()


class ProblemConflictSerializer(ErrorSerializer):
    current = ProblemDetailSerializer()


class IssueLinkConflictSerializer(ProblemConflictSerializer):
    problem_id = serializers.UUIDField(required=False)
