"""Create or reset the fictitious demo workspace and print the visitor sign-in."""

import json
from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from feedback.demo import DemoSeedError, seed_demo


class Command(BaseCommand):
    requires_migrations_checks = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    def handle(self, *args: object, **options: Any) -> None:
        try:
            result = seed_demo(visitor_password=settings.RESCRIBO_DEMO_PASSWORD or None)
        except DemoSeedError as error:
            raise CommandError(str(error)) from error
        if options["json"]:
            self.stdout.write(
                json.dumps(
                    {
                        "workspace_id": result.workspace_id,
                        "email": result.visitor_email,
                        "password": result.visitor_password,
                    }
                )
            )
            return
        password = result.visitor_password or "(unchanged)"
        self.stdout.write(f"Demo visitor: {result.visitor_email} / {password}")
