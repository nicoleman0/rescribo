"""Restore a backup into a throwaway database, check it, then drop it.

Usage: restore_check.py [DUMP]. Defaults to the newest dump in backups/.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"


def database_url() -> str:
    if url := os.environ.get("RESCRIBO_DATABASE_URL"):
        return url
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("RESCRIBO_DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    sys.exit("RESCRIBO_DATABASE_URL is not set. Run task bootstrap first.")


def in_postgres(command: str, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    # Server-side tools match the server version and need nothing on the host.
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "sh", "-c", command],
        cwd=ROOT,
        check=True,
        **kwargs,  # type: ignore[call-overload]
    )


def main() -> None:
    if len(sys.argv) > 1:
        dump = Path(sys.argv[1])
    else:
        dumps = sorted(BACKUPS.glob("*.dump"))
        if not dumps:
            sys.exit("No dump in backups/. Run task backup first.")
        dump = dumps[-1]
    if not dump.is_file() or dump.stat().st_size == 0:
        sys.exit(f"Dump {dump} is missing or empty.")
    name = f"rescribo_restore_{uuid.uuid4().hex[:12]}"
    in_postgres(f'createdb -U "$POSTGRES_USER" {name}')
    try:
        with dump.open("rb") as source:
            in_postgres(
                f'pg_restore -U "$POSTGRES_USER" -d {name} --no-owner --exit-on-error',
                stdin=source,
            )
        parts = urlsplit(database_url())
        env = {**os.environ, "RESCRIBO_DATABASE_URL": urlunsplit(parts._replace(path=f"/{name}"))}
        subprocess.run(
            ["uv", "run", "python", "backend/manage.py", "check_restore"],
            cwd=ROOT,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        sys.exit(f"Restore check failed: {' '.join(map(str, error.cmd[-3:]))}")
    finally:
        in_postgres(f'dropdb -U "$POSTGRES_USER" --if-exists {name}')
    print(f"Restore check passed for {dump.name}.")


if __name__ == "__main__":
    main()
