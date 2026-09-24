"""API contracts for feedback reads and manual capture."""

from typing import Any
from uuid import UUID

from rest_framework import serializers

from feedback.inbox import InboxFilters
from feedback.models import Problem, Report, ReportSource
from feedback.submissions import ReportSubmission

UNASSIGNED = "unassigned"


class MemberSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email")


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
