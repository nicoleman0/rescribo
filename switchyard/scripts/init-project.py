#!/usr/bin/env python3
"""Initialize a project freshly made from Switchyard.

Moves the workflow guide to docs/WORKFLOW.md and deletes Switchyard-only
files, including locally edited ones: a committed copy stays in git history.
Skips listed paths with uncommitted changes, because git could not restore
those, stops before any change when the directory has no git work tree
or when the guide does not start with Switchyard's heading, and never commits.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

README = Path("README.md")
GUIDE = Path("docs/WORKFLOW.md")
CHART = Path("docs/workflow.svg")
DELETED_PATHS = [
    Path("CHANGELOG.md"),
    Path("CONTRIBUTING.md"),
    Path("LICENSE"),
    Path("docs/switchyard.svg"),
    Path("docs/social-preview.png"),
    Path("docs/pixelart.py"),
    Path(".claude/skills/work-issues/update-paths.txt"),
]
TEMPLATE_HEADING = "# Switchyard"
BANNER_TARGET = "(docs/switchyard.svg)"
CHART_REF = "(docs/workflow.svg)"


def stop(message: str):
    print(f"Stopping. {message}", file=sys.stderr)
    raise SystemExit(1)


def verify_work_tree(root: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        stop("git is required to check for uncommitted changes before any file moves or is deleted.")
    if result.returncode != 0 or result.stdout.strip() != "true":
        stop(
            "This directory is not inside a git work tree, so git could not restore "
            "deleted or moved files. Run init from the project root of a repository "
            "made from Switchyard."
        )


def has_template_heading(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    return text.startswith(TEMPLATE_HEADING)


def verify_template(root: Path) -> None:
    if (root / README).exists():
        if not has_template_heading(root / README):
            stop(
                f'{README} does not start with Switchyard\'s heading ("{TEMPLATE_HEADING}"), '
                "so this is not a fresh copy of the template. Init changed nothing. "
                "Run it only in a new project made from Switchyard."
            )
    elif not has_template_heading(root / GUIDE):
        stop(
            f'Neither {README} nor {GUIDE} starts with Switchyard\'s heading ("{TEMPLATE_HEADING}"), '
            "so this is not a fresh copy of the template. Init changed nothing. "
            "Run it only in a new project made from Switchyard."
        )


def changed_paths(root: Path) -> set[str]:
    listed = [README, *DELETED_PATHS]
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall", "--", *(str(p) for p in listed)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stop("git status failed before any change: " + result.stderr.strip())
    changed = set()
    for line in result.stdout.splitlines():
        path = line[3:] if len(line) > 3 else ""
        if path.startswith('"'):
            path = path.strip('"')
        changed.add(path)
    return changed


def edit_guide(text: str) -> str:
    lines = text.splitlines()
    banner = next(
        (i for i, line in enumerate(lines) if line.lstrip().startswith("![") and BANNER_TARGET in line),
        None,
    )
    if banner is not None:
        del lines[banner]
        # Collapse the blank line the banner left behind.
        if 0 < banner < len(lines) and lines[banner - 1] == "" and lines[banner] == "":
            del lines[banner]
    text = "\n".join(lines) + "\n"
    text = text.replace(CHART_REF, "(workflow.svg)")
    lines = text.splitlines()
    heading = next((i for i, line in enumerate(lines) if line.rstrip() == "## License"), None)
    if heading is not None:
        # LICENSE gets deleted, so the guide's License section goes too: the
        # heading plus its body, up to the next heading or the end of the file.
        end = heading + 1
        while end < len(lines) and not lines[end].startswith("#"):
            end += 1
        del lines[heading:end]
        while lines and not lines[-1].strip():
            lines.pop()
        text = "\n".join(lines) + "\n"
    return text


def main() -> None:
    root = Path.cwd()
    verify_work_tree(root)
    verify_template(root)
    changed = changed_paths(root)

    def skip_reason(path: Path) -> str | None:
        if not path.exists():
            return "absent"
        if str(path) in changed:
            return "uncommitted changes"
        return None

    print("Switchyard init")

    if GUIDE.exists():
        print(f"skipped   {README} ({GUIDE} already exists)")
    else:
        reason = skip_reason(README)
        if reason:
            print(f"skipped   {README} ({reason})")
        else:
            GUIDE.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(README, GUIDE)
            GUIDE.write_text(edit_guide(GUIDE.read_text()))
            print(f"moved     {README} -> {GUIDE}")

    for path in DELETED_PATHS:
        reason = skip_reason(path)
        if reason:
            print(f"skipped   {path} ({reason})")
        else:
            path.unlink()
            print(f"deleted   {path}")

    if CHART.exists():
        print(f"kept      {CHART}")

    print()
    print("Init made no commits. Next:")
    print("- Add your own README.md.")
    print("- Add your own LICENSE.")
    print("- Fill in the Project section of AGENTS.md: checks, shared services, and conventions.")


if __name__ == "__main__":
    main()
