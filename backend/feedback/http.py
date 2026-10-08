"""HTTP translation of feedback domain errors, shared by report and problem views."""

from collections.abc import Callable
from typing import Any

from rest_framework import exceptions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from feedback.errors import (
    AlreadyLinked,
    ConfirmationRequired,
    ConnectionNotReady,
    DeliveryNotReady,
    FeedbackError,
    InvalidReference,
    InvalidTransition,
    IssueAlreadyLinked,
    IssueAlreadyLinkedElsewhere,
    IssueCreateUnresolved,
    IssueOperationError,
    IssueProviderUnavailable,
    IssueReferenceRejected,
    MessageRequired,
    NoChanges,
    NotFound,
    ReasonRequired,
    ReleaseAccessMissing,
    ReleaseConnectionNotReady,
    ReleaseNotFound,
    ReleaseProviderUnavailable,
    TitleRequired,
    VersionConflict,
)

CONFLICT_DETAILS: dict[type[FeedbackError], str] = {
    VersionConflict: "This record changed since you loaded it. Review the current version.",
    InvalidTransition: "This action is not available in the record's current state.",
    AlreadyLinked: "The report is already linked to this problem.",
    IssueAlreadyLinked: "This issue is already linked to this problem.",
    NoChanges: "Nothing would change.",
    IssueCreateUnresolved: "Resolve pending issue creation before linking or creating an issue.",
}


class FeedbackPagination(PageNumberPagination):
    page_size = 25


def invalid_request(field_errors: Any) -> Response:
    return Response(
        {
            "detail": "Check the submitted fields.",
            "reason": "invalid_request",
            "field_errors": field_errors,
        },
        status=400,
    )


def feedback_error_response(error: FeedbackError, *, current: Callable[[], Any]) -> Response:
    """Map a domain error to a response. Every 409 carries the current authorised record."""
    if isinstance(error, NotFound):
        raise exceptions.NotFound()
    if isinstance(error, ReleaseAccessMissing):
        return Response(
            {
                "detail": "The GitHub App installation needs Contents read access.",
                "reason": error.reason,
                "field_errors": {},
                "current": current(),
            },
            status=409,
        )
    if isinstance(error, ReleaseConnectionNotReady):
        return Response(
            {
                "detail": "Connect an active GitHub repository before listing releases.",
                "reason": error.reason,
                "field_errors": {},
                "current": current(),
            },
            status=409,
        )
    if isinstance(error, ReleaseNotFound):
        return Response(
            {
                "detail": "The selected release is no longer available.",
                "reason": error.reason,
                "field_errors": {},
            },
            status=422,
        )
    if isinstance(error, ReleaseProviderUnavailable):
        return Response(
            {
                "detail": "GitHub releases are temporarily unavailable. Try again.",
                "reason": error.reason,
                "field_errors": {},
            },
            status=503,
        )
    if isinstance(error, InvalidReference):
        return Response(
            {
                "detail": "Choose an existing, active record in this workspace.",
                "reason": error.reason,
                "field_errors": {f"{error.field}_id": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, TitleRequired):
        return Response(
            {
                "detail": "Check the submitted fields.",
                "reason": error.reason,
                "field_errors": {"title": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, ReasonRequired):
        return Response(
            {
                "detail": "Provide a reason before continuing.",
                "reason": error.reason,
                "field_errors": {"reason": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, ConnectionNotReady):
        return Response(
            {
                "detail": "Connect an active GitHub repository before working with issues.",
                "reason": error.reason,
                "field_errors": {},
            },
            status=400,
        )
    if isinstance(error, DeliveryNotReady):
        return Response(
            {"detail": error.detail, "reason": error.reason, "field_errors": {}}, status=400
        )
    if isinstance(error, MessageRequired):
        return Response(
            {
                "detail": "Check the submitted fields.",
                "reason": error.reason,
                "field_errors": {"message": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, ConfirmationRequired):
        return Response(
            {
                "detail": "Confirm that you checked Slack before sending again.",
                "reason": error.reason,
                "field_errors": {"checked_slack": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, IssueReferenceRejected):
        return Response(
            {
                "detail": error.detail,
                "reason": error.reason,
                "field_errors": {"reference": [error.reason]},
            },
            status=400,
        )
    if isinstance(error, IssueProviderUnavailable):
        return Response(
            {
                "detail": "Check the GitHub connection status, then try again.",
                "reason": error.reason,
                "field_errors": {},
            },
            status=400,
        )
    if isinstance(error, IssueAlreadyLinkedElsewhere):
        return Response(
            {
                "detail": f'This issue is already linked to "{error.problem_title}".',
                "reason": error.reason,
                "field_errors": {},
                "problem_id": str(error.problem_id),
                "current": current(),
            },
            status=409,
        )
    if isinstance(error, IssueOperationError):
        return Response(
            {"detail": error.detail, "reason": error.reason, "field_errors": {}}, status=400
        )
    detail = CONFLICT_DETAILS.get(type(error))
    if detail is None:
        raise error
    return Response(
        {"detail": detail, "reason": error.reason, "field_errors": {}, "current": current()},
        status=409,
    )
