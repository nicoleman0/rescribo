"""Slack integration boundary for capture, identity, and follow-up delivery."""

from integrations.slack.capture import CapturedReport, resolve_report_permalink
from integrations.slack.delivery import (
    DeliveredMessage,
    DeliveryRejected,
    SlackConnectionGuard,
    send_delayed_dm,
)
from integrations.slack.identity import (
    LinkCodeRejected,
    LinkCodeStore,
    SlackIdentity,
    redeem_for_shortcut,
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
    ChannelRejected,
    SlackChannel,
    validate_channel,
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
    "AppUninstalled",
    "CapturedReport",
    "ChannelEligibilityCache",
    "ChannelRejected",
    "CaptureSubmission",
    "DeliveredMessage",
    "DeliveryRejected",
    "InvalidSlackSignature",
    "LinkCodeRejected",
    "LinkCodeStore",
    "MessageShortcut",
    "ShortcutPayloadError",
    "SourceRejected",
    "SlackChannel",
    "SlackConnectionGuard",
    "SlackIdentity",
    "SubmissionErrors",
    "build_capture_modal",
    "check_source_allowed",
    "parse_capture_submission",
    "parse_app_uninstalled",
    "parse_message_shortcut",
    "REQUIRED_BOT_SCOPES",
    "require_linked_actor",
    "redeem_for_shortcut",
    "resolve_report_permalink",
    "send_delayed_dm",
    "validate_channel",
    "verify_slack_signature",
]
