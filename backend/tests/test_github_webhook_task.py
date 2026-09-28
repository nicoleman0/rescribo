"""Tests for the Celery task that dispatches a verified GitHub delivery."""

from typing import Any
from unittest.mock import patch

from feedback.tasks import process_github_delivery
from integrations.github_app.webhooks import InstallationEvent, IssueEvent


def test_issues_event_dispatches_to_apply_issue_webhook() -> None:
    payload: dict[str, Any] = {
        "action": "closed",
        "installation": {"id": 42},
        "issue": {
            "id": 555,
            "number": 7,
            "state_reason": "completed",
            "updated_at": "2026-09-20T21:00:00Z",
        },
        "repository": {"id": 999, "full_name": "acme/widgets"},
    }
    with patch("feedback.tasks.apply_issue_webhook") as apply_issue:
        process_github_delivery(event_name="issues", payload=payload)

    apply_issue.assert_called_once()
    kwargs = apply_issue.call_args.kwargs
    assert kwargs["installation_id"] == "42"
    assert kwargs["event"] == IssueEvent(
        action="closed",
        number=7,
        repository="acme/widgets",
        state_reason="completed",
        updated_at="2026-09-20T21:00:00Z",
        repository_id="999",
        issue_id="555",
    )


def test_untracked_issue_action_does_not_dispatch() -> None:
    payload: dict[str, Any] = {
        "action": "labeled",
        "installation": {"id": 42},
        "issue": {
            "id": 555,
            "number": 7,
            "state_reason": None,
            "updated_at": "2026-09-20T21:00:00Z",
        },
        "repository": {"id": 999, "full_name": "acme/widgets"},
    }
    with patch("feedback.tasks.apply_issue_webhook") as apply_issue:
        process_github_delivery(event_name="issues", payload=payload)

    apply_issue.assert_not_called()


def test_installation_event_dispatches_to_apply_installation_webhook() -> None:
    payload: dict[str, Any] = {"action": "suspend", "installation": {"id": 42}}
    with patch("feedback.tasks.apply_installation_webhook") as apply_installation:
        process_github_delivery(event_name="installation", payload=payload)

    apply_installation.assert_called_once_with(
        installation_id="42",
        event=InstallationEvent(
            event="installation", action="suspend", repositories_removed=(), access_lost=True
        ),
    )


def test_missing_installation_id_does_not_dispatch() -> None:
    payload: dict[str, Any] = {"action": "closed", "issue": {"number": 7}}
    with (
        patch("feedback.tasks.apply_issue_webhook") as apply_issue,
        patch("feedback.tasks.apply_installation_webhook") as apply_installation,
    ):
        process_github_delivery(event_name="issues", payload=payload)

    apply_issue.assert_not_called()
    apply_installation.assert_not_called()


def test_ping_event_is_ignored() -> None:
    payload: dict[str, Any] = {"zen": "Keep it logically awesome.", "installation": {"id": 42}}
    with (
        patch("feedback.tasks.apply_issue_webhook") as apply_issue,
        patch("feedback.tasks.apply_installation_webhook") as apply_installation,
    ):
        process_github_delivery(event_name="ping", payload=payload)

    apply_issue.assert_not_called()
    apply_installation.assert_not_called()
