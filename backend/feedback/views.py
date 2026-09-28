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
from feedback.engineering_issues import link_issue, preview_issue, refresh_issue
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
    CreateProblemForReportSerializer,
    ExternalOperationSerializer,
    InboxFilterSerializer,
    IssueAbandonSerializer,
    IssueApproveSerializer,
    IssueDraftResultSerializer,
    IssueDraftSerializer,
    IssueLinkConflictSerializer,
    IssuePreviewSerializer,
    IssueRecoveryResultSerializer,
    IssueRecoverySerializer,
    IssueRefreshSerializer,
    IssueRefreshStatusSerializer,
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
from operations.github_issue_create import (
    abandon_creation,
    approve_draft,
    create_draft,
    marker_for,
    operation_for_member,
    request_recovery,
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
            replace=data["replace"],
        )
        return issue.problem


class IssueOperationView(WorkspaceView):
    def operation_error(self, error: FeedbackError, problem_id: UUID) -> Response:
        return feedback_error_response(
            error,
            current=lambda: (
                ProblemDetailSerializer(
                    get_problem(actor=self.membership, problem_id=problem_id)
                ).data
            ),
        )


class ProblemIssuePreviewView(IssueOperationView):
    @extend_schema(responses={200: IssuePreviewSerializer, **READ_ERRORS})
    def get(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        try:
            preview = preview_issue(actor=self.membership, problem_id=problem_id)
        except NotFound:
            raise exceptions.NotFound() from None
        return Response(IssuePreviewSerializer(preview).data)

    @method_decorator(csrf_protect)
    @extend_schema(
        request=IssueDraftSerializer,
        responses={201: IssueDraftResultSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        data = IssueDraftSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            operation = create_draft(
                actor=self.membership,
                problem_id=problem_id,
                **data.validated_data,
            )
        except FeedbackError as error:
            return self.operation_error(error, problem_id)
        response = {
            "id": operation.pk,
            "draft_version": operation.draft_version,
            "expires_at": operation.expires_at,
            "title": operation.title,
            "body": operation.body,
            "marker": marker_for(operation.pk),
            "repository": operation.destination,
            "visibility": operation.connection.visibility,
        }
        return Response(IssueDraftResultSerializer(response).data, status=201)


@method_decorator(csrf_protect, name="dispatch")
class ProblemIssueApproveView(IssueOperationView):
    @extend_schema(
        request=IssueApproveSerializer, responses={202: ExternalOperationSerializer, **WRITE_ERRORS}
    )
    def post(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        data = IssueApproveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            operation = approve_draft(
                actor=self.membership, problem_id=problem_id, **data.validated_data
            )
        except FeedbackError as error:
            return self.operation_error(error, problem_id)
        return Response(ExternalOperationSerializer(operation).data, status=202)


class ProblemExternalOperationView(IssueOperationView):
    @extend_schema(responses={200: ExternalOperationSerializer, **READ_ERRORS})
    def get(
        self, request: Request, workspace_id: UUID, problem_id: UUID, operation_id: UUID
    ) -> Response:
        try:
            operation = operation_for_member(
                actor=self.membership,
                problem_id=problem_id,
                operation_id=operation_id,
            )
        except FeedbackError as error:
            return self.operation_error(error, problem_id)
        return Response(ExternalOperationSerializer(operation).data)


@method_decorator(csrf_protect, name="dispatch")
class ProblemIssueRecoveryView(IssueOperationView):
    @extend_schema(
        request=IssueRecoverySerializer,
        responses={202: IssueRecoveryResultSerializer, **WRITE_ERRORS},
    )
    def post(
        self, request: Request, workspace_id: UUID, problem_id: UUID, operation_id: UUID
    ) -> Response:
        data = IssueRecoverySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            operation = request_recovery(
                actor=self.membership,
                problem_id=problem_id,
                operation_id=operation_id,
                **data.validated_data,
            )
        except FeedbackError as error:
            return self.operation_error(error, problem_id)
        return Response(IssueRecoveryResultSerializer(operation).data, status=202)


@method_decorator(csrf_protect, name="dispatch")
class ProblemIssueAbandonView(IssueOperationView):
    @extend_schema(
        request=IssueAbandonSerializer, responses={200: ExternalOperationSerializer, **WRITE_ERRORS}
    )
    def post(
        self, request: Request, workspace_id: UUID, problem_id: UUID, operation_id: UUID
    ) -> Response:
        data = IssueAbandonSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            operation = abandon_creation(
                actor=self.membership,
                problem_id=problem_id,
                operation_id=operation_id,
                **data.validated_data,
            )
        except FeedbackError as error:
            return self.operation_error(error, problem_id)
        return Response(ExternalOperationSerializer(operation).data)


@method_decorator(csrf_protect, name="dispatch")
class ProblemIssueRefreshView(WorkspaceView):
    @extend_schema(
        request=IssueRefreshSerializer,
        responses={202: IssueRefreshStatusSerializer, **WRITE_ERRORS},
    )
    def post(self, request: Request, workspace_id: UUID, problem_id: UUID) -> Response:
        data = IssueRefreshSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            issue = refresh_issue(
                actor=self.membership,
                problem_id=problem_id,
                expected_issue_id=data.validated_data["issue_id"],
            )
        except NotFound:
            raise exceptions.NotFound() from None
        except FeedbackError as error:
            return feedback_error_response(
                error,
                current=lambda: (
                    ProblemDetailSerializer(
                        get_problem(actor=self.membership, problem_id=problem_id)
                    ).data
                ),
            )
        status = "running" if issue.sync_lease_token else "pending"
        return Response({"issue_id": issue.pk, "status": status}, status=202)
