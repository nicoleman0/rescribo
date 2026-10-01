"""Slack account linking: one-use web codes redeemed by a signed Slack actor."""

from datetime import timedelta
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Membership
from accounts.tokens import IssuedToken, digest, issue_token
from connections.models import Connection, ExternalIdentity, SlackLinkCode

LINK_CODE_LIFETIME = timedelta(minutes=5)


class LinkCodeRejected(ValueError):
    """The code is unknown, expired, used, or bound to another workspace or member."""


def issue_link_code(actor: Membership) -> IssuedToken:
    issued = issue_token(now=timezone.now(), lifetime=LINK_CODE_LIFETIME)
    with transaction.atomic():
        SlackLinkCode.objects.filter(membership=actor, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        SlackLinkCode.objects.create(
            token_digest=issued.digest, membership=actor, expires_at=issued.expires_at
        )
    return issued


def redeem_link_code(code: str, *, workspace_id: UUID, team_id: str, user_id: str) -> Membership:
    """Bind the signed Slack actor to the member who issued the code."""
    if not team_id or not user_id:
        raise LinkCodeRejected("Slack team and user are required.")
    now = timezone.now()
    with transaction.atomic():
        pending = (
            SlackLinkCode.objects.select_for_update()
            .select_related("membership")
            .filter(
                token_digest=digest(code.strip()),
                membership__workspace_id=workspace_id,
                membership__is_active=True,
                used_at__isnull=True,
                expires_at__gt=now,
            )
            .first()
        )
        if pending is None:
            raise LinkCodeRejected("This linking code is invalid or expired.")
        pending.used_at = now
        pending.save(update_fields=["used_at"])
        membership = pending.membership
        ExternalIdentity.objects.filter(
            membership=membership, provider=Connection.Provider.SLACK
        ).delete()
        try:
            with transaction.atomic():
                ExternalIdentity.objects.create(
                    workspace_id=workspace_id,
                    membership=membership,
                    provider=Connection.Provider.SLACK,
                    provider_team_id=team_id,
                    provider_user_id=user_id,
                    linked_at=now,
                )
        except IntegrityError as error:
            raise LinkCodeRejected(
                "This Slack account is already linked to another member."
            ) from error
    return membership


def unlink(actor: Membership) -> None:
    ExternalIdentity.objects.filter(membership=actor, provider=Connection.Provider.SLACK).delete()


def linked_identity(actor: Membership) -> ExternalIdentity | None:
    return ExternalIdentity.objects.filter(
        membership=actor, provider=Connection.Provider.SLACK
    ).first()


def linked_membership(*, workspace_id: UUID, team_id: str, user_id: str) -> Membership | None:
    """The active member linked to this Slack actor, never matched by name or email."""
    identity = (
        ExternalIdentity.objects.select_related("membership")
        .filter(
            workspace_id=workspace_id,
            provider=Connection.Provider.SLACK,
            provider_team_id=team_id,
            provider_user_id=user_id,
            membership__workspace_id=workspace_id,
            membership__is_active=True,
        )
        .first()
    )
    return identity.membership if identity else None
