"""Thin HTTP adapters for inbox reads and manual report capture."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.views import ErrorSerializer, WorkspaceView
from feedback.errors import FeedbackError, NotFound
from feedback.inbox import get_report, search_reports, workspace_directory
from feedback.models import Report
from feedback.reports import submit_report
from feedback.serializers import (
    InboxFilterSerializer,
    ManualReportSerializer,
    MemberSummarySerializer,
    ReportDetailSerializer,
    ReportListItemSerializer,
)

READ_ERRORS = {401: ErrorSerializer, 404: ErrorSerializer}


def invalid_request(field_errors: Any) -> Response:
    return Response(
        {
            "detail": "Check the submitted fields.",
            "reason": "invalid_request",
            "field_errors": field_errors,
        },
        status=400,
    )


def feedback_error_response(error: FeedbackError) -> Response:
    field = "title" if error.reason == "title_required" else getattr(error, "field", None)
    return Response(
        {
            "detail": "The request could not be completed.",
            "reason": error.reason,
            "field_errors": {field: [error.reason]} if field else {},
        },
        status=400,
    )


class ReportPagination(PageNumberPagination):
    page_size = 25


@method_decorator(csrf_protect, name="dispatch")
class ReportListView(ListModelMixin, WorkspaceView, GenericAPIView):
    serializer_class = ReportListItemSerializer
    pagination_class = ReportPagination

    def get_queryset(self) -> QuerySet[Report]:
        filters = InboxFilterSerializer(data=self.request.query_params)
        if not filters.is_valid():
            raise exceptions.ValidationError(filters.errors)
        return search_reports(actor=self.membership, filters=filters.to_filters())

    @extend_schema(
        parameters=[InboxFilterSerializer],
        responses={200: ReportListItemSerializer(many=True), 400: ErrorSerializer, **READ_ERRORS},
    )
    def get(self, request: Request, workspace_id: UUID) -> Response:
        return self.list(request)

    @extend_schema(
        request=ManualReportSerializer,
        responses={201: ReportDetailSerializer, 400: ErrorSerializer, **READ_ERRORS},
    )
    def post(self, request: Request, workspace_id: UUID) -> Response:
        data = ManualReportSerializer(data=request.data)
        if not data.is_valid():
            return invalid_request(data.errors)
        try:
            result = submit_report(actor=self.membership, submission=data.to_submission())
        except FeedbackError as error:
            return feedback_error_response(error)
        report = get_report(actor=self.membership, report_id=result.report.pk)
        return Response(ReportDetailSerializer(report).data, status=201)


class ReportDetailView(WorkspaceView):
    @extend_schema(responses={200: ReportDetailSerializer, **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        try:
            report = get_report(actor=self.membership, report_id=report_id)
        except NotFound:
            raise exceptions.NotFound() from None
        return Response(ReportDetailSerializer(report).data)


class MemberDirectoryView(WorkspaceView):
    @extend_schema(responses={200: MemberSummarySerializer(many=True), **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID) -> Response:
        rows = workspace_directory(actor=self.membership)
        return Response(MemberSummarySerializer(rows, many=True).data)
