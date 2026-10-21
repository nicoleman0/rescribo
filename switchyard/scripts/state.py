#!/usr/bin/env python3
"""Read and update issue records in the main checkout's ignored state folder."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def fail(issue, message):
    print(f"Issue {issue}: {message}", file=sys.stderr)
    raise SystemExit(1)


def repo_root():
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    first = next(line[9:] for line in result.stdout.splitlines() if line.startswith("worktree "))
    return Path(first)


def issue_path(issue):
    if not issue.isascii() or not issue.isdigit():
        fail(issue, "issue number must contain only digits")
    return repo_root() / ".switchyard" / "state" / f"{issue}.json"


def read_record(issue):
    path = issue_path(issue)
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        fail(issue, "no record. Run setup-worktree.sh, or state.py init")
    except (OSError, json.JSONDecodeError) as exc:
        fail(issue, f"cannot read record: {exc}")


def write_record(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def fields(args, issue):
    result = {}
    for item in args:
        if "=" not in item:
            fail(issue, f"expected key=value, got {item}")
        key, value = item.split("=", 1)
        if not key:
            fail(issue, "field name cannot be empty")
        if key == "issue":
            fail(issue, "issue is a reserved field")
        result[key] = value
    return result


def command(args):
    if not args:
        fail("?", "usage: state.py init|set|get|rm|status ...")
    action = args.pop(0)
    if action == "status":
        status()
        return
    if not args:
        fail("?", f"{action} requires an issue number")
    issue = args.pop(0)
    path = issue_path(issue)
    if action == "init":
        record = {"issue": issue, **fields(args, issue)}
        write_record(path, record)
    elif action == "set":
        record = read_record(issue)
        record.update(fields(args, issue))
        write_record(path, record)
    elif action == "get":
        if len(args) != 1:
            fail(issue, "get requires one field name")
        value = read_record(issue).get(args[0])
        if value is None or value == "":
            fail(issue, f"field {args[0]} is missing or empty")
        print(value)
    elif action == "rm":
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    else:
        fail(issue, f"unknown command {action}")


def status():
    folder = repo_root() / ".switchyard" / "state"
    records = []
    if folder.exists():
        for path in folder.glob("*.json"):
            try:
                records.append(json.loads(path.read_text()))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Cannot read {path}: {exc}", file=sys.stderr)
    records.sort(key=lambda row: int(row["issue"]))
    if not records:
        print("No issues in flight.")
        return

    herdr_records = [r for r in records if r.get("runner") == "herdr" and r.get("worker")]
    agents = {}
    herdr_error = False
    if herdr_records:
        try:
            result = subprocess.run(["herdr", "agent", "list"], check=True, capture_output=True, text=True)
            payload = json.loads(result.stdout)
            rows = payload.get("result", {}).get("agents", payload.get("agents", []))
            agents = {row.get("name"): row for row in rows}
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            print(f"Could not read Herdr agents: {exc}", file=sys.stderr)
            herdr_error = True

    headers = ["ISSUE", "BRANCH", "PHASE", "BACKEND", "WORKER", "PANE", "STATE", "PR"]
    table = []
    for record in records:
        issue, branch = record.get("issue", "?"), record.get("branch", "-")
        worker = record.get("worker") or record.get("session") or "-"
        phase = record.get("role") or "setup"
        live_state = "-"
        if not record.get("path") or not Path(record["path"]).is_dir():
            live_state = "no worktree"
        elif record.get("worker"):
            if herdr_error:
                live_state = "?"
            else:
                live_state = agents.get(record["worker"], {}).get("agent_status", "ended")
        pr = "-"
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--head", branch, "--state", "all", "--json", "number,state", "--limit", "1"],
                check=True, capture_output=True, text=True,
            )
            prs = json.loads(result.stdout)
            if prs:
                pr = f"#{prs[0]['number']} {prs[0]['state'].lower()}"
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as exc:
            print(f"Could not read PR for issue {issue}: {exc}", file=sys.stderr)
            pr = "?"
        table.append([issue, branch, phase, record.get("backend") or "-", worker,
                      record.get("pane") or "-", live_state, pr])
    widths = [max(len(headers[i]), *(len(row[i]) for row in table)) for i in range(len(headers))]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    for row in table:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


if __name__ == "__main__":
    try:
        command(sys.argv[1:])
    except subprocess.CalledProcessError as exc:
        fail("?", f"command failed: {exc}")
    except OSError as exc:
        fail("?", f"operating system error: {exc}")
