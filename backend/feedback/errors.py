"""Errors raised by feedback domain use cases."""

from typing import Any
from uuid import UUID


class FeedbackError(Exception):
    reason = "feedback_error"

    def __init__(self, reason: str | None = None, *, message: str | None = None) -> None:
        if reason is not None:
            self.reason = reason
        super().__init__(self.reason if message is None else message)


class TitleRequired(FeedbackError, ValueError):
    reason = "title_required"


class NoChanges(FeedbackError, ValueError):
    reason = "no_changes"


class NotFound(FeedbackError, LookupError):
    def __init__(self, *, record: str) -> None:
        self.record = record
        super().__init__(f"{record}_not_found")


class AlreadyLinked(FeedbackError):
    reason = "already_linked"


class InvalidSourceKind(FeedbackError, ValueError):
    reason = "invalid_source_kind"


class ReasonRequired(FeedbackError, ValueError):
    reason = "reason_required"


class InvalidReference(FeedbackError, ValueError):
    reason = "invalid_reference"

    def __init__(self, *, field: str) -> None:
        self.field = field
        super().__init__()


class VersionConflict(FeedbackError):
    reason = "version_conflict"

    def __init__(self, *, current: Any) -> None:
        self.current = current
        super().__init__()


class InvalidTransition(FeedbackError):
    reason = "invalid_transition"

    def __init__(self, *, action: str, from_state: str) -> None:
        self.action = action
        self.from_state = from_state
        super().__init__()


class ConnectionNotReady(FeedbackError):
    reason = "connection_not_ready"


class IssueReferenceRejected(FeedbackError, ValueError):
    reason = "issue_reference_rejected"

    def __init__(self, *, detail: str) -> None:
        self.detail = detail
        super().__init__()


class IssueAlreadyLinked(FeedbackError):
    reason = "issue_already_linked"


class IssueAlreadyLinkedElsewhere(FeedbackError):
    reason = "issue_linked_elsewhere"

    def __init__(self, *, problem_id: UUID, problem_title: str) -> None:
        self.problem_id = problem_id
        self.problem_title = problem_title
        super().__init__()


class IssueProviderUnavailable(FeedbackError):
    reason = "issue_provider_unavailable"
