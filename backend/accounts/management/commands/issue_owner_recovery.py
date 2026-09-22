"""Issue a one-use operator reset link or set a new owner password."""

import getpass
from argparse import ArgumentParser
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Membership
from accounts.services import create_password_reset, operator_set_owner_password
from accounts.tokens import TokenError


class Command(BaseCommand):
    requires_migrations_checks = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--set-password", action="store_true")

    def handle(self, *args: object, **options: Any) -> None:
        user = get_user_model().objects.filter(email=str(options["email"]).lower()).first()
        membership = Membership.objects.filter(
            user=user, is_active=True, role=Membership.Role.OWNER
        ).first()
        if user is None or membership is None:
            raise CommandError("No active workspace owner matches that email.")
        if options["set_password"]:
            password = getpass.getpass("New password: ")
            if password != getpass.getpass("New password again: "):
                raise CommandError("Passwords do not match.")
            try:
                operator_set_owner_password(actor=membership, password=password)
            except TokenError as error:
                raise CommandError("Password rejected: " + "; ".join(error.messages)) from error
            self.stdout.write("Owner password updated.")
            return
        _, secret = create_password_reset(
            actor=membership, target=membership, issued_by_operator=True, now=timezone.now()
        )
        from django.conf import settings

        self.stdout.write(f"{settings.RESCRIBO_PUBLIC_BASE_URL}/reset-password/{secret}")
