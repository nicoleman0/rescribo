"""The restore check reads a report through the API; it runs here against the test database."""

from io import StringIO
from unittest.mock import patch

import pytest
from builders import make_membership, make_report
from django.core.management import CommandError, call_command
from django.http import HttpResponse

pytestmark = pytest.mark.django_db


def test_restore_check_reads_a_report_as_its_owner() -> None:
    owner = make_membership(role="owner")
    report = make_report(actor=owner)
    out = StringIO()

    call_command("check_restore", stdout=out)

    assert str(report.pk) in out.getvalue()


def test_restore_check_fails_without_a_report() -> None:
    make_membership(role="owner")

    with pytest.raises(CommandError, match="no report"):
        call_command("check_restore")


def test_restore_check_fails_when_the_api_does_not_serve_the_report() -> None:
    owner = make_membership(role="owner")
    make_report(actor=owner)

    with (
        patch("django.test.Client.get", return_value=HttpResponse(status=500)),
        pytest.raises(CommandError, match="HTTP 500"),
    ):
        call_command("check_restore")
