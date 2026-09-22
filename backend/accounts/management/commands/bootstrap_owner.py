"""Create the first workspace owner without accepting passwords in argv."""

import getpass
import os
from argparse import ArgumentParser
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Workspace
from accounts.services import bootstrap_owner


class Command(BaseCommand):
    requires_migrations_checks = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", required=True)
        parser.add_argument("--workspace-name", required=True)
        parser.add_argument("--workspace-slug", required=True)
        parser.add_argument("--add-owner", action="store_true")
        parser.add_argument("--non-interactive", action="store_true")

    def handle(self, *args: object, **options: Any) -> None:
        slug = str(options["workspace_slug"])
        workspace = Workspace.objects.filter(slug=slug).first()
        if workspace and not options["add_owner"]:
            raise CommandError("Workspace slug already exists; pass --add-owner to add an owner.")
        email = str(options["email"]).lower()
        existing_user = get_user_model().objects.filter(email=email).exists()
        password: str | None = None
        if not existing_user:
            if options["non_interactive"]:
                password = os.environ.get("RESCRIBO_BOOTSTRAP_PASSWORD", "")
                if not password:
                    raise CommandError("RESCRIBO_BOOTSTRAP_PASSWORD is required.")
            else:
                password = getpass.getpass("Password: ")
                if password != getpass.getpass("Password again: "):
                    raise CommandError("Passwords do not match.")
        try:
            workspace, _, _ = bootstrap_owner(
                email=email,
                full_name=str(options["full_name"]),
                password=password,
                workspace_name=str(options["workspace_name"]),
                workspace_slug=slug,
                add_owner=bool(options["add_owner"]),
            )
        except ValueError as error:
            messages = {
                "workspace_exists": (
                    "Workspace slug already exists; pass --add-owner to add an owner."
                ),
                "password_required": "A password is required for a new owner.",
            }
            raise CommandError(messages.get(str(error), str(error))) from error
        except ValidationError as error:
            raise CommandError("Password rejected: " + "; ".join(error.messages)) from error
        self.stdout.write(f"Owner ready for workspace {workspace.slug}.")
