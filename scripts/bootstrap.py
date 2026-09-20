"""Create local configuration without overwriting existing credentials."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    print("Keeping existing .env")
else:
    content = (root / ".env.example").read_text()
    content = content.replace("replace-with-a-random-local-secret", secrets.token_urlsafe(48))
    content = content.replace("rescribo_dev", secrets.token_hex(24))
    # Exclusive creation prevents accidentally replacing a concurrent setup's credentials.
    with destination.open("x") as handle:
        destination.chmod(0o600)
        handle.write(content)
    print("Created private local .env")
