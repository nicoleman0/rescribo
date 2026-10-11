#!/usr/bin/env python3
"""Merge workflow files from a later Switchyard release into this repository."""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCE = "https://github.com/nicoleman0/switchyard.git"
VERSION_PATH = ".claude/skills/work-issues/VERSION"
PATHS_PATH = ".claude/skills/work-issues/update-paths.txt"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class Refusal(Exception):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(["git", *args], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise Refusal(message or f"git {' '.join(args)} failed")
    return result


def release_tuple(value: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.fullmatch(value)
    return tuple(map(int, match.groups())) if match else None


def list_releases(git_dir: Path) -> list[str]:
    result = git("--git-dir", str(git_dir), "tag", "--list", "v*", check=False)
    tags = [line.decode() for line in result.stdout.splitlines() if release_tuple(line.decode()) is not None]
    return sorted(tags, key=lambda tag: release_tuple(tag) or (0, 0, 0))


def tree_entries(git_dir: Path, tag: str, paths: list[str]) -> dict[str, tuple[int, bytes]]:
    result = git("--git-dir", str(git_dir), "ls-tree", "-r", "-z", tag, "--", *paths)
    entries: dict[str, tuple[int, bytes]] = {}
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode_text, kind, _object_id = metadata.split()
        mode = int(mode_text, 8)
        path = os.fsdecode(raw_path)
        if mode not in (0o100644, 0o100755) or kind != b"blob":
            raise Refusal(f"{tag}:{path} is not a regular file")
        entries[path] = (mode, git("--git-dir", str(git_dir), "show", f"{tag}:{path}").stdout)
    return entries


def read_update_paths(git_dir: Path, target: str) -> list[str]:
    result = git("--git-dir", str(git_dir), "show", f"{target}:{PATHS_PATH}", check=False)
    if result.returncode:
        raise Refusal(f"{target} has no {PATHS_PATH}; update from a release that includes the update path")
    paths: list[str] = []
    for line in result.stdout.decode().splitlines():
        path = line.split("#", 1)[0].strip()
        if not path:
            continue
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts or path in (".", ""):
            raise Refusal(f"unsafe path in {PATHS_PATH}: {path}")
        paths.append(path.rstrip("/"))
    return paths


def covers(path: str, roots: list[str]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


def selected_entries(entries: dict[str, tuple[int, bytes]], roots: list[str]) -> dict[str, tuple[int, bytes]]:
    return {path: item for path, item in entries.items() if covers(path, roots) and path != VERSION_PATH}


def validate_parent_paths(root: Path, path: str) -> None:
    current = root
    for part in Path(path).parts[:-1]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise Refusal(f"{current.relative_to(root)} is not a real directory")


def local_file(root: Path, path: str) -> tuple[bytes | None, int | None]:
    validate_parent_paths(root, path)
    full_path = root / path
    try:
        info = full_path.lstat()
    except FileNotFoundError:
        return None, None
    if stat.S_ISLNK(info.st_mode) or stat.S_ISDIR(info.st_mode):
        raise Refusal(f"{path} is a local directory or symlink where a file is expected")
    if not stat.S_ISREG(info.st_mode):
        raise Refusal(f"{path} is not a regular local file")
    return full_path.read_bytes(), (0o100755 if info.st_mode & 0o111 else 0o100644)


@dataclass
class Action:
    path: str
    status: str | None
    content: bytes | None
    mode: int | None


def merge_content(path: str, local: bytes | None, base: bytes | None, target: bytes | None,
                  base_version: str, target_version: str) -> tuple[bytes, bool]:
    with tempfile.TemporaryDirectory(prefix="switchyard-merge-") as temporary:
        temp = Path(temporary)
        files = [temp / name for name in ("local", "base", "target")]
        for file_path, content in zip(files, (local or b"", base or b"", target or b"")):
            file_path.write_bytes(content)
        result = subprocess.run(
            ["git", "merge-file", "-p", "--diff3", "-L", "yours", "-L", f"switchyard {base_version}",
             "-L", f"switchyard {target_version}", str(files[0]), str(files[1]), str(files[2])],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    if result.returncode < 0 or result.returncode > 127:
        detail = result.stderr.decode(errors="replace").strip()
        raise Refusal(f"cannot merge {path}: {detail or 'git merge-file failed'}")
    return result.stdout, result.returncode != 0


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Switchyard repository or local clone")
    parser.add_argument("--from", dest="base", help="base release (for projects without VERSION)")
    parser.add_argument("--to", dest="target", help="target release; defaults to newest release")
    args = parser.parse_args()

    try:
        root_result = git("rev-parse", "--show-toplevel", check=False)
        if root_result.returncode:
            raise Refusal("run this command inside a git work tree")
        project_root = Path(os.fsdecode(root_result.stdout.strip()))
        dirty = git("status", "--porcelain", "--untracked-files=no", cwd=project_root).stdout
        if dirty:
            raise Refusal("tracked files have uncommitted changes; commit or stash them before updating")

        validate_parent_paths(project_root, VERSION_PATH)
        version_file = project_root / VERSION_PATH
        try:
            version_info = version_file.lstat()
        except FileNotFoundError:
            stored = None
        else:
            if not stat.S_ISREG(version_info.st_mode):
                raise Refusal(f"{VERSION_PATH} is not a regular local file")
            stored = version_file.read_text().strip()
        raw_base = args.base or stored

        with tempfile.TemporaryDirectory(prefix="switchyard-source-") as temporary:
            bare = Path(temporary) / "source.git"
            clone = subprocess.run(["git", "clone", "--quiet", "--bare", args.source, str(bare)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if clone.returncode:
                raise Refusal(clone.stderr.decode(errors="replace").strip() or "could not clone source")
            releases = list_releases(bare)
            if not raw_base:
                visible = ", ".join(releases) or "(none found)"
                raise Refusal(f"no VERSION found; pass --from VERSION. Available releases: {visible}")
            base_version = release_tuple(raw_base)
            if base_version is None:
                raise Refusal(f"invalid base release {raw_base!r}; use X.Y.Z or vX.Y.Z")
            base = f"v{base_version[0]}.{base_version[1]}.{base_version[2]}"
            if base not in releases:
                raise Refusal(f"unknown base release {base}; available releases: {', '.join(releases)}")
            if args.target:
                target_version = release_tuple(args.target)
                if target_version is None:
                    raise Refusal(f"invalid target release {args.target!r}; use X.Y.Z or vX.Y.Z")
                target = f"v{target_version[0]}.{target_version[1]}.{target_version[2]}"
                if target not in releases:
                    raise Refusal(f"unknown target release {target}; available releases: {', '.join(releases)}")
            else:
                if not releases:
                    raise Refusal("source has no vX.Y.Z release tags")
                target = releases[-1]
                target_version = release_tuple(target)
                assert target_version is not None
            target_label = ".".join(map(str, target_version))
            base_label = ".".join(map(str, base_version))
            if target_version < base_version:
                raise Refusal(f"target {target} is older than base {base}")
            if target == base:
                print(f"Already at {target_label}")
                return 0

            paths = read_update_paths(bare, target)
            target_tree = selected_entries(tree_entries(bare, target, paths), paths)
            base_tree = selected_entries(tree_entries(bare, base, paths), paths)
            for listed in paths:
                if not any(covers(path, [listed]) for path in target_tree):
                    raise Refusal(f"path {listed} from {PATHS_PATH} is missing in {target}")

            all_paths = sorted(set(base_tree) | set(target_tree))
            actions: list[Action] = []
            counts: dict[str, int] = {}
            for path in all_paths:
                base_item = base_tree.get(path)
                target_item = target_tree.get(path)
                base_content = base_item[1] if base_item else None
                target_content = target_item[1] if target_item else None
                if base_item == target_item:
                    continue
                local_content, local_mode = local_file(project_root, path)
                target_mode_changed = target_item is not None and local_content is not None and local_mode != target_item[0] and (
                    base_item is None or base_item[0] != target_item[0]
                )
                if local_content == target_content:
                    if target_mode_changed:
                        actions.append(Action(path, "updated", target_content, target_item[0]))
                    continue
                if target_mode_changed and base_item is not None and target_item is not None and target_content == base_content:
                    actions.append(Action(path, "updated", local_content, target_item[0]))
                    continue
                if base_item is None and local_content is None:
                    actions.append(Action(path, "added", target_content, target_item[0] if target_item else None))
                elif local_content == base_content and target_item is not None:
                    mode = target_item[0] if base_item is None or base_item[0] != target_item[0] else local_mode
                    actions.append(Action(path, "updated", target_content, mode))
                elif local_content == base_content and target_item is None:
                    actions.append(Action(path, "removed", None, None))
                elif local_content is None and base_item is not None and target_item is not None:
                    actions.append(Action(path, "kept", None, None))
                elif target_item is None and local_content != base_content:
                    actions.append(Action(path, "kept", None, None))
                else:
                    merged, conflict = merge_content(path, local_content, base_content, target_content,
                                                     base_label, target_label)
                    if target_item and base_item and base_item[0] != target_item[0]:
                        mode = target_item[0]
                    else:
                        mode = local_mode or (target_item[0] if target_item else base_item[0])
                    actions.append(Action(path, "conflict" if conflict else "merged", merged, mode))

            for action in actions:
                full_path = project_root / action.path
                if action.status == "removed":
                    full_path.unlink()
                elif action.content is not None:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_bytes(action.content)
                    if action.mode is not None:
                        full_path.chmod(0o755 if action.mode == 0o100755 else 0o644)
                if action.status:
                    counts[action.status] = counts.get(action.status, 0) + 1
                    print(f"{action.status}: {action.path}")
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text(target_label + "\n")
            for status in ("added", "updated", "removed", "merged", "conflict", "kept"):
                if counts.get(status):
                    print(f"{status}: {counts[status]}")
            return 1 if counts.get("conflict") or counts.get("kept") else 0
    except (OSError, Refusal) as error:
        print(f"update-switchyard: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(run())
