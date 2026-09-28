"""Thin HTTP adapters for reports, problems, and triage actions."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from django.db.models import QuerySet
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import exceptions
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.views import ErrorSerializer, WorkspaceView
from feedback.engineering_issues import create_issue, link_issue, preview_issue, refresh_issue
from feedback.errors import FeedbackError, NotFound, TitleRequired
from feedback.http import FeedbackPagination, feedback_error_response, invalid_request
from feedback.inbox import get_report, search_reports, workspace_directory
from feedback.models import Activity, Problem, Report
from feedback.problem_reads import (
    activity_references,
    get_problem,
    problem_activity,
    problem_reports,
    search_problems,
)
from feedback.problems import ProblemChanges, assign_problem_owner, update_problem
from feedback.reports import (
    assign_report,
    create_problem_and_link_report,
    dismiss_report,
    link_report,
    restore_report,
    submit_report,
    unlink_report,
)
from feedback.serializers import (
    AssignReportSerializer,
    CreateIssueSerializer,
    CreateProblemForReportSerializer,
    InboxFilterSerializer,
    IssueCreationUncertainSerializer,
    IssueLinkConflictSerializer,
    IssuePreviewSerializer,
    LinkIssueSerializer,
    LinkReportSerializer,
    ManualReportSerializer,
    MemberSummarySerializer,
    ProblemActivitySerializer,
    ProblemConflictSerializer,
    ProblemDetailSerializer,
    ProblemEditSerializer,
    ProblemFilterSerializer,
    ProblemListItemSerializer,
    ProblemOwnerSerializer,
    ReportConflictSerializer,
    ReportDetailSerializer,
    ReportListItemSerializer,
    VersionedSerializer,
)

READ_ERRORS = {401: ErrorSerializer, 404: ErrorSerializer}
WRITE_ERRORS = {
    400: ErrorSerializer,
    401: ErrorSerializer,
    403: ErrorSerializer,
    404: ErrorSerializer,
}


@method_decorator(csrf_protect, name="dispatch")
class ReportListView(ListModelMixin, WorkspaceView, GenericAPIView):
    serializer_class = ReportListItemSerializer
    pagination_class = FeedbackPagination

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
        responses={
            200: ReportDetailSerializer,
            201: ReportDetailSerializer,
            400: ErrorSerializer,
            **READ_ERRORS,
        },
    )
    def post(self, request: Request, workspace_id: UUID) -> Response:
        data = ManualReportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            result = submit_report(actor=self.membership, submission=data.to_submission())
        except TitleRequired:
            return Response(
                {
                    "detail": "The request could not be completed.",
                    "reason": "title_required",
                    "field_errors": {"title": ["title_required"]},
                },
                status=400,
            )
        report = get_report(actor=self.membership, report_id=result.report.pk)
        return Response(ReportDetailSerializer(report).data, status=201 if result.created else 200)


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


class ProblemListView(ListModelMixin, WorkspaceView, GenericAPIView):
    serializer_class = ProblemListItemSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self) -> QuerySet[Problem]:
        filters = ProblemFilterSerializer(data=self.request.query_params)
        if not filters.is_valid():
            raise exceptions.ValidationError(filters.errors)
        return search_problems(actor=self.membership, text=filters.validated_data.get("q", ""))

    @extend_schema(
        parameters=[ProblemFilterSerializer],
        responses={200: ProblemListItemSerializer(many=True), 400: ErrorSerializer, **READ_ERRORS},
    )
    def get(self, request: Request, workspace_id: UUID) -> Response:
        return self.list(request)


class ProblemDetailView(WorkspaceView):
    @extend_schema(responses={200: ProblemDetailSerializer, **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        try:
            problem = get_problem(actor=self.membership, problem_id=problem_id)
        except NotFound:
            raise exceptions.NotFound() from None
        return Response(ProblemDetailSerializer(problem).data)


class ProblemReportListView(ListModelMixin, WorkspaceView, GenericAPIView):
    serializer_class = ReportDetailSerializer
    pagination_class = FeedbackPagination

    def get_queryset(self) -> QuerySet[Report]:
        try:
            return problem_reports(actor=self.membership, problem_id=self.kwargs["problem_id"])
        except NotFound:
            raise exceptions.NotFound() from None

    @extend_schema(responses={200: ReportDetailSerializer(many=True), **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        return self.list(request)


class ProblemActivityListView(WorkspaceView, GenericAPIView):
    serializer_class = ProblemActivitySerializer
    pagination_class = FeedbackPagination

    def get_queryset(self) -> QuerySet[Activity]:
        try:
            return problem_activity(actor=self.membership, problem_id=self.kwargs["problem_id"])
        except NotFound:
            raise exceptions.NotFound() from None

    @extend_schema(responses={200: ProblemActivitySerializer(many=True), **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        page = self.paginate_queryset(self.get_queryset())
        if page is None:
            raise AssertionError("Problem activity is always paginated.")
        references = activity_references(actor=self.membership, rows=page)
        rows = ProblemActivitySerializer(page, many=True, context={"references": references})
        return self.get_paginated_response(rows.data)


@method_decorator(csrf_protect, name="dispatch")
class ReportActionView(WorkspaceView):
    """Run one report triage use case and return the updated report."""

    input_serializer: type[VersionedSerializer] = VersionedSerializer
    success_status = 200

    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        raise NotImplementedError

    def post(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        data = self.input_serializer(data=request.data)
        if not data.is_valid():
            return invalid_request(data.errors)
        try:
            report = self.perform(report_id, data.validated_data)
        except FeedbackError as error:
            return feedback_error_response(error, current=self._current(report_id))
        report = get_report(actor=self.membership, report_id=report.pk)
        return Response(ReportDetailSerializer(report).data, status=self.success_status)

    def _current(self, report_id: UUID) -> Callable[[], Any]:
        return lambda: (
            ReportDetailSerializer(get_report(actor=self.membership, report_id=report_id)).data
        )


def report_action_schema(
    request: type[VersionedSerializer], success_status: int = 200
) -> Callable[[Any], Any]:
    return extend_schema(
        request=request,
        responses={
            success_status: ReportDetailSerializer,
            409: ReportConflictSerializer,
            **WRITE_ERRORS,
        },
    )


@extend_schema_view(post=report_action_schema(LinkReportSerializer))
class ReportLinkView(ReportActionView):
    input_serializer = LinkReportSerializer

    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return link_report(
            actor=self.membership,
            report_id=report_id,
            expected_version=data["expected_version"],
            problem_id=data["problem_id"],
        )


@extend_schema_view(post=report_action_schema(CreateProblemForReportSerializer, 201))
class ReportCreateProblemView(ReportActionView):
    input_serializer = CreateProblemForReportSerializer
    success_status = 201

    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return create_problem_and_link_report(
            actor=self.membership,
            report_id=report_id,
            expected_version=data["expected_version"],
            title=data["title"],
            summary=data.get("summary", ""),
            owner_id=data.get("owner_id"),
        )


@extend_schema_view(post=report_action_schema(AssignReportSerializer))
class ReportAssignView(ReportActionView):
    input_serializer = AssignReportSerializer

    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return assign_report(
            actor=self.membership,
            report_id=report_id,
            expected_version=data["expected_version"],
            assignee_id=data["assignee_id"],
        )


@extend_schema_view(post=report_action_schema(VersionedSerializer))
class ReportUnlinkView(ReportActionView):
    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return unlink_report(
            actor=self.membership, report_id=report_id, expected_version=data["expected_version"]
        )


@extend_schema_view(post=report_action_schema(VersionedSerializer))
class ReportDismissView(ReportActionView):
    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return dismiss_report(
            actor=self.membership, report_id=report_id, expected_version=data["expected_version"]
        )


@extend_schema_view(post=report_action_schema(VersionedSerializer))
class ReportRestoreView(ReportActionView):
    def perform(self, report_id: UUID, data: dict[str, Any]) -> Report:
        return restore_report(
            actor=self.membership, report_id=report_id, expected_version=data["expected_version"]
        )


@method_decorator(csrf_protect, name="dispatch")
class ProblemActionView(WorkspaceView):
    """Run one problem use case and return the updated problem."""

    input_serializer: type[VersionedSerializer] = VersionedSerializer
    success_status = 200

    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        raise NotImplementedError

    def post(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        data = self.input_serializer(data=request.data)
        if not data.is_valid():
            return invalid_request(data.errors)
        try:
            problem = self.perform(problem_id, data.validated_data)
        except FeedbackError as error:
            return feedback_error_response(
                error,
                current=lambda: (
                    ProblemDetailSerializer(
                        get_problem(actor=self.membership, problem_id=problem_id)
                    ).data
                ),
            )
        problem = get_problem(actor=self.membership, problem_id=problem.pk)
        return Response(ProblemDetailSerializer(problem).data, status=self.success_status)


def problem_action_schema(request: type[VersionedSerializer]) -> Callable[[Any], Any]:
    return extend_schema(
        request=request,
        responses={200: ProblemDetailSerializer, 409: ProblemConflictSerializer, **WRITE_ERRORS},
    )


@extend_schema_view(post=problem_action_schema(ProblemEditSerializer))
class ProblemEditView(ProblemActionView):
    input_serializer = ProblemEditSerializer

    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        return update_problem(
            actor=self.membership,
            problem_id=problem_id,
            expected_version=data["expected_version"],
            changes=ProblemChanges(title=data.get("title"), summary=data.get("summary")),
        )


@extend_schema_view(post=problem_action_schema(ProblemOwnerSerializer))
class ProblemOwnerView(ProblemActionView):
    input_serializer = ProblemOwnerSerializer

    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        return assign_problem_owner(
            actor=self.membership,
            problem_id=problem_id,
            expected_version=data["expected_version"],
            owner_id=data["owner_id"],
        )


@extend_schema_view(
    post=extend_schema(
        request=LinkIssueSerializer,
        responses={200: ProblemDetailSerializer, 409: IssueLinkConflictSerializer, **WRITE_ERRORS},
    )
)
class ProblemIssueLinkView(ProblemActionView):
    input_serializer = LinkIssueSerializer

    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        issue = link_issue(
            actor=self.membership,
            problem_id=problem_id,
            expected_version=data["expected_version"],
            reference=data["reference"],
        )
        return issue.problem


class ProblemIssuePreviewView(WorkspaceView):
    @extend_schema(responses={200: IssuePreviewSerializer, **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        try:
            preview = preview_issue(actor=self.membership, problem_id=problem_id)
        except NotFound:
            raise exceptions.NotFound() from None
        return Response(IssuePreviewSerializer(preview).data)


@extend_schema_view(
    post=extend_schema(
        request=CreateIssueSerializer,
        responses={
            201: ProblemDetailSerializer,
            409: IssueCreationUncertainSerializer,
            **WRITE_ERRORS,
        },
    )
)
class ProblemIssueCreateView(ProblemActionView):
    input_serializer = CreateIssueSerializer
    success_status = 201

    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        issue = create_issue(
            actor=self.membership,
            problem_id=problem_id,
            expected_version=data["expected_version"],
            title=data["title"],
            body=data["body"],
        )
        return issue.problem


@extend_schema_view(post=problem_action_schema(VersionedSerializer))
class ProblemIssueRefreshView(ProblemActionView):
    def perform(self, problem_id: UUID, data: dict[str, Any]) -> Problem:
        return refresh_issue(
            actor=self.membership,
            problem_id=problem_id,
            expected_version=data["expected_version"],
        )
