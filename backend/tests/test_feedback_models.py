import pytest
from builders import make_membership, make_problem, make_report, make_user, make_workspace
from django.db import IntegrityError, transaction

from accounts.models import Membership
from feedback.models import Activity, Problem, Report, ReportSource

pytestmark = pytest.mark.django_db


def raw_report(actor: Membership) -> Report:
    return Report.objects.create(workspace=actor.workspace, submitted_by=actor, title="Raw")


def test_report_problem_link_constraint() -> None:
    actor = make_membership()
    problem = make_problem(actor=actor)
    report = make_report(actor=actor)
    with pytest.raises(IntegrityError), transaction.atomic():
        Report.objects.filter(pk=report.pk).update(triage_state="linked")
    with pytest.raises(IntegrityError), transaction.atomic():
        Report.objects.filter(pk=report.pk).update(problem=problem)


def test_source_uniqueness_is_workspace_scoped() -> None:
    actor = make_membership()
    source = ReportSource.objects.create(
        report=raw_report(actor),
        workspace=actor.workspace,
        kind="slack",
        external_workspace_id="T1",
        external_channel_id="C1",
        external_message_id="1.2",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        ReportSource.objects.create(
            report=raw_report(actor),
            workspace=actor.workspace,
            kind="slack",
            external_workspace_id=source.external_workspace_id,
            external_channel_id=source.external_channel_id,
            external_message_id=source.external_message_id,
        )
    other = make_membership(
        user=make_user(email="other@example.test"),
        workspace=make_workspace(slug="other", name="Other"),
    )
    ReportSource.objects.create(
        report=raw_report(other),
        workspace=other.workspace,
        kind="slack",
        external_workspace_id="T1",
        external_channel_id="C1",
        external_message_id="1.2",
    )


def test_manual_sources_and_problem_constraints() -> None:
    actor = make_membership()
    make_report(actor=actor)
    make_report(actor=actor)
    problem = make_problem(actor=actor)
    with pytest.raises(IntegrityError), transaction.atomic():
        Problem.objects.filter(pk=problem.pk).update(state="not_planned")
    with pytest.raises(IntegrityError), transaction.atomic():
        Activity.objects.create(
            workspace=actor.workspace,
            actor_membership=actor,
            actor_system="worker",
            action="report.created",
            record_type=Activity.RecordType.REPORT,
            record_id=problem.pk,
        )
    with pytest.raises(IntegrityError), transaction.atomic():
        Activity.objects.create(
            workspace=actor.workspace,
            action="report.created",
            record_type=Activity.RecordType.REPORT,
            record_id=problem.pk,
        )
