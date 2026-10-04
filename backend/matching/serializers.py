"""API shapes for match runs and suggestions. Scores rank; they are not confidence."""

from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from feedback.serializers import ProblemSummarySerializer, VersionedSerializer
from matching.contract import ErrorCategory
from matching.models import MatchRun, MatchSuggestion

EVIDENCE_LABELS = {
    ("problem", "title"): "Problem title",
    ("problem", "summary"): "Problem summary",
    ("linked_report", "title"): "Linked report title",
    ("linked_report", "description"): "Linked report description",
}


class EvidenceSerializer(serializers.Serializer):
    record = serializers.ChoiceField(choices=["problem", "linked_report"])
    id = serializers.UUIDField()
    field = serializers.ChoiceField(choices=["title", "summary", "description"])
    explanation = serializers.SerializerMethodField()

    def get_explanation(self, evidence: dict[str, str]) -> str:
        return EVIDENCE_LABELS[(evidence["record"], evidence["field"])]


class MatchSuggestionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    rank = serializers.IntegerField()
    score = serializers.FloatField(help_text="Relative ranking signal, not a probability.")
    features = serializers.DictField(child=serializers.FloatField())
    evidence = EvidenceSerializer(many=True)
    problem = ProblemSummarySerializer()
    decision = serializers.ChoiceField(choices=MatchSuggestion.Decision.choices)
    decided_at = serializers.DateTimeField(allow_null=True)


class MatchRunSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    state = serializers.ChoiceField(choices=MatchRun.State.choices)
    failure = serializers.ChoiceField(
        choices=[category.value for category in ErrorCategory], allow_blank=True
    )
    abstain_reason = serializers.ChoiceField(
        choices=["no_candidates", "below_threshold", "insufficient_margin"], allow_blank=True
    )
    report_version = serializers.IntegerField()
    algorithm_version = serializers.CharField()
    config_version = serializers.CharField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
    suggestions = serializers.SerializerMethodField()

    @extend_schema_field(MatchSuggestionSerializer(many=True))
    def get_suggestions(self, run: MatchRun) -> list[dict[str, Any]]:
        suggestions = sorted(run.suggestions.all(), key=lambda suggestion: suggestion.rank)
        return MatchSuggestionSerializer(suggestions, many=True).data  # type: ignore[return-value]


class ReportMatchSerializer(serializers.Serializer):
    """The report's latest run, or null before the first one or while suggestions are off."""

    suggestions_enabled = serializers.BooleanField()
    run = MatchRunSerializer(allow_null=True)


class ReportMatchConflictSerializer(serializers.Serializer):
    detail = serializers.CharField()
    reason = serializers.CharField()
    field_errors = serializers.DictField()
    current = ReportMatchSerializer()


class AcceptSuggestionSerializer(VersionedSerializer):
    """`expected_version` is the report version the member saw."""
