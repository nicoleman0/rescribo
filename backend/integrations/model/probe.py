"""The connection test: a fixed prompt with no workspace content, answered as schema JSON."""

import secrets

from connections.errors import known_error
from integrations.model.clients import ModelClient

SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["ok"]},
        "nonce": {"type": "string"},
    },
    "required": ["status", "nonce"],
    "additionalProperties": False,
}
SYSTEM = "You check that a connection works. Reply only with JSON that matches the schema."
# Reasoning models spend part of this budget before they answer.
MAX_TOKENS = 4096


def check_model(client: ModelClient) -> None:
    """Pass only when the model echoes a fresh nonce, so a cached or canned reply fails."""
    nonce = secrets.token_hex(8)
    result = client.generate_json(
        system=SYSTEM,
        user=f'Return JSON with status "ok" and nonce "{nonce}".',
        schema=SCHEMA,
        max_tokens=MAX_TOKENS,
    )
    if result != {"status": "ok", "nonce": nonce}:
        raise known_error("model_no_structured_output")
