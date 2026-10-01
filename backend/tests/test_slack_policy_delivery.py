"""Channel policy and the follow-up delivery boundary that #14 builds on."""

from types import SimpleNamespace

import pytest

from integrations.slack import (
    ChannelRejected,
    DeliveryRejected,
    SlackConnectionGuard,
    send_delayed_dm,
    validate_channel,
)


def channel(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": "C0SOURCE",
        "is_private": False,
        "is_archived": False,
        "is_member": True,
        "is_shared": False,
        "is_ext_shared": False,
        "is_im": False,
        "is_mpim": False,
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("is_im", "direct_message"),
        ("is_mpim", "group_direct_message"),
        ("is_ext_shared", "externally_shared"),
        ("is_archived", "archived"),
        ("is_member", "bot_not_member"),
    ],
)
def test_channel_policy_fails_closed(field: str, reason: str) -> None:
    value: object = False if field == "is_member" else True
    with pytest.raises(ChannelRejected) as error:
        validate_channel(channel(**{field: value}))
    assert error.value.reason == reason


def test_channel_policy_accepts_internal_public_and_private_channels() -> None:
    assert validate_channel(channel()).channel_id == "C0SOURCE"
    assert validate_channel(channel(id="G0PRIVATE", is_private=True)).is_private is True
    assert validate_channel(channel(is_shared=True)).channel_id == "C0SOURCE"


class DeliveryClient:
    def __init__(self, *, post_error: Exception | None = None) -> None:
        self.calls: list[tuple[str, str, str]] = []
        self.post_error = post_error

    def conversations_open(self, *, users: str) -> dict[str, object]:
        self.calls.append(("open", users, ""))
        return {"channel": {"id": "D0ACTOR"}}

    def chat_postMessage(self, *, channel: str, text: str) -> dict[str, object]:
        self.calls.append(("post", channel, text))
        if self.post_error is not None:
            raise self.post_error
        return {"ts": "1758400300.000200"}


def test_delayed_dm_opens_and_posts_directly() -> None:
    client = DeliveryClient()
    guard = SlackConnectionGuard(team_id="T0TEAM")
    result = send_delayed_dm(
        client,
        guard,
        send_id="send-1",
        actor_id="U0ACTOR",
        text="The fix is available.",
        member_is_active=lambda: True,
    )
    assert result.conversation_id == "D0ACTOR"
    assert client.calls == [
        ("open", "U0ACTOR", ""),
        ("post", "D0ACTOR", "The fix is available."),
    ]
    assert guard.pending_send_ids == set()


def test_member_revocation_is_checked_before_each_external_write() -> None:
    client = DeliveryClient()
    guard = SlackConnectionGuard(team_id="T0TEAM")
    active = iter([True, False])
    with pytest.raises(DeliveryRejected):
        send_delayed_dm(
            client,
            guard,
            send_id="send-1",
            actor_id="U0ACTOR",
            text="Do not send.",
            member_is_active=lambda: next(active),
        )
    assert [call[0] for call in client.calls] == ["open"]


def test_revoked_connection_stops_follow_up_actions() -> None:
    response = SimpleNamespace(data={"error": "token_revoked"})
    error = RuntimeError("revoked")
    error.response = response  # type: ignore[attr-defined]
    client = DeliveryClient(post_error=error)
    guard = SlackConnectionGuard(team_id="T0TEAM")
    with pytest.raises(RuntimeError):
        send_delayed_dm(
            client,
            guard,
            send_id="send-1",
            actor_id="U0ACTOR",
            text="May fail.",
            member_is_active=lambda: True,
        )
    assert guard.active is False
    with pytest.raises(DeliveryRejected):
        send_delayed_dm(
            client,
            guard,
            send_id="send-2",
            actor_id="U0ACTOR",
            text="Must not send.",
            member_is_active=lambda: True,
        )
