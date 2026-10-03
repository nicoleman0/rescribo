"""Slack integration boundary for capture, identity, and follow-up delivery."""

from integrations.slack.errors import ChannelRejected, slack_error_code
from integrations.slack.messages import follow_up_message_blocks, outcome_message_blocks
from integrations.slack.modals import (
    CaptureSubmission,
    SubmissionErrors,
    build_capture_modal,
    build_notice_modal,
    parse_capture_submission,
)
from integrations.slack.policy import REQUIRED_BOT_SCOPES, SlackChannel, validate_channel
from integrations.slack.shortcuts import (
    MessageShortcut,
    ShortcutPayloadError,
    parse_message_shortcut,
)
from integrations.slack.signing import InvalidSlackSignature, verify_slack_signature

__all__ = [
    "REQUIRED_BOT_SCOPES",
    "CaptureSubmission",
    "ChannelRejected",
    "InvalidSlackSignature",
    "MessageShortcut",
    "ShortcutPayloadError",
    "SlackChannel",
    "SubmissionErrors",
    "build_capture_modal",
    "build_notice_modal",
    "follow_up_message_blocks",
    "outcome_message_blocks",
    "parse_capture_submission",
    "parse_message_shortcut",
    "slack_error_code",
    "validate_channel",
    "verify_slack_signature",
]
