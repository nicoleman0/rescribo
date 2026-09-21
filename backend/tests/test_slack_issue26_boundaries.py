from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from integrations.slack import (
    CapturedReport,
    ChannelEligibilityCache,
    ChannelRejected,
    DeliveryRejected,
    LinkCodeRejected,
    LinkCodeStore,
    SlackConnectionGuard,
    SlackIdentity,
    parse_app_uninstalled,
    require_linked_actor,
    resolve_report_permalink,
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


def test_channel_cache_is_used_only_for_modal_startup() -> None:
    clock = [100.0]
    calls: list[str] = []
    state: dict[str, object] = channel()

    def fetch(channel_id: str) -> Mapping[str, object]:
        calls.append(channel_id)
        return state

    cache = ChannelEligibilityCache(fetch, ttl_seconds=10, clock=lambda: clock[0])
    cache.validate_for_modal_start("C0SOURCE")
    cache.validate_for_modal_start("C0SOURCE")
    assert calls == ["C0SOURCE"]

    state["is_archived"] = True
    with pytest.raises(ChannelRejected) as error:
        cache.validate_for_submission("C0SOURCE")
    assert error.value.reason == "archived"
    assert calls == ["C0SOURCE", "C0SOURCE"]

    clock[0] = 111.0
    state["is_archived"] = False
    cache.validate_for_modal_start("C0SOURCE")
    assert calls == ["C0SOURCE", "C0SOURCE", "C0SOURCE"]


def test_linking_binds_code_to_workspace_and_signed_slack_identity() -> None:
    store = LinkCodeStore(lifetime_seconds=300, clock=lambda: 100.0)
    code = store.create(product_membership_id="member-1", workspace_id="workspace-1")
    identity = store.redeem(
        code,
        workspace_id="workspace-1",
        team_id="T0TEAM",
        actor_id="U0ACTOR",
    )
    assert identity == SlackIdentity("member-1", "T0TEAM", "U0ACTOR")
    require_linked_actor(
        identity,
        team_id="T0TEAM",
        actor_id="U0ACTOR",
        membership_active=True,
    )

    with pytest.raises(LinkCodeRejected):
        store.redeem(
            code,
            workspace_id="workspace-1",
            team_id="T0TEAM",
            actor_id="U0ACTOR",
        )
    with pytest.raises(LinkCodeRejected):
        require_linked_actor(
            identity,
            team_id="T0TEAM",
            actor_id="U0OTHER",
            membership_active=True,
        )


def test_linking_code_expires() -> None:
    clock = [100.0]
    store = LinkCodeStore(lifetime_seconds=5, clock=lambda: clock[0])
    code = store.create(product_membership_id="member-1", workspace_id="workspace-1")
    clock[0] = 105.0
    with pytest.raises(LinkCodeRejected):
        store.redeem(code, workspace_id="workspace-1", team_id="T0TEAM", actor_id="U0ACTOR")


class PermalinkClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def chat_getPermalink(self, *, channel: str, message_ts: str) -> dict[str, object]:
        self.calls.append((channel, message_ts))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response  # type: ignore[return-value]


def report() -> CapturedReport:
    return CapturedReport(
        report_id="report-1",
        team_id="T0TEAM",
        channel_id="C0SOURCE",
        actor_id="U0ACTOR",
        message_ts="1758400000.000100",
        title="Export failed",
    )


def test_permalink_failure_preserves_report_and_retry_succeeds() -> None:
    client = PermalinkClient(
        [RuntimeError("temporarily unavailable"), {"permalink": "https://slack.example/p/1"}]
    )
    failed = resolve_report_permalink(report(), client)
    assert failed.report_id == "report-1"
    assert failed.title == "Export failed"
    assert failed.permalink is None
    assert failed.permalink_error == "RuntimeError"

    retried = resolve_report_permalink(failed, client)
    assert retried.report_id == failed.report_id
    assert retried.permalink == "https://slack.example/p/1"
    assert retried.permalink_error is None


def test_permalink_error_records_the_reason_code() -> None:
    response = SimpleNamespace(data={"error": "channel_not_found"})
    rejected = RuntimeError("slack rejected the call")
    rejected.response = response  # type: ignore[attr-defined]
    client = PermalinkClient([rejected, {"permalink": ""}])
    assert resolve_report_permalink(report(), client).permalink_error == "channel_not_found"
    assert resolve_report_permalink(report(), client).permalink_error == "missing_permalink"


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


def test_app_uninstalled_event_disables_connection_and_cancels_pending_sends() -> None:
    event = parse_app_uninstalled(
        {
            "type": "event_callback",
            "team_id": "T0TEAM",
            "api_app_id": "A0APP",
            "event": {"type": "app_uninstalled"},
        }
    )
    guard = SlackConnectionGuard(team_id=event.team_id)
    assert guard.disable_for_uninstall("T0OTHER") is False
    assert guard.active is True
    guard.begin_send("send-1")
    assert guard.disable_for_uninstall(event.team_id) is True
    assert guard.active is False
    assert guard.pending_send_ids == set()
    with pytest.raises(DeliveryRejected):
        guard.require_active()
