"""Slack integration boundary for the message shortcut capture flow."""

from integrations.slack.modals import (
    CaptureSubmission,
    SubmissionErrors,
    build_capture_modal,
    parse_capture_submission,
)
from integrations.slack.shortcuts import (
    MessageShortcut,
    ShortcutPayloadError,
    SourceRejected,
    check_source_allowed,
    parse_message_shortcut,
)
from integrations.slack.signing import InvalidSlackSignature, verify_slack_signature

__all__ = [
    "CaptureSubmission",
    "InvalidSlackSignature",
    "MessageShortcut",
    "ShortcutPayloadError",
    "SourceRejected",
    "SubmissionErrors",
    "build_capture_modal",
    "check_source_allowed",
    "parse_capture_submission",
    "parse_message_shortcut",
    "verify_slack_signature",
]
