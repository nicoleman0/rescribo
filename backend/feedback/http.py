"""HTTP translation of feedback domain errors, shared by report and problem views."""

from collections.abc import Callable
from typing import Any

from rest_framework import exceptions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from feedback.errors import (
    AlreadyLinked,
    ConnectionNotReady,
    FeedbackError,
    InvalidReference,
    InvalidTransition,
    IssueAlreadyLinked,
    IssueAlreadyLinkedElsewhere,
    IssueProviderUnavailable,
    IssueReferenceRejected,
    NoChanges,
    NotFound,
    TitleRequired,
    VersionConflict,
)

CONFLICT_DETAILS: dict[type[FeedbackError], str] = {
    VersionConflict: "This record changed since you loaded it. Review the current version.",
    InvalidTransition: "This action is not available in the record's current state.",
    AlreadyLinked: "The report is already linked to this problem.",
    IssueAlreadyLinked: "This issue is already linked to this problem.",
    NoChanges: "Nothing would change.",
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
    if isinstance(error, ConnectionNotReady):
        return Response(
            {
                "detail": "Connect an active GitHub repository before working with issues.",
                "reason": error.reason,
                "field_errors": {},
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
    detail = CONFLICT_DETAILS.get(type(error))
    if detail is None:
        raise error
    return Response(
        {"detail": detail, "reason": error.reason, "field_errors": {}, "current": current()},
        status=409,
    )
