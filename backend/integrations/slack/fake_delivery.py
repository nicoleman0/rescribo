"""Fake Slack writes for explicitly enabled end-to-end environments."""

from typing import Any
from uuid import uuid4


class FakeDeliveryClient:
    def conversations_open(self, *, users: str) -> dict[str, Any]:
        return {"ok": True, "channel": {"id": f"DFAKE{users}"}}

    def chat_postMessage(
        self, *, channel: str, text: str, blocks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {"ok": True, "channel": channel, "ts": f"{uuid4().int}.000001"}

    def chat_update(
        self,
        *,
        channel: str,
        ts: str,
        text: str,
        blocks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {"ok": True, "channel": channel, "ts": ts}


_fake = FakeDeliveryClient()


def fake_delivery_client() -> FakeDeliveryClient:
    return _fake
