"""Slack integration boundary for capture, identity, and follow-up delivery."""

from integrations.slack.delivery import (
    DeliveredMessage,
    DeliveryRejected,
    SlackConnectionGuard,
    send_delayed_dm,
)
from integrations.slack.errors import ChannelRejected, slack_error_code
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
    "DeliveredMessage",
    "DeliveryRejected",
    "InvalidSlackSignature",
    "MessageShortcut",
    "ShortcutPayloadError",
    "SlackChannel",
    "SlackConnectionGuard",
    "SubmissionErrors",
    "build_capture_modal",
    "build_notice_modal",
    "parse_capture_submission",
    "parse_message_shortcut",
    "send_delayed_dm",
    "slack_error_code",
    "validate_channel",
    "verify_slack_signature",
]
