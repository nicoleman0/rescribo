"""Channel eligibility policy fails closed when a source is not capturable."""

import pytest

from integrations.slack import ChannelRejected, validate_channel


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
