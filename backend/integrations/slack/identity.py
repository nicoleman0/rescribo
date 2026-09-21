"""Short-lived Slack identity linking bound to the signed actor and team."""

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Final


class LinkCodeRejected(ValueError):
    """Raised when a linking code is unknown, expired, used, or mis-bound."""


@dataclass(frozen=True)
class SlackIdentity:
    product_membership_id: str
    team_id: str
    actor_id: str


@dataclass
class _PendingCode:
    product_membership_id: str
    workspace_id: str
    expires_at: float
    used: bool = False


class LinkCodeStore:
    """In-memory harness for the one-use code contract.

    The product implementation should put the digest and expiry in its
    database or cache. The raw code remains in the logged-in product session.
    """

    def __init__(self, *, lifetime_seconds: int = 300, clock: Callable[[], float] = time) -> None:
        self._lifetime_seconds = lifetime_seconds
        self._clock = clock
        self._codes: dict[str, _PendingCode] = {}

    @staticmethod
    def _digest(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def create(self, *, product_membership_id: str, workspace_id: str) -> str:
        code = secrets.token_urlsafe(24)
        self._codes[self._digest(code)] = _PendingCode(
            product_membership_id=product_membership_id,
            workspace_id=workspace_id,
            expires_at=self._clock() + self._lifetime_seconds,
        )
        return code

    def redeem(
        self,
        code: str,
        *,
        workspace_id: str,
        team_id: str,
        actor_id: str,
    ) -> SlackIdentity:
        pending = self._codes.get(self._digest(code))
        if pending is None or pending.used or pending.expires_at <= self._clock():
            raise LinkCodeRejected("linking code is invalid or expired")
        if not hmac.compare_digest(pending.workspace_id, workspace_id):
            raise LinkCodeRejected("linking code is bound to another product workspace")
        if not team_id or not actor_id:
            raise LinkCodeRejected("Slack team and actor are required")
        pending.used = True
        return SlackIdentity(
            product_membership_id=pending.product_membership_id,
            team_id=team_id,
            actor_id=actor_id,
        )


def require_linked_actor(
    identity: SlackIdentity,
    *,
    team_id: str,
    actor_id: str,
    membership_active: bool,
) -> None:
    """Require an exact verified mapping before accepting a capture/action."""
    if not membership_active:
        raise LinkCodeRejected("product membership is inactive")
    if not hmac.compare_digest(identity.team_id, team_id):
        raise LinkCodeRejected("Slack workspace does not match the linked identity")
    if not hmac.compare_digest(identity.actor_id, actor_id):
        raise LinkCodeRejected("Slack actor does not match the linked identity")


def redeem_for_shortcut(
    store: LinkCodeStore,
    code: str,
    *,
    workspace_id: str,
    team_id: str,
    actor_id: str,
) -> SlackIdentity:
    """Redeem a modal code against the signed shortcut identity."""
    return store.redeem(
        code,
        workspace_id=workspace_id,
        team_id=team_id,
        actor_id=actor_id,
    )


__all__: Final = [
    "LinkCodeRejected",
    "LinkCodeStore",
    "SlackIdentity",
    "redeem_for_shortcut",
    "require_linked_actor",
]
