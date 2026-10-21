#!/usr/bin/env python3
"""Claim and read Redis databases assigned to issue worktrees."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

MIN_INDEX = 1
MAX_INDEX = 15


def choose(held):
    for index in range(MIN_INDEX, MAX_INDEX + 1):
        if index not in held:
            return index
    raise ValueError("no free index")


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def state_folder():
    checkout = os.environ.get("MAIN_CHECKOUT")
    if not checkout:
        fail("MAIN_CHECKOUT is required")
    return Path(checkout) / ".switchyard" / "state"


def read_records(folder):
    records = {}
    holders = {}
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"Cannot read Redis index record {path.name}: {exc}")
        issue = str(record.get("issue", path.stem))
        value = record.get("redis_index")
        if value is None:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            index = value
        elif isinstance(value, str) and value.isascii() and value.isdigit():
            index = int(value)
        else:
            index = None
        if index is None or not MIN_INDEX <= index <= MAX_INDEX:
            fail(f"Issue {issue} has invalid redis_index {value!r}; expected 1 to 15")
        if index in holders:
            fail(f"Redis index {index} is held by issues {holders[index]} and {issue}")
        holders[index] = issue
        records[issue] = index
    return records


def state_set(issue, index):
    script = Path(__file__).resolve().parents[1] / "scripts" / "state.py"
    subprocess.run([sys.executable, str(script), "set", issue, f"redis_index={index}"], check=True)


def claim(issue, folder):
    folder.mkdir(parents=True, exist_ok=True)
    lock_path = folder / ".redis-index.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = read_records(folder)
        if issue in records:
            print(records[issue])
            return
        try:
            index = choose(set(records.values()))
        except ValueError:
            owners = ", ".join(sorted(records, key=lambda key: int(key)))
            fail(f"No Redis index is free. Issues {owners} hold 1 to 15. Tear one down first.")
        state_set(issue, index)
        print(index)


def held(issue, folder):
    value = read_records(folder).get(issue)
    if value is not None:
        print(value)


def main(args):
    if len(args) != 2 or args[0] not in {"claim", "held"}:
        fail("Usage: redis_index.py claim|held ISSUE")
    action, issue = args
    if not issue.isascii() or not issue.isdigit():
        fail("Issue number must contain only digits")
    folder = state_folder()
    if action == "claim":
        claim(issue, folder)
    else:
        held(issue, folder)


if __name__ == "__main__":
    main(sys.argv[1:])
