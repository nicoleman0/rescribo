"""Reset the reserved browser-test workspace and emit synthetic credentials."""

import json
import os
from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Invitation, Membership, PasswordReset, Workspace
from accounts.tokens import issue_token


class Command(BaseCommand):
    requires_migrations_checks = True

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--json", action="store_true")

    @transaction.atomic
    def handle(self, *args: object, **options: Any) -> None:
        slug = "e2e-test"
        workspace, _ = Workspace.objects.get_or_create(slug=slug, defaults={"name": "E2E Test"})
        Invitation.objects.filter(workspace=workspace).delete()
        PasswordReset.objects.filter(workspace=workspace).delete()
        Membership.objects.filter(workspace=workspace).delete()
        emails = [
            "owner-1@example.test",
            "owner-2@example.test",
            "owner-3@example.test",
            "owner-4@example.test",
            "owner-5@example.test",
            "owner-reset@example.test",
            "member@example.test",
        ]
        password = os.environ.get("RESCRIBO_E2E_PASSWORD", "Rescribo-e2e-test-2026!")
        users = []
        roles = [Membership.Role.OWNER] * 6 + [Membership.Role.MEMBER]
        for email, role in zip(emails, roles, strict=True):
            user, _ = get_user_model().objects.get_or_create(
                email=email, defaults={"full_name": role.title()}
            )
            user.set_password(password)
            user.is_active = True
            user.save(update_fields=["password", "is_active"])
            Membership.objects.create(workspace=workspace, user=user, role=role)
            users.append({"email": email, "password": password})
        owner = Membership.objects.filter(
            workspace=workspace, role=Membership.Role.OWNER, is_active=True
        ).first()
        if owner is None:
            raise CommandError("The E2E workspace must have an active owner.")
        expired = issue_token(now=timezone.now(), lifetime=timedelta(seconds=-1))
        Invitation.objects.create(
            workspace=workspace,
            email="expired@example.test",
            role=Membership.Role.MEMBER,
            token_digest=expired.digest,
            created_by_membership=owner,
            expires_at=expired.expires_at,
        )
        result = {
            "workspace_id": str(workspace.pk),
            "users": users,
            "expired_invitation_token": expired.secret,
        }
        self.stdout.write(json.dumps(result) if options["json"] else "E2E test accounts seeded.")
