"""Rejection reasons and provider error codes shared across the Slack boundary."""


class ChannelRejected(ValueError):
    """Raised when a Slack conversation is not an eligible capture source.

    The message names the reason code and the channel id only; never the
    message text or actor identity.
    """

    def __init__(self, reason: str, channel_id: str) -> None:
        super().__init__(f"{reason}:{channel_id}")
        self.reason = reason
        self.channel_id = channel_id


def slack_error_code(error: Exception) -> str | None:
    """Pull Slack's `error` code out of a failed call, whose body may be bytes."""
    response = getattr(error, "response", None)
    data = getattr(response, "data", None)
    code = data.get("error") if isinstance(data, dict) else None
    return code if isinstance(code, str) else None
