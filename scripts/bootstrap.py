"""Create local configuration without overwriting existing credentials."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    print("Keeping existing .env")
    current = destination.read_text()
    example = (root / ".env.example").read_text()
    present = {line.split("=", 1)[0] for line in current.splitlines() if "=" in line}
    missing = [
        line
        for line in example.splitlines()
        if "=" in line and line.split("=", 1)[0] not in present
    ]
    if missing:
        with destination.open("a") as handle:
            handle.write("\n" + "\n".join(missing) + "\n")
        print("Added missing local settings from .env.example")
else:
    content = (root / ".env.example").read_text()
    content = content.replace("replace-with-a-random-local-secret", secrets.token_urlsafe(48))
    content = content.replace("rescribo_dev", secrets.token_hex(24))
    # Exclusive creation prevents accidentally replacing a concurrent setup's credentials.
    with destination.open("x") as handle:
        destination.chmod(0o600)
        handle.write(content)
    print("Created private local .env")
