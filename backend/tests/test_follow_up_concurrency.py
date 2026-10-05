"""Competing follow-up writes and issue reopenings on separate PostgreSQL connections.

Each test holds one writer inside its transaction until the other writer is provably queued on
a row lock, so the interleaving is fixed and the outcome does not depend on timing.
"""

from typing import Any
from unittest.mock import patch

import pytest
from concurrency import race
from issue_world import World, github_reads

from connections.models import Connection, ExternalIdentity
from feedback.engineering_issues import apply_issue_webhook
from feedback.errors import InvalidTransition, NotFound, VersionConflict
from feedback.follow_ups import (
    approve_notification,
    current_notification,
    draft_notification,
    edit_notification,
)
from feedback.models import FollowUp, Problem, ReportNotificationOperation

pytestmark = pytest.mark.django_db(transaction=True)

TEAM = "T0RACE"


class Drafted:
    """A fixed problem with one linked report and a drafted follow-up the actor can send."""

    def __init__(self) -> None:
        self.world = World()
        self.actor = self.world.actor
        Connection.objects.create(
            workspace=self.actor.workspace,
            provider="slack",
            external_id=TEAM,
            identity="Acme Slack",
            status="active",
            credential="encrypted",
        )
        ExternalIdentity.objects.create(
            workspace=self.actor.workspace,
            membership=self.actor,
            provider="slack",
            provider_team_id=TEAM,
            provider_user_id="U0RACE",
        )
        self.follow_up = FollowUp.objects.get(report=self.world.report)
        self.draft = draft_notification(actor=self.actor, follow_up_id=self.follow_up.pk)

    def edit(self, message: str, draft_version: int = 1) -> ReportNotificationOperation:
        return edit_notification(
            actor=self.actor,
            follow_up_id=self.follow_up.pk,
            notification_id=self.draft.pk,
            message=message,
            draft_version=draft_version,
        )

    def approve(self, draft_version: int = 1) -> ReportNotificationOperation:
        return approve_notification(
            actor=self.actor,
            follow_up_id=self.follow_up.pk,
            notification_id=self.draft.pk,
            draft_version=draft_version,
        )

    def row(self) -> ReportNotificationOperation:
        return ReportNotificationOperation.objects.get(pk=self.draft.pk)


@pytest.fixture(autouse=True)
def no_broker() -> Any:
    with patch("feedback.follow_ups.dispatch_task"):
        yield


def test_concurrent_draft_edits_admit_one_and_the_loser_sees_the_winner() -> None:
    drafted = Drafted()

    outcomes = race(lambda: drafted.edit("Winner"), lambda: drafted.edit("Loser"))

    assert outcomes["holder"].message == "Winner"
    conflict = outcomes["challenger"]
    assert isinstance(conflict, VersionConflict)
    assert conflict.current.message == "Winner"
    assert conflict.current.draft_version == 2
    row = drafted.row()
    assert (row.message, row.draft_version) == ("Winner", 2)


def test_edit_racing_an_approval_cannot_change_what_was_approved() -> None:
    drafted = Drafted()
    approved_message = drafted.draft.message

    outcomes = race(drafted.approve, lambda: drafted.edit("Sneaked in after approval"))

    assert outcomes["holder"].state == "queued"
    assert isinstance(outcomes["challenger"], InvalidTransition)
    row = drafted.row()
    assert (row.state, row.message, row.draft_version) == ("queued", approved_message, 1)


def test_approval_racing_an_edit_is_rejected_as_stale() -> None:
    drafted = Drafted()

    outcomes = race(lambda: drafted.edit("Reworded"), drafted.approve)

    conflict = outcomes["challenger"]
    assert isinstance(conflict, VersionConflict)
    assert conflict.current.message == "Reworded" and conflict.current.draft_version == 2
    assert drafted.row().state == "draft"


def reopen_on_github(drafted: Drafted) -> None:
    world = drafted.world
    with github_reads(world.github_says(state="open", seconds=30)):
        apply_issue_webhook(
            installation_id=world.connection.external_id,
            event=world.event(action="reopened", seconds=30),
        )


def test_reopen_after_an_approval_cancels_the_unsent_send() -> None:
    drafted = Drafted()

    outcomes = race(drafted.approve, lambda: reopen_on_github(drafted))

    assert outcomes["holder"].state == "queued"
    assert outcomes["challenger"] is None
    row = drafted.row()
    assert (row.state, row.invalidation_reason) == ("cancelled", "issue_reopened")
    assert Problem.objects.get(pk=drafted.world.problem.pk).state == Problem.State.IN_PROGRESS


def test_approval_after_a_reopen_is_refused() -> None:
    drafted = Drafted()

    outcomes = race(lambda: reopen_on_github(drafted), drafted.approve)

    assert isinstance(outcomes["challenger"], NotFound)
    row = drafted.row()
    assert row.state == "cancelled" and row.invalidation_reason == "issue_reopened"
    assert current_notification(drafted.follow_up) is None
    assert outcomes["holder"] is None
