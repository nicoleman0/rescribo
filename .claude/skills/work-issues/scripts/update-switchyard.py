#!/usr/bin/env python3
"""Merge workflow files from a later Switchyard release into this repository.

`--install` instead puts the workflow into a repository that has never had
Switchyard: it has no base release, so it adds missing files and merges
existing ones against an empty base.
"""

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
PROJECT_OWNED = {".claude/skills/work-issues/routing.md"}
PATHS_PATH = ".claude/skills/work-issues/update-paths.txt"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
AGENTS_PATH = "AGENTS.md"
AGENTS_SECTIONS = ("Workflow", "Writing")
GITIGNORE_PATH = ".gitignore"
CONFIG_PATH = "openspec/config.yaml"
INIT_COMMAND = "npx @fission-ai/openspec init --tools claude,codex,opencode"


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


def merge_with_empty_base(path: str, local: bytes | None, target: bytes | None,
                          target_version: str) -> tuple[bytes, bool]:
    """Three-way merge with no base release; markers name the two sides."""
    with tempfile.TemporaryDirectory(prefix="switchyard-install-") as temporary:
        temp = Path(temporary)
        files = [temp / name for name in ("yours", "base", f"switchyard {target_version}")]
        for file_path, content in zip(files, (local or b"", b"", target or b"")):
            file_path.write_bytes(content)
        result = subprocess.run(
            ["git", "merge-file", "-p", "-L", "yours", "-L", f"switchyard {target_version}",
             "-L", f"switchyard {target_version}", str(files[0]), str(files[1]), str(files[2])],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    if result.returncode < 0 or result.returncode > 127:
        detail = result.stderr.decode(errors="replace").strip()
        raise Refusal(f"cannot merge {path}: {detail or 'git merge-file failed'}")
    return result.stdout, result.returncode != 0


def file_text(path: str, content: bytes, release: bool = False) -> str:
    prefix = "release " if release else ""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal(f"{prefix}{path} is not UTF-8 text")


def agents_section_spans(lines: list[str], path: str, release: bool = False) -> dict[str, tuple[int, int]]:
    """For each top-level `## Name` section: (heading index, next heading index).

    Headings inside fenced code are skipped; the section reaches to the next
    `## ` heading of any name. Duplicate section names are refused, and a
    release file must carry every managed section.
    """
    headings: list[tuple[int, str]] = []
    fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            headings.append((index, line[len("## "):].strip()))
    label = f"release {path}" if release else path
    for name in AGENTS_SECTIONS:
        matches = [index for index, seen in headings if seen == name]
        if release and not matches:
            raise Refusal(f"{label} has no {name} section")
        if len(matches) > 1:
            raise Refusal(f"{label} has more than one {name} section")
    return {name: (index, headings[number + 1][0] if number + 1 < len(headings) else len(lines))
            for number, (index, name) in enumerate(headings) if name in AGENTS_SECTIONS}


def merge_agents_sections(release: bytes, local: bytes | None,
                          target_label: str) -> tuple[bytes | None, str | None]:
    """Install merge for AGENTS.md: the whole release file when absent, otherwise
    the Workflow and Writing section bodies. Other content stays untouched; the
    release's Project section is never added to an existing file.
    """
    if local is None:
        return release, "added"
    local_text = file_text(AGENTS_PATH, local)
    release_text = file_text(AGENTS_PATH, release, release=True)
    local_lines = local_text.split("\n") if local_text else []
    release_lines = release_text.split("\n")
    spans = agents_section_spans(local_lines, AGENTS_PATH)
    release_spans = agents_section_spans(release_lines, AGENTS_PATH, release=True)

    changed = False
    conflict = False
    # (start, end) splice ranges in the local file; applied bottom-up
    splices: list[tuple[int, int, list[str]]] = []

    for name in AGENTS_SECTIONS:
        if name in spans:
            start, end = spans[name]
            body = "\n".join(local_lines[start + 1:end]).rstrip("\n")
            release_start, release_end = release_spans[name]
            release_body = "\n".join(release_lines[release_start + 1:release_end]).rstrip("\n")
            if body == release_body:
                continue
            changed = True
            if not body.strip():
                # empty section body: the release body drops in without a merge
                merged_lines = release_body.split("\n") if release_body else []
            else:
                merged, conflicted = merge_with_empty_base(
                    f"{AGENTS_PATH} ({name})", body.encode("utf-8"),
                    release_body.encode("utf-8"), target_label)
                conflict = conflict or conflicted
                merged_lines = merged.decode("utf-8").rstrip("\n").split("\n")
            if end < len(local_lines):
                merged_lines.append("")
            splices.append((start + 1, end, merged_lines))
            continue
        changed = True
        release_start, release_end = release_spans[name]
        release_body = "\n".join(release_lines[release_start + 1:release_end]).rstrip("\n").strip("\n")
        section_lines = [f"## {name}"]
        if release_body:
            section_lines += [""] + release_body.split("\n")
        if splices and splices[-1][0] == len(local_lines):
            start, end, piece = splices[-1]
            splices[-1] = (start, end, piece + [""] + section_lines)
        else:
            splices.append((len(local_lines), len(local_lines), section_lines))

    if not changed:
        return None, None
    new_lines = list(local_lines)
    replacements = [item for item in splices if item[0] != item[1]]
    appends = [item for item in splices if item[0] == item[1]]
    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        new_lines[start:end] = replacement
    for _, _, piece in appends:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines += piece
    merged_text = "\n".join(new_lines)
    if not local_text:
        if merged_text and not merged_text.endswith("\n"):
            merged_text += "\n"
    elif local_text.endswith("\n") != merged_text.endswith("\n"):
        merged_text += "\n" if local_text.endswith("\n") else merged_text[:-1]
    return merged_text.encode("utf-8"), "conflict" if conflict else "merged"


def top_key_line(line: str) -> re.Match | None:
    return re.match(r"^([A-Za-z_][A-Za-z0-9_.-]*):(.*)$", line)


def yaml_top_key_indexes(lines: list[str], path: str) -> list[tuple[str, int, str]]:
    """(key, line index, inline value) for every top-level mapping key."""
    keys: list[tuple[str, int, str]] = []
    for index, line in enumerate(lines):
        if not line or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            continue
        match = top_key_line(line)
        if match is None:
            raise Refusal(
                f"{path} is not a top-level mapping: line {index + 1} is neither a `key:` "
                "line, a comment, nor indented content"
            )
        keys.append((match.group(1), index, match.group(2)))
    return keys


def read_rules_entries(lines: list[str], path: str, rules_index: int, rules_end: int) -> list[tuple[str, str | None, int]]:
    """File-order records of a `rules:` mapping: (key, entry text, line index).

    A key line without entries is `(key, None, index)`. Entries are the text
    after `    - `, right-stripped. Every other shape is refused.
    """
    entries: list[tuple[str, str | None, int]] = []
    child_key: str | None = None
    for index in range(rules_index + 1, rules_end):
        line = lines[index]
        if not line or line.lstrip().startswith("#"):
            continue
        child = re.match(r"^  ([A-Za-z_][A-Za-z0-9_.-]*):(.*)$", line)
        if child:
            if child.group(2).strip():
                raise Refusal(f"{path}: rules.{child.group(1)} is not a list of `- ` entries")
            child_key = child.group(1)
            if any(seen == child_key for seen, _, _ in entries):
                raise Refusal(f"{path}: rules.{child_key} appears twice")
            entries.append((child_key, None, index))
            continue
        if child_key is None:
            raise Refusal(f"{path}: {line!r} under rules comes before a rule key")
        entry = re.match(r"^    - (.*)$", line)
        if entry is None:
            raise Refusal(f"{path}: unexpected line under rules at line {index + 1}: {line!r}")
        entries.append((child_key, entry.group(1).rstrip(), index))
    return entries


def rules_block(text: str, path: str) -> tuple[list[tuple[str, str | None, int]], int, int] | None:
    """Locate and parse the `rules:` block: (entries, rules line index, block end)."""
    lines = text.split("\n")
    keys = yaml_top_key_indexes(lines, path)
    rules = [(key, index, inline) for key, index, inline in keys if key == "rules"]
    if not rules:
        return None
    if len(rules) > 1:
        raise Refusal(f"{path}: top-level rules appears more than once")
    _, rules_index, inline = rules[0]
    if inline.strip():
        raise Refusal(f"{path}: rules is not a top-level mapping; its value is {inline.strip()!r}")
    rules_end = next((index for _, index, _ in keys if index > rules_index), len(lines))
    return read_rules_entries(lines, path, rules_index, rules_end), rules_index, rules_end


def install_gitignore_merge(release: bytes, local: bytes | None) -> tuple[bytes | None, str | None]:
    """Add the release's `.claude` lines; existing lines are never rewritten."""
    release_text = file_text(GITIGNORE_PATH, release, release=True)
    patterns = [line.rstrip() for line in release_text.split("\n")
                if ".claude" in line and not line.lstrip().startswith("#")]
    if local is None:
        if not patterns:
            return None, None
        return ("\n".join(patterns) + "\n").encode("utf-8"), "added"
    local_text = file_text(GITIGNORE_PATH, local)
    missing = [pattern for pattern in patterns
               if pattern not in {line.rstrip() for line in local_text.split("\n")}]
    if not missing:
        return None, None
    prefix = local_text if local_text.endswith("\n") else local_text + "\n"
    return (prefix + "\n".join(missing) + "\n").encode("utf-8"), "merged"


def render_rules(pairs: list[tuple[str, str]]) -> list[str]:
    rendered: list[str] = []
    last_key: str | None = None
    for key, entry in pairs:
        if key != last_key:
            rendered.append(f"  {key}:")
            last_key = key
        rendered.append(f"    - {entry}")
    return rendered


def install_config_merge(release: bytes, local: bytes | None) -> tuple[bytes | None, str | None]:
    """Merge the release's `rules` into the project's openspec/config.yaml.

    Only the top-level rules mapping changes; every other key, including
    `context`, stays byte-for-byte. Malformed structures are refused.
    """
    release_block = rules_block(file_text(CONFIG_PATH, release, release=True), CONFIG_PATH)
    if release_block is None:
        raise Refusal(f"release {CONFIG_PATH} has no rules: block")
    release_entries, _, _ = release_block
    release_pairs = [(key, entry) for key, entry, _ in release_entries if entry is not None]
    rules_header = ["rules:"]
    if local is None:
        if not release_pairs:
            return None, None
        head = ["schema: spec-driven", ""]
        return ("\n".join(head + rules_header + render_rules(release_pairs)) + "\n").encode("utf-8"), "added"

    local_text = file_text(CONFIG_PATH, local)
    local_block = rules_block(local_text, CONFIG_PATH)
    if local_block is None:
        # no rules mapping yet: append one, keeping the project's own keys
        tail = local_text if local_text.endswith("\n") else local_text + "\n"
        return (tail + "\n".join(rules_header + render_rules(release_pairs)) + "\n").encode("utf-8"), "merged"

    local_entries, rules_index, rules_end = local_block
    owned = {(key, entry) for key, entry, _ in local_entries if entry is not None}
    missing = [pair for pair in release_pairs if pair not in owned]
    if not missing:
        return None, None
    lines = local_text.split("\n")
    last_entry: dict[str, int] = {}
    for key, entry, index in local_entries:
        if entry is not None:
            last_entry[key] = index
        elif key not in last_entry:
            last_entry[key] = index  # a key line with no entries yet
    missing_keys = list(dict.fromkeys(key for key, _ in missing))
    missing_entries = {key: [entry for seen, entry in missing if seen == key] for key in missing_keys}
    # entries for rule keys the file has go after that key's last entry; new
    # rule keys go after the last content line inside the rules block
    splices: list[tuple[int, list[str]]] = []
    new_key_block: list[str] = []
    for key in missing_keys:
        if key in last_entry:
            entries = [f"    - {entry}" for entry in missing_entries[key]]
            splices.append((last_entry[key] + 1, entries))
            continue
        new_key_block.append(f"  {key}:")
        new_key_block += [f"    - {entry}" for entry in missing_entries[key]]
    if new_key_block:
        insert_at = rules_index + 1
        for index in range(rules_end - 1, rules_index, -1):
            if lines[index].strip():
                insert_at = index + 1
                break
        splices.append((insert_at, new_key_block))
    final_lines = list(lines)
    for position, piece in sorted(splices, key=lambda item: item[0], reverse=True):
        final_lines[position:position] = piece
    return "\n".join(final_lines).encode("utf-8"), "merged"


def run() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Switchyard repository or local clone")
    parser.add_argument("--from", dest="base", help="base release (for projects without VERSION)")
    parser.add_argument("--to", dest="target", help="target release; defaults to newest release")
    parser.add_argument("--install", action="store_true",
                        help="install the workflow into a repository that has no VERSION file")
    args = parser.parse_args()

    try:
        if args.install and args.base:
            raise Refusal("--install starts from nothing; it does not take --from")
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
        if args.install and stored is not None:
            raise Refusal(f"{VERSION_PATH} already names {stored}; run the updater without --install")
        raw_base = args.base or stored

        openspec_existed = (project_root / "openspec").is_dir()
        agents_existed = local_file(project_root, AGENTS_PATH)[0] is not None

        with tempfile.TemporaryDirectory(prefix="switchyard-source-") as temporary:
            bare = Path(temporary) / "source.git"
            clone = subprocess.run(["git", "clone", "--quiet", "--bare", args.source, str(bare)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if clone.returncode:
                raise Refusal(clone.stderr.decode(errors="replace").strip() or "could not clone source")
            releases = list_releases(bare)
            if not raw_base and not args.install:
                visible = ", ".join(releases) or "(none found)"
                raise Refusal(f"no VERSION found; pass --from VERSION. Available releases: {visible}")
            base = None
            base_version = None
            if not args.install:
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
            base_label = ".".join(map(str, base_version)) if not args.install else ""
            if not args.install:
                if target_version < base_version:
                    raise Refusal(f"target {target} is older than base {base}")
                if target == base:
                    print(f"Already at {target_label}")
                    return 0

            paths = read_update_paths(bare, target)
            target_tree = selected_entries(tree_entries(bare, target, paths), paths)
            for listed in paths:
                if not any(covers(path, [listed]) for path in target_tree):
                    raise Refusal(f"path {listed} from {PATHS_PATH} is missing in {target}")

            actions: list[Action] = []
            counts: dict[str, int] = {}

            if args.install:
                for path in sorted(target_tree):
                    target_item = target_tree[path]
                    mode, target_content = target_item
                    if path in PROJECT_OWNED:
                        local_content, _ = local_file(project_root, path)
                        if local_content is None:
                            actions.append(Action(path, "added", target_content, mode))
                        continue
                    local_content, _ = local_file(project_root, path)
                    content = None
                    status = None
                    if path == AGENTS_PATH:
                        content, status = merge_agents_sections(target_content, local_content, target_label)
                    elif path == GITIGNORE_PATH:
                        content, status = install_gitignore_merge(target_content, local_content)
                    elif path == CONFIG_PATH:
                        content, status = install_config_merge(target_content, local_content)
                    elif local_content is None:
                        content, status = target_content, "added"
                    elif local_content != target_content:
                        content, conflict = merge_with_empty_base(path, local_content, target_content, target_label)
                        status = "conflict" if conflict else "merged"
                    if status and content is not None:
                        merge_mode = None if local_content is not None else mode
                        actions.append(Action(path, status, content, merge_mode))
            else:
                base_tree = selected_entries(tree_entries(bare, base, paths), paths)
                all_paths = sorted(set(base_tree) | set(target_tree))
                for path in all_paths:
                    base_item = base_tree.get(path)
                    target_item = target_tree.get(path)
                    if path in PROJECT_OWNED:
                        local_content, _ = local_file(project_root, path)
                        if target_item is not None and local_content is None:
                            actions.append(Action(path, "added", target_item[1], target_item[0]))
                        continue
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
            if args.install:
                if not openspec_existed:
                    print(f"Next: run {INIT_COMMAND} in this repository")
                if agents_existed:
                    print("Next: list the project's checks in AGENTS.md")
            return 1 if counts.get("conflict") or counts.get("kept") else 0
    except (OSError, Refusal) as error:
        print(f"update-switchyard: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(run())
