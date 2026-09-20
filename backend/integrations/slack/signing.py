"""Slack interaction request signature verification."""

from collections.abc import Mapping

from slack_sdk.signature import SignatureVerifier


class InvalidSlackSignature(PermissionError):
    """Raised when an interaction request fails Slack signature verification."""


def verify_slack_signature(*, signing_secret: str, body: bytes, headers: Mapping[str, str]) -> None:
    """Verify the Slack signing signature over the raw body, or raise.

    `SignatureVerifier.is_valid` performs the v0 HMAC computation, enforces the
    five-minute replay window, and compares digests in constant time. Wrap it as
    an exception-raising trust boundary: a malformed timestamp header or a
    missing signature header raises rather than returning a false verdict.
    """
    timestamp = headers.get("X-Slack-Request-Timestamp")
    signature = headers.get("X-Slack-Signature")
    if not timestamp or not signature:
        raise InvalidSlackSignature("Missing Slack signature headers.")
    verifier = SignatureVerifier(signing_secret=signing_secret)
    try:
        valid = verifier.is_valid(body=body, timestamp=timestamp, signature=signature)
    except ValueError as error:
        raise InvalidSlackSignature(f"Malformed Slack signature headers: {error}") from error
    if not valid:
        raise InvalidSlackSignature("Slack signature verification failed.")
