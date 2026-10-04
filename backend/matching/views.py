"""Thin HTTP adapters for match suggestions."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.views import ErrorSerializer, WorkspaceView
from feedback.errors import FeedbackError
from feedback.http import feedback_error_response, invalid_request
from matching.decisions import (
    MatchNotRetryable,
    SuggestionDecided,
    SuggestionNotCurrent,
    accept_suggestion,
    latest_run,
    reject_suggestion,
    retry_match,
    suggestion_report_id,
)
from matching.serializers import (
    AcceptSuggestionSerializer,
    ReportMatchConflictSerializer,
    ReportMatchSerializer,
)

CONFLICT_DETAILS: dict[type[FeedbackError], str] = {
    SuggestionNotCurrent: "This suggestion is out of date. Review the current suggestions.",
    SuggestionDecided: "This suggestion already has a decision.",
    MatchNotRetryable: "Only a failed match for an untriaged report can be retried.",
}
ERRORS = {401: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {
    400: ErrorSerializer,
    403: ErrorSerializer,
    409: ReportMatchConflictSerializer,
    **ERRORS,
}


class MatchView(WorkspaceView):
    def report_match(self, report_id: UUID) -> dict[str, Any]:
        # Read the run even when off, so access checks are the same either way.
        run = latest_run(actor=self.membership, report_id=report_id)
        enabled = settings.RESCRIBO_MATCH_SUGGESTIONS_ENABLED
        return ReportMatchSerializer(
            {"suggestions_enabled": enabled, "run": run if enabled else None}
        ).data

    def disabled(self) -> Response | None:
        if settings.RESCRIBO_MATCH_SUGGESTIONS_ENABLED:
            return None
        return Response(
            {"detail": "Match suggestions are turned off.", "reason": "suggestions_disabled"},
            status=404,
        )

    def error(self, error: FeedbackError, current: Callable[[], Any]) -> Response:
        detail = CONFLICT_DETAILS.get(type(error))
        if detail is None:
            return feedback_error_response(error, current=current)
        return Response(
            {"detail": detail, "reason": error.reason, "field_errors": {}, "current": current()},
            status=409,
        )


class ReportMatchView(MatchView):
    @extend_schema(responses={200: ReportMatchSerializer, **ERRORS})
    def get(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        try:
            return Response(self.report_match(report_id))
        except FeedbackError as error:
            return feedback_error_response(error, current=lambda: None)


@method_decorator(csrf_protect, name="dispatch")
class ReportMatchRetryView(MatchView):
    @extend_schema(request=None, responses={202: ReportMatchSerializer, **WRITE_ERRORS})
    def post(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        if disabled := self.disabled():
            return disabled
        try:
            retry_match(actor=self.membership, report_id=report_id)
        except FeedbackError as error:
            return self.error(error, lambda: self.report_match(report_id))
        return Response(self.report_match(report_id), status=202)


@method_decorator(csrf_protect, name="dispatch")
class SuggestionDecisionView(MatchView):
    def decide(self, suggestion_id: UUID, data: dict[str, Any]) -> None:
        raise NotImplementedError

    def handle(self, suggestion_id: UUID, data: dict[str, Any]) -> Response:
        if disabled := self.disabled():
            return disabled

        def current() -> dict[str, Any]:
            return self.report_match(
                suggestion_report_id(actor=self.membership, suggestion_id=suggestion_id)
            )

        try:
            self.decide(suggestion_id, data)
        except FeedbackError as error:
            return self.error(error, current)
        return Response(current())


class SuggestionAcceptView(SuggestionDecisionView):
    """Links the report through the normal version-checked linking use case."""

    def decide(self, suggestion_id: UUID, data: dict[str, Any]) -> None:
        accept_suggestion(
            actor=self.membership,
            suggestion_id=suggestion_id,
            expected_version=data["expected_version"],
        )

    @extend_schema(
        request=AcceptSuggestionSerializer, responses={200: ReportMatchSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request, workspace_id: UUID, suggestion_id: UUID) -> Response:
        data = AcceptSuggestionSerializer(data=request.data)
        if not data.is_valid():
            return invalid_request(data.errors)
        return self.handle(suggestion_id, data.validated_data)


class SuggestionRejectView(SuggestionDecisionView):
    def decide(self, suggestion_id: UUID, data: dict[str, Any]) -> None:
        reject_suggestion(actor=self.membership, suggestion_id=suggestion_id)

    @extend_schema(request=None, responses={200: ReportMatchSerializer, **WRITE_ERRORS})
    def post(self, request: Request, workspace_id: UUID, suggestion_id: UUID) -> Response:
        return self.handle(suggestion_id, {})
