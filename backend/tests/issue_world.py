"""Shared setup for tests that replay GitHub issue deliveries against a fixed problem."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

from builders import (
    make_connection,
    make_engineering_issue,
    make_membership,
    make_problem,
    make_report,
)

from feedback.models import Problem, Report
from feedback.problems import confirm_fix
from feedback.reports import link_report
from integrations.github_app.webhooks import IssueEvent
from operations.models import InboundReceipt
from operations.tasks import process_inbound_receipt

INSTALLATION_ID = "42"
REPOSITORY_ID = "999"


class World:
    """One linked report on a fixed problem whose GitHub issue is open."""

    def __init__(self) -> None:
        self.issue_id = str(uuid4().int)[:12]
        self.actor = make_membership()
        self.connection = make_connection(
            workspace=self.actor.workspace, external_id=INSTALLATION_ID
        )
        self.problem = make_problem(actor=self.actor)
        report = make_report(actor=self.actor)
        self.report = link_report(
            actor=self.actor,
            report_id=report.pk,
            expected_version=report.version,
            problem_id=self.problem.pk,
        )
        confirm_fix(
            actor=self.actor,
            problem_id=self.problem.pk,
            expected_version=Problem.objects.get(pk=self.problem.pk).version,
            fix_note="Shipped",
            fix_version="1.0.0",
        )
        self.report = Report.objects.select_related("problem").get(pk=self.report.pk)
        self.confirmed_at = Problem.objects.get(pk=self.problem.pk).fix_confirmed_at
        assert self.confirmed_at is not None
        self.issue = make_engineering_issue(
            problem=self.problem,
            connection=self.connection,
            created_by=self.actor,
            issue_id=self.issue_id,
            provider_updated_at=self.confirmed_at - timedelta(minutes=1),
        )

    def at(self, seconds: int) -> datetime:
        assert self.confirmed_at is not None
        return self.confirmed_at + timedelta(seconds=seconds)

    def event(self, *, action: str, seconds: int) -> IssueEvent:
        return IssueEvent(
            action=action,
            number=7,
            repository="acme/widgets",
            state_reason=None,
            updated_at=self.at(seconds).isoformat(),
            repository_id=REPOSITORY_ID,
            issue_id=self.issue_id,
        )

    def receipt(self, *, action: str, seconds: int) -> InboundReceipt:
        event = self.event(action=action, seconds=seconds)
        return InboundReceipt.objects.create(
            provider="github",
            delivery_id=f"d-{uuid4().hex}",
            event="issues",
            installation_id=INSTALLATION_ID,
            normalized=event.as_dict(),
        )

    def github_says(self, *, state: str, seconds: int) -> dict[str, Any]:
        return {
            "id": int(self.issue_id),
            "number": 7,
            "title": "Export button does nothing",
            "state": state,
            "state_reason": "completed" if state == "closed" else None,
            "html_url": "https://github.com/acme/widgets/issues/7",
            "repository_url": "https://api.github.com/repos/acme/widgets",
            "updated_at": self.at(seconds).isoformat(),
        }


@contextmanager
def github_reads(payload: dict[str, Any]) -> Iterator[MagicMock]:
    """Mock only the provider read; the sync and apply logic stays real."""
    client = MagicMock()
    client.create_installation_token.return_value = ("installation-token", "expires")
    client.get_repository_by_id.return_value = {
        "id": int(REPOSITORY_ID),
        "full_name": "acme/widgets",
    }
    client.get_issue.return_value = payload
    with patch("feedback.engineering_issues.github_client") as factory:
        factory.return_value.__enter__.return_value = client
        yield client


def deliver(receipt: InboundReceipt) -> None:
    process_inbound_receipt(str(receipt.pk))
    receipt.refresh_from_db()
    assert receipt.status == InboundReceipt.Status.SUCCEEDED
