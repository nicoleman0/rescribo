"""Transactional account use cases shared by HTTP handlers and workers."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import Invitation, Membership, PasswordReset, User, Workspace
from accounts.tokens import (
    INVITATION_LIFETIME,
    PASSWORD_RESET_LIFETIME,
    TokenError,
    check_token,
    digest,
    issue_token,
)


@dataclass(frozen=True)
class MembershipView:
    membership_id: str
    role: str
    workspace_id: str
    workspace_name: str
    workspace_slug: str


@dataclass(frozen=True)
class SessionView:
    user_id: str
    email: str
    full_name: str
    memberships: tuple[MembershipView, ...]


class LastActiveOwner(Exception):
    reason = "last_active_owner"


def bootstrap_owner(
    *,
    email: str,
    full_name: str,
    password: str | None,
    workspace_name: str,
    workspace_slug: str,
    add_owner: bool = False,
    now: datetime | None = None,
) -> tuple[Workspace, User, Membership]:
    current = now or timezone.now()
    with transaction.atomic():
        workspace = Workspace.objects.filter(slug=workspace_slug).first()
        if workspace is not None and not add_owner:
            raise ValueError("workspace_exists")
        if workspace is None:
            workspace = Workspace.objects.create(
                name=workspace_name, slug=workspace_slug, created_at=current
            )
        user_model = get_user_model()
        user = user_model.objects.filter(email=email.strip().lower()).first()
        if user is None:
            if password is None:
                raise ValueError("password_required")
            validate_password(password, user_model(email=email, full_name=full_name))
            user = user_model.objects.create_user(
                email=email, full_name=full_name, password=password, date_joined=current
            )
        membership, _ = Membership.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={"role": Membership.Role.OWNER, "created_at": current},
        )
        if not membership.is_active or membership.role != Membership.Role.OWNER:
            membership.is_active = True
            membership.revoked_at = None
            membership.role = Membership.Role.OWNER
            membership.save(update_fields=["is_active", "revoked_at", "role"])
        return workspace, user, membership


def describe_session(*, user: User) -> SessionView:
    memberships = tuple(
        MembershipView(
            str(item.pk),
            item.role,
            str(item.workspace_id),
            item.workspace.name,
            item.workspace.slug,
        )
        for item in Membership.objects.filter(user=user, is_active=True).select_related("workspace")
    )
    return SessionView(str(user.pk), user.email, user.full_name, memberships)


def resolve_active_membership(*, user: User, workspace_id: UUID | str) -> Membership:
    try:
        return Membership.objects.select_related("workspace", "user").get(
            user=user, workspace_id=workspace_id, is_active=True
        )
    except Membership.DoesNotExist as error:
        raise LookupError("workspace_not_found") from error


def require_remaining_active_owner(*, actor: Membership, target: Membership) -> None:
    with transaction.atomic():
        # A workspace lock gives every owner change the same lock order.
        Workspace.objects.select_for_update().get(pk=actor.workspace_id)
        locked_target = Membership.objects.select_for_update().get(pk=target.pk)
        is_last_owner = (
            locked_target.role == Membership.Role.OWNER
            and locked_target.is_active
            and not Membership.objects.filter(
                workspace_id=actor.workspace_id,
                role=Membership.Role.OWNER,
                is_active=True,
            )
            .exclude(pk=locked_target.pk)
            .exists()
        )
        if is_last_owner:
            raise LastActiveOwner


def revoke_all_sessions(*, user: User) -> None:
    type(user).objects.filter(pk=user.pk).update(session_generation=F("session_generation") + 1)


def operator_set_owner_password(*, actor: Membership, password: str) -> None:
    user = actor.user
    try:
        validate_password(password, user)
    except ValidationError as error:
        rejected = TokenError("password_rejected")
        rejected.messages = error.messages
        raise rejected from error
    with transaction.atomic():
        PasswordReset.objects.filter(
            user=user, used_at__isnull=True, revoked_at__isnull=True
        ).update(revoked_at=timezone.now())
        user.set_password(password)
        user.session_generation += 1
        user.save(update_fields=["password", "session_generation"])


def create_invitation(
    *, actor: Membership, email: str, role: str, now: datetime | None = None
) -> tuple[Invitation, str]:
    current = now or timezone.now()
    if role != Membership.Role.MEMBER:
        raise ValueError("Only member invitations are available.")
    issued = issue_token(now=current, lifetime=INVITATION_LIFETIME)
    with transaction.atomic():
        Invitation.objects.filter(
            workspace_id=actor.workspace_id,
            email=email.lower(),
            used_at__isnull=True,
            revoked_at__isnull=True,
        ).update(revoked_at=current)
        invitation = Invitation.objects.create(
            workspace_id=actor.workspace_id,
            email=email.lower(),
            role=role,
            token_digest=issued.digest,
            created_by_membership=actor,
            expires_at=issued.expires_at,
        )
    return invitation, issued.secret


def preview_invitation(*, secret: str, now: datetime | None = None) -> dict[str, str]:
    current = now or timezone.now()
    invitation = (
        Invitation.objects.filter(token_digest=digest(secret)).select_related("workspace").first()
    )
    if invitation is None:
        return {"status": "unknown"}
    try:
        check_token(
            secret=secret,
            digest=invitation.token_digest,
            expires_at=invitation.expires_at,
            used=bool(invitation.used_at or invitation.revoked_at),
            now=current,
        )
    except TokenError as error:
        return {"status": "expired" if error.reason == "invitation_expired" else "unknown"}
    exists = get_user_model().objects.filter(email=invitation.email).exists()
    return {
        "status": "requires_sign_in" if exists else "valid",
        "workspace_name": invitation.workspace.name,
    }


def accept_invitation(
    *,
    secret: str,
    full_name: str,
    password: str,
    authenticated_user: User | None = None,
    now: datetime | None = None,
) -> User:
    current = now or timezone.now()
    with transaction.atomic():
        invitation = (
            Invitation.objects.select_for_update().filter(token_digest=digest(secret)).first()
        )
        if invitation is None:
            raise TokenError("invalid_token")
        check_token(
            secret=secret,
            digest=invitation.token_digest,
            expires_at=invitation.expires_at,
            used=bool(invitation.used_at or invitation.revoked_at),
            now=current,
        )
        user_model = get_user_model()
        user = user_model.objects.filter(email=invitation.email).first()
        if user is not None:
            if authenticated_user is None or authenticated_user.pk != user.pk:
                raise TokenError("sign_in_required")
        else:
            try:
                validate_password(password, user_model(email=invitation.email, full_name=full_name))
            except ValidationError as error:
                rejected = TokenError("password_rejected")
                rejected.messages = error.messages
                raise rejected from error
            user = user_model.objects.create_user(
                email=invitation.email, full_name=full_name, password=password
            )
        membership, created = Membership.objects.get_or_create(
            workspace_id=invitation.workspace_id,
            user=user,
            defaults={
                "role": invitation.role,
                "invited_by_membership": invitation.created_by_membership,
            },
        )
        if not created and not membership.is_active:
            membership.is_active = True
            membership.revoked_at = None
            membership.role = invitation.role
            membership.save(update_fields=["is_active", "revoked_at", "role"])
        invitation.used_at = current
        invitation.save(update_fields=["used_at"])
        return user


def revoke_membership(
    *, actor: Membership, target: Membership, now: datetime | None = None
) -> None:
    if target.workspace_id != actor.workspace_id:
        raise LookupError("membership_not_found")
    current = now or timezone.now()
    with transaction.atomic():
        require_remaining_active_owner(actor=actor, target=target)
        target = Membership.objects.select_for_update().get(pk=target.pk)
        if not target.is_active:
            return
        target.is_active = False
        target.revoked_at = current
        target.save(update_fields=["is_active", "revoked_at"])
        if not Membership.objects.filter(user=target.user, is_active=True).exists():
            revoke_all_sessions(user=target.user)


def revoke_invitation(*, workspace_id: UUID | str, invitation_id: UUID | str) -> None:
    count = Invitation.objects.filter(
        pk=invitation_id, workspace_id=workspace_id, used_at__isnull=True, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    if not count:
        raise LookupError("invitation_not_found")


def change_membership_role(*, actor: Membership, target: Membership, role: str) -> None:
    if target.workspace_id != actor.workspace_id:
        raise LookupError("membership_not_found")
    if role not in Membership.Role.values:
        raise ValueError("Unknown membership role.")
    with transaction.atomic():
        require_remaining_active_owner(actor=actor, target=target)
        target = Membership.objects.select_for_update().get(pk=target.pk)
        target.role = role
        target.save(update_fields=["role"])


def create_password_reset(
    *,
    actor: Membership,
    target: Membership,
    now: datetime | None = None,
    issued_by_operator: bool = False,
) -> tuple[PasswordReset, str]:
    current = now or timezone.now()
    issued = issue_token(now=current, lifetime=PASSWORD_RESET_LIFETIME)
    if target.workspace_id != actor.workspace_id:
        raise LookupError("membership_not_found")
    if not issued_by_operator:
        if not owner_may_reset_membership(target=target):
            raise LookupError("membership_not_found")
    with transaction.atomic():
        PasswordReset.objects.filter(
            user=target.user, used_at__isnull=True, revoked_at__isnull=True
        ).update(revoked_at=current)
        reset = PasswordReset.objects.create(
            user=target.user,
            workspace_id=actor.workspace_id,
            issued_by_membership=None if issued_by_operator else actor,
            issued_by_operator=issued_by_operator,
            token_digest=issued.digest,
            expires_at=issued.expires_at,
        )
    return reset, issued.secret


def owner_may_reset_membership(*, target: Membership) -> bool:
    return (
        target.is_active
        and target.user.is_active
        and target.role == Membership.Role.MEMBER
        and Membership.objects.filter(user=target.user, is_active=True).count() == 1
    )


def preview_password_reset(*, secret: str, now: datetime | None = None) -> dict[str, str]:
    reset = PasswordReset.objects.filter(token_digest=digest(secret)).first()
    if reset is None:
        return {"status": "unknown"}
    try:
        check_token(
            secret=secret,
            digest=reset.token_digest,
            expires_at=reset.expires_at,
            used=bool(reset.used_at or reset.revoked_at),
            now=now or timezone.now(),
        )
    except TokenError:
        return {"status": "expired"}
    return {"status": "valid"}


def redeem_password_reset(*, secret: str, password: str, now: datetime | None = None) -> User:
    current = now or timezone.now()
    with transaction.atomic():
        reset = (
            PasswordReset.objects.select_for_update()
            .filter(token_digest=digest(secret))
            .select_related("user")
            .first()
        )
        if reset is None:
            raise TokenError("invalid_token")
        check_token(
            secret=secret,
            digest=reset.token_digest,
            expires_at=reset.expires_at,
            used=bool(reset.used_at or reset.revoked_at),
            now=current,
        )
        if reset.issued_by_operator:
            eligible = (
                reset.user.is_active and reset.user.memberships.filter(is_active=True).exists()
            )
        else:
            membership = Membership.objects.filter(
                user=reset.user, workspace_id=reset.workspace_id, is_active=True
            ).first()
            eligible = membership is not None and owner_may_reset_membership(target=membership)
        if not eligible:
            raise TokenError("invalid_token")
        try:
            validate_password(password, reset.user)
        except ValidationError as error:
            rejected = TokenError("password_rejected")
            rejected.messages = error.messages
            raise rejected from error
        reset.user.set_password(password)
        reset.user.session_generation += 1
        reset.user.save(update_fields=["password", "session_generation"])
        PasswordReset.objects.filter(
            user=reset.user, used_at__isnull=True, revoked_at__isnull=True
        ).update(revoked_at=current)
        reset.used_at = current
        reset.save(update_fields=["used_at"])
        return reset.user
