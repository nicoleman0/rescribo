"""Slack integration boundary for capture, identity, and follow-up delivery."""

from integrations.slack.capture import CapturedReport, resolve_report_permalink
from integrations.slack.delivery import (
    DeliveredMessage,
    DeliveryRejected,
    SlackConnectionGuard,
    send_delayed_dm,
)
from integrations.slack.errors import ChannelRejected, slack_error_code
from integrations.slack.identity import (
    LinkCodeRejected,
    LinkCodeStore,
    SlackIdentity,
    require_linked_actor,
)
from integrations.slack.lifecycle import AppUninstalled, parse_app_uninstalled
from integrations.slack.modals import (
    CaptureSubmission,
    SubmissionErrors,
    build_capture_modal,
    parse_capture_submission,
)
from integrations.slack.policy import (
    REQUIRED_BOT_SCOPES,
    ChannelEligibilityCache,
    SlackChannel,
    validate_channel,
)
from integrations.slack.shortcuts import (
    MessageShortcut,
    ShortcutPayloadError,
    check_source_allowed,
    parse_message_shortcut,
)
from integrations.slack.signing import InvalidSlackSignature, verify_slack_signature

__all__ = [
    "REQUIRED_BOT_SCOPES",
    "AppUninstalled",
    "CaptureSubmission",
    "CapturedReport",
    "ChannelEligibilityCache",
    "ChannelRejected",
    "DeliveredMessage",
    "DeliveryRejected",
    "InvalidSlackSignature",
    "LinkCodeRejected",
    "LinkCodeStore",
    "MessageShortcut",
    "ShortcutPayloadError",
    "SlackChannel",
    "SlackConnectionGuard",
    "SlackIdentity",
    "SubmissionErrors",
    "build_capture_modal",
    "check_source_allowed",
    "parse_app_uninstalled",
    "parse_capture_submission",
    "parse_message_shortcut",
    "require_linked_actor",
    "resolve_report_permalink",
    "send_delayed_dm",
    "slack_error_code",
    "validate_channel",
    "verify_slack_signature",
]
