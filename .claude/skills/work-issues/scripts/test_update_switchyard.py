"""Offline integration tests for update-switchyard.py."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("update-switchyard.py").resolve()
VERSION = ".claude/skills/work-issues/VERSION"
ROUTING = ".claude/skills/work-issues/routing.md"
PATHS = ".claude/skills/work-issues/update-paths.txt"
UPDATER = ".claude/skills/work-issues/scripts/update-switchyard.py"
COVERED = [
    ".claude/agents",
    ".claude/skills/work-issues",
    ".github/ISSUE_TEMPLATE",
    ".github/workflows/switchyard.yml",
    ".gitignore",
    "AGENTS.md",
    "openspec/config.yaml",
]
INIT_COMMAND = "npx @fission-ai/openspec init --tools claude,codex,opencode"
RELEASE_AGENTS = (
    b"# Working in this repository\n\n"
    b"## Workflow\n\n"
    b"- ship issues one at a time\n"
    b"- archive the change in the PR\n\n"
    b"## Project\n\n"
    b"Describe the project here.\n\n"
    b"## Writing\n\n"
    b"- plain words\n"
)
RELEASE_CONFIG = (
    b"schema: spec-driven\n\n"
    b"context: |\n"
    b"  delivery order lives in issues\n\n"
    b"rules:\n"
    b"  proposal:\n"
    b"    - Name the GitHub issue the change delivers.\n"
    b"  tasks:\n"
    b"    - Include the repository checks from AGENTS.md as the final task group.\n"
)
RELEASE_GITIGNORE = (
    b"node_modules/\n\n"
    b"# Briefs, answers, screenshots, and PR bodies stay local to each worktree.\n"
    b".claude/*\n!.claude/skills/\n!.claude/commands/\n!.claude/agents/\n"
)
DEFAULT_FILES = {
    ".claude/agents/worker.md": b"worker v1\n",
    ".claude/skills/work-issues/workflow.txt": b"first line\nstable line\nlast line\n",
    ".github/ISSUE_TEMPLATE/issue.yml": b"issue\n",
    ".github/workflows/switchyard.yml": b"ci v1\n",
    ".gitignore": RELEASE_GITIGNORE,
    "AGENTS.md": RELEASE_AGENTS,
    "openspec/config.yaml": RELEASE_CONFIG,
    VERSION: b"0.1.0\n",
    PATHS: ("\n".join(COVERED) + "\n").encode(),
    "outside.txt": b"outside v1\n",
}


class UpdateSwitchyardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="test-update-switchyard-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "upstream"
        self.project = self.root / "project"
        self.env = os.environ.copy()
        self.env.update({
            "GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User", "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        })
        self.init_repo(self.source)
        self.write_files(self.source, DEFAULT_FILES)
        self.commit(self.source, "base")
        self.tag(self.source, "v0.1.0")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(["git", *args], cwd=repo, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            self.fail(result.stderr.decode(errors="replace"))
        return result

    def init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.git(path, "init", "-q")
        self.git(path, "config", "user.name", "Test User")
        self.git(path, "config", "user.email", "test@example.com")

    def write_files(self, root: Path, files: dict[str, bytes]) -> None:
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def commit(self, repo: Path, message: str) -> None:
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "--allow-empty", "-qm", message)

    def tag(self, repo: Path, name: str) -> None:
        self.git(repo, "tag", name)

    def make_target(self, changes: dict[str, bytes | None] | None = None, *, paths: bytes | None = None) -> None:
        for name, content in (changes or {}).items():
            path = self.source / name
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        if paths is not None:
            (self.source / PATHS).write_bytes(paths)
        self.commit(self.source, "target")
        self.tag(self.source, "v0.2.0")

    def make_project(self, *, files: dict[str, bytes] | None = None, version: bytes | None = b"0.1.0\n",
                     own_tag: bool = False, sparse: bool = False) -> None:
        self.init_repo(self.project)
        initial = files if files is not None else {k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"}
        initial = dict(initial)
        if version is not None:
            initial[VERSION] = version
        else:
            initial.pop(VERSION, None)
        self.write_files(self.project, initial)
        if sparse:
            for name in list((self.project / ".github").rglob("*")) if (self.project / ".github").exists() else []:
                if name.is_file():
                    name.unlink()
            for name in (".gitignore", "AGENTS.md", "openspec/config.yaml"):
                (self.project / name).unlink(missing_ok=True)
        self.commit(self.project, "unrelated project history")
        if own_tag:
            self.tag(self.project, "v0.1.0")

    def run_update(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
        env = self.env.copy()
        env["TMPDIR"] = str(self.root)
        return subprocess.run(["python3", str(SCRIPT), "--source", str(self.source), *args],
                              cwd=cwd or self.project, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def assert_refused_clean(self, result: subprocess.CompletedProcess[bytes], message: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout.decode() + result.stderr.decode())
        self.assertIn(message, result.stderr.decode())
        status = self.git(self.project, "status", "--porcelain").stdout
        self.assertEqual(status, b"")

    def test_unedited_file_updates_and_version_names_target(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"first line\nstable line\nnew last line\n"})
        self.make_project()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(),
                         b"first line\nstable line\nnew last line\n")
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertIn(b"updated: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_project_owned_routing_is_never_updated_or_removed(self) -> None:
        self.source.joinpath(ROUTING).write_bytes(b"example v1\n")
        self.commit(self.source, "add routing base")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({ROUTING: b"example v2\n"})
        files = {k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"}
        files[ROUTING] = b"project edit\n"
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"project edit\n")
        self.assertNotIn(("updated: " + ROUTING).encode(), result.stdout)
        self.assertNotIn(("added: " + ROUTING).encode(), result.stdout)

    def test_project_owned_routing_survives_upstream_deletion_without_report(self) -> None:
        self.source.joinpath(ROUTING).write_bytes(b"example v1\n")
        self.commit(self.source, "add routing base")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({ROUTING: None})
        files = {k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"}
        files[ROUTING] = b"project edit\n"
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"project edit\n")
        for status in ("removed", "kept", "updated", "added"):
            self.assertNotIn((status + ": " + ROUTING).encode(), result.stdout)

    def test_unedited_project_owned_routing_is_not_updated(self) -> None:
        self.source.joinpath(ROUTING).write_bytes(b"example v1\n")
        self.commit(self.source, "add routing base")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({ROUTING: b"example v2\n"})
        files = {k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"}
        files[ROUTING] = b"example v1\n"
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"example v1\n")
        self.assertNotIn(("updated: " + ROUTING).encode(), result.stdout)
        self.assertNotIn(("added: " + ROUTING).encode(), result.stdout)

    def test_project_owned_routing_adds_only_when_missing_and_other_files_update(self) -> None:
        self.source.joinpath(ROUTING).write_bytes(b"example v1\n")
        self.commit(self.source, "add routing base")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({ROUTING: b"example v2\n", ".claude/skills/work-issues/workflow.txt": b"new content\n"})
        files = {k: v for k, v in DEFAULT_FILES.items() if k not in ("outside.txt", ROUTING)}
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"example v2\n")
        self.assertIn(("added: " + ROUTING).encode(), result.stdout)
        self.assertIn(b"updated: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_project_owned_routing_added_in_new_release_does_not_conflict(self) -> None:
        (self.source / ROUTING).unlink(missing_ok=True)
        self.commit(self.source, "ensure base has no routing")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({ROUTING: b"example\n"})
        files = {k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"}
        files[ROUTING] = b"local file\n"
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"local file\n")
        self.assertNotIn(("conflict: " + ROUTING).encode(), result.stdout)

    def test_independent_edits_merge(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"first line\nstable line\nupstream last\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/skills/work-issues/workflow.txt": b"local first\nstable line\nlast line\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"local first\nstable line\nupstream last\n", (self.project / ".claude/skills/work-issues/workflow.txt").read_bytes())
        self.assertIn(b"merged: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_same_line_conflict_has_both_sides_and_base(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"upstream\nstable line\nlast line\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/skills/work-issues/workflow.txt": b"local\nstable line\nlast line\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        text = (self.project / ".claude/skills/work-issues/workflow.txt").read_text()
        for marker in ("<<<<<<< yours", "||||||| switchyard 0.1.0", "=======", ">>>>>>> switchyard 0.2.0", "local", "upstream"):
            self.assertIn(marker, text)
        self.assertIn(b"conflict: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_multiple_conflict_regions_are_reported_as_conflict(self) -> None:
        base = "\n".join(chr(ord("a") + index) for index in range(10)) + "\n"
        upstream = "\n".join(["upstream first", *list("bcdefghi"), "upstream last"]) + "\n"
        local = "\n".join(["local first", *list("bcdefghi"), "local last"]) + "\n"
        (self.source / "AGENTS.md").write_text(base)
        self.commit(self.source, "ten-line base")
        self.git(self.source, "tag", "-f", "v0.1.0")
        self.make_target({"AGENTS.md": upstream.encode()})
        self.make_project(files={**{key: value for key, value in DEFAULT_FILES.items() if key != "outside.txt"},
                                 "AGENTS.md": local.encode()})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"conflict: AGENTS.md", result.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_bytes().count(b"<<<<<<< yours"), 2)

    def test_upstream_mode_only_change_updates_unedited_and_edited_files(self) -> None:
        target = self.source / ".claude/skills/work-issues/workflow.txt"
        target.chmod(0o755)
        self.commit(self.source, "make workflow executable")
        self.tag(self.source, "v0.2.0")
        for edited in (False, True):
            with self.subTest(edited=edited):
                if edited:
                    self.project = self.root / "edited-project"
                files = {key: value for key, value in DEFAULT_FILES.items() if key != "outside.txt"}
                if edited:
                    files[".claude/skills/work-issues/workflow.txt"] = b"local content\n"
                self.make_project(files=files)
                result = self.run_update()
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertTrue(os.access(self.project / ".claude/skills/work-issues/workflow.txt", os.X_OK))
                self.assertIn(b"updated: .claude/skills/work-issues/workflow.txt", result.stdout)
                expected = b"local content\n" if edited else DEFAULT_FILES[".claude/skills/work-issues/workflow.txt"]
                self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(), expected)

    def test_both_sides_add_same_path_conflicts(self) -> None:
        self.make_target({".claude/skills/work-issues/new.txt": b"upstream\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/skills/work-issues/new.txt": b"local\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"conflict: .claude/skills/work-issues/new.txt", result.stdout)
        self.assertIn(b"local", (self.project / ".claude/skills/work-issues/new.txt").read_bytes())
        self.assertIn(b"upstream", (self.project / ".claude/skills/work-issues/new.txt").read_bytes())

    def test_unedited_upstream_deletion_removes_file(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": None})
        self.make_project()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertFalse((self.project / ".claude/skills/work-issues/workflow.txt").exists())
        self.assertIn(b"removed: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_locally_edited_upstream_deletion_is_kept(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": None})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/skills/work-issues/workflow.txt": b"local edit\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(), b"local edit\n")
        self.assertIn(b"kept: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_locally_deleted_upstream_edit_is_kept(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"upstream edit\n"})
        self.make_project()
        (self.project / ".claude/skills/work-issues/workflow.txt").unlink()
        self.commit(self.project, "delete locally")
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.project / ".claude/skills/work-issues/workflow.txt").exists())
        self.assertIn(b"kept: .claude/skills/work-issues/workflow.txt", result.stdout)

    def test_unchanged_files_outside_paths_and_second_run(self) -> None:
        self.make_target({"outside.txt": b"outside v2\n"})
        local = b"my project edit\n"
        self.make_project(files={**DEFAULT_FILES,
                                 ".claude/skills/work-issues/workflow.txt": local})
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(), local)
        self.assertEqual((self.project / "outside.txt").read_bytes(), b"outside v1\n")
        self.commit(self.project, "accept update")
        again = self.run_update()
        self.assertEqual(again.returncode, 0)
        self.assertIn(b"Already at 0.2.0", again.stdout)

    def test_modes_follow_new_and_merged_upstream_modes(self) -> None:
        new_file = self.source / ".claude/skills/work-issues/new-exec.sh"
        new_file.write_text("#!/bin/sh\n")
        new_file.chmod(0o755)
        self.make_target({".claude/skills/work-issues/workflow.txt":
                          b"first line\nstable line\nupstream last\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/skills/work-issues/workflow.txt":
                                 b"local first\nstable line\nlast line\n"})
        edited = self.project / ".claude/skills/work-issues/workflow.txt"
        edited.chmod(0o755)
        self.git(self.project, "add", str(edited.relative_to(self.project)))
        self.git(self.project, "commit", "-qm", "make edited hook executable")
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(os.access(self.project / ".claude/skills/work-issues/new-exec.sh", os.X_OK))
        self.assertTrue(os.access(edited, os.X_OK))
        self.assertIn(b"local first\nstable line\nupstream last\n", edited.read_bytes())

    def test_sparse_existing_repo_is_not_populated(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"first line\nstable line\nupdated\n"})
        self.make_project(files={".claude/agents/local.md": b"agent\n",
                                 ".claude/skills/work-issues/workflow.txt": DEFAULT_FILES[".claude/skills/work-issues/workflow.txt"],
                                 PATHS: DEFAULT_FILES[PATHS]}, sparse=True)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for path in (".github", ".gitignore", "AGENTS.md", "openspec/config.yaml"):
            self.assertFalse((self.project / path).exists(), path)

    def test_refusals(self) -> None:
        self.make_target()
        self.make_project()
        self.project.joinpath(VERSION).unlink()
        self.commit(self.project, "remove version")
        result = self.run_update()
        self.assert_refused_clean(result, "no VERSION")
        self.assertIn("v0.1.0, v0.2.0", result.stderr.decode())
        result = self.run_update("--from", "v9.0.0")
        self.assert_refused_clean(result, "unknown base release")
        result = self.run_update("--from", "0.1.0", "--to", "9.0.0")
        self.assert_refused_clean(result, "unknown target release")
        result = self.run_update("--from", "0.2.0", "--to", "0.1.0")
        self.assert_refused_clean(result, "older than base")
        result = self.run_update("--from", "0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_dirty_project_and_non_repo_are_refused(self) -> None:
        self.make_target()
        self.make_project()
        (self.project / ".claude/skills/work-issues/workflow.txt").write_text("dirty\n")
        result = self.run_update()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"uncommitted changes", result.stderr)
        self.assertIn(b" M ", self.git(self.project, "status", "--porcelain").stdout)
        outside = self.root / "outside"
        outside.mkdir()
        result = self.run_update(cwd=outside)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"inside a git work tree", result.stderr)

    def test_missing_target_paths_and_path_list_are_refused(self) -> None:
        self.make_target(paths=b".claude/agents\nmissing/path\n")
        self.make_project()
        result = self.run_update()
        self.assert_refused_clean(result, "missing/path")

    def test_target_without_path_list_is_refused(self) -> None:
        self.make_target()
        (self.source / PATHS).unlink()
        self.commit(self.source, "remove list")
        self.tag(self.source, "v0.3.0")
        self.make_project()
        result = self.run_update("--to", "0.3.0")
        self.assert_refused_clean(result, "has no")

    def test_local_directory_and_symlink_are_refused(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"changed\n"})
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind):
                self.make_project()
                path = self.project / ".claude/skills/work-issues/workflow.txt"
                path.unlink()
                if kind == "directory":
                    path.mkdir()
                else:
                    path.symlink_to("../agent")
                self.commit(self.project, f"local {kind}")
                result = self.run_update()
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"directory or symlink", result.stderr)
                self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")
                shutil.rmtree(self.project)

    def test_symlinked_parent_is_refused(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"changed\n"})
        self.make_project()
        claude = self.project / ".claude"
        saved = self.root / "claude-directory"
        claude.rename(saved)
        claude.symlink_to(saved, target_is_directory=True)
        self.commit(self.project, "replace workflow directory with symlink")
        result = self.run_update()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"not a real directory", result.stderr)
        self.assertEqual((saved / "skills/work-issues/workflow.txt").read_bytes(),
                         DEFAULT_FILES[".claude/skills/work-issues/workflow.txt"])

    def test_binary_merge_refuses_before_writing_other_files(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"other changed\n",
                          ".claude/agents/worker.md": b"\0upstream\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/agents/worker.md": b"\0local\n"})
        before = (self.project / ".claude/skills/work-issues/workflow.txt").read_bytes()
        result = self.run_update()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"cannot merge", result.stderr)
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(), before)
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")

    def test_version_prefixes_and_project_tags_are_unchanged(self) -> None:
        self.make_target({".claude/skills/work-issues/workflow.txt": b"first line\nstable line\nupdated\n"})
        self.make_project(own_tag=True)
        other = self.root / "project-without-v"
        subprocess.run(["git", "clone", "--quiet", str(self.project), str(other)], check=True,
                       env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        before = self.git(self.project, "for-each-ref", "--format=%(refname):%(objectname)").stdout
        prefixed = self.run_update("--from", "v0.1.0")
        plain = self.run_update("--from", "0.1.0", cwd=other)
        self.assertEqual(prefixed.returncode, 0, prefixed.stderr.decode())
        self.assertEqual(plain.returncode, 0, plain.stderr.decode())
        after = self.git(self.project, "for-each-ref", "--format=%(refname):%(objectname)").stdout
        self.assertEqual(before, after)
        expected = b"first line\nstable line\nupdated\n"
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(), expected)
        self.assertEqual((other / ".claude/skills/work-issues/workflow.txt").read_bytes(), expected)

    def test_non_regular_upstream_entry_is_refused(self) -> None:
        self.make_target()
        link = self.source / ".claude/skills/work-issues/link"
        link.symlink_to("workflow.txt")
        self.commit(self.source, "symlink")
        self.tag(self.source, "v0.3.0")
        self.make_project()
        result = self.run_update("--to", "0.3.0")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"not a regular file", result.stderr)
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")

    def test_install_into_empty_repo(self) -> None:
        self.make_target()
        self.make_project(files={"README.md": b"mine\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        for path in (".claude/agents/worker.md", ".claude/skills/work-issues/workflow.txt", PATHS,
                     ".github/ISSUE_TEMPLATE/issue.yml", ".github/workflows/switchyard.yml",
                     "AGENTS.md", ".gitignore", "openspec/config.yaml"):
            self.assertIn(("added: " + path).encode(), result.stdout, path)
        self.assertIn(b"added: 8", result.stdout)
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertEqual((self.project / "README.md").read_bytes(), b"mine\n")
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b".claude/*\n!.claude/skills/\n!.claude/commands/\n!.claude/agents/\n")
        self.assertEqual((self.project / "openspec/config.yaml").read_bytes(),
                         b"schema: spec-driven\n\n"
                         b"rules:\n"
                         b"  proposal:\n"
                         b"    - Name the GitHub issue the change delivers.\n"
                         b"  tasks:\n"
                         b"    - Include the repository checks from AGENTS.md as the final task group.\n")
        self.assertIn(("Next: run " + INIT_COMMAND).encode(), result.stdout)
        self.assertNotIn(b"checks in AGENTS.md", result.stdout)
        after = self.run_update()
        self.assertEqual(after.returncode, 0, after.stdout.decode() + after.stderr.decode())
        self.assertIn(b"Already at 0.2.0", after.stdout)

    def test_install_merges_own_files(self) -> None:
        self.make_target()
        own_config = (b"schema: spec-driven\n"
                      b"context: |\n"
                      b"  my project\n"
                      b"\n"
                      b"rules:\n"
                      b"  proposal:\n"
                      b"    - Name the GitHub issue the change delivers.\n"
                      b"    - Local proposal step.\n"
                      b"  tasks:\n"
                      b"    - Local task rule.\n")
        self.make_project(files={
            "README.md": b"mine\n",
            ".gitignore": b"node_modules/\n.env\n",
            "openspec/config.yaml": own_config,
            "AGENTS.md": b"# My repo\n\n## Build\n\nmake\n",
        }, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"merged: .gitignore", result.stdout)
        self.assertIn(b"merged: openspec/config.yaml", result.stdout)
        self.assertIn(b"merged: AGENTS.md", result.stdout)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b"node_modules/\n.env\n.claude/*\n!.claude/skills/\n!.claude/commands/\n!.claude/agents/\n")
        self.assertEqual((self.project / "openspec/config.yaml").read_bytes(),
                         b"schema: spec-driven\n"
                         b"context: |\n"
                         b"  my project\n"
                         b"\n"
                         b"rules:\n"
                         b"  proposal:\n"
                         b"    - Name the GitHub issue the change delivers.\n"
                         b"    - Local proposal step.\n"
                         b"  tasks:\n"
                         b"    - Local task rule.\n"
                         b"    - Include the repository checks from AGENTS.md as the final task group.\n")
        self.assertEqual((self.project / "AGENTS.md").read_bytes(),
                         b"# My repo\n\n## Build\n\nmake\n\n"
                         b"## Workflow\n\n- ship issues one at a time\n- archive the change in the PR\n\n"
                         b"## Writing\n\n- plain words\n")
        self.assertIn(b"Next: list the project's checks in AGENTS.md", result.stdout)
        self.assertNotIn(b"openspec init", result.stdout)

    def test_install_gitignore_adds_only_missing_lines(self) -> None:
        self.make_target()
        self.make_project(files={".gitignore": b".claude/*\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"merged: .gitignore", result.stdout)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b".claude/*\n!.claude/skills/\n!.claude/commands/\n!.claude/agents/\n")

    def test_install_agents_conflict_keeps_local_content(self) -> None:
        self.make_target()
        self.make_project(files={"AGENTS.md": b"# My repo\n\n## Workflow\n\n- local rule\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 1, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"conflict: AGENTS.md", result.stdout)
        text = (self.project / "AGENTS.md").read_bytes()
        self.assertIn(b"# My repo\n\n## Workflow", text)
        for marker in ("<<<<<<< yours", "- local rule", "- ship issues one at a time",
                       ">>>>>>> switchyard 0.2.0"):
            self.assertIn(marker, text.decode())
        self.assertNotIn(b"Describe the project here.", text)
        self.assertIn(b"## Writing\n\n- plain words", text)
        self.assertIn(b"Next: list the project's checks in AGENTS.md", result.stdout)

    def test_install_agents_empty_section_takes_release_body(self) -> None:
        self.make_target()
        self.make_project(files={"AGENTS.md": b"# My repo\n\n## Workflow\n\n## Writing\n\n- plain words\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"merged: AGENTS.md", result.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(),
                         b"# My repo\n\n## Workflow\n\n"
                         b"- ship issues one at a time\n- archive the change in the PR\n\n"
                         b"## Writing\n\n- plain words\n")

    def test_install_identical_agents_is_silent(self) -> None:
        self.make_target()
        self.make_project(files={"AGENTS.md": RELEASE_AGENTS}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        for status in ("added", "merged", "conflict", "updated", "removed"):
            self.assertNotIn((status + ": AGENTS.md").encode(), result.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)
        self.assertIn(b"Next: list the project's checks in AGENTS.md", result.stdout)

    def test_install_keeps_existing_project_owned_routing(self) -> None:
        self.make_target({ROUTING: b"release routing\n"})
        self.make_project(files={ROUTING: b"project routing\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertNotIn(b"routing.md", result.stdout)
        self.assertEqual((self.project / ROUTING).read_bytes(), b"project routing\n")

    def test_install_adds_missing_project_owned_routing(self) -> None:
        self.make_target({ROUTING: b"release routing\n"})
        self.make_project(files={}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn(("added: " + ROUTING).encode(), result.stdout)
        self.assertEqual((self.project / ROUTING).read_bytes(), b"release routing\n")

    def test_install_existing_ordinary_file_conflicts(self) -> None:
        self.make_target()
        self.make_project(files={"README.md": b"mine\n",
                                 ".claude/skills/work-issues/workflow.txt": b"local hook\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 1, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"conflict: .claude/skills/work-issues/workflow.txt", result.stdout)
        text = (self.project / ".claude/skills/work-issues/workflow.txt").read_bytes()
        for marker in (b"<<<<<<< yours", b"local hook", b"first line", b">>>>>>> switchyard 0.2.0"):
            self.assertIn(marker, text)

    def test_install_identical_ordinary_file_is_silent(self) -> None:
        self.make_target()
        self.make_project(files={".claude/skills/work-issues/workflow.txt":
                                 DEFAULT_FILES[".claude/skills/work-issues/workflow.txt"]}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertNotIn(b"workflow.txt", result.stdout)
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(),
                         DEFAULT_FILES[".claude/skills/work-issues/workflow.txt"])

    def test_install_refusals(self) -> None:
        self.make_target()
        self.make_project()
        result = self.run_update("--install", "--from", "0.1.0")
        self.assert_refused_clean(result, "does not take --from")
        result = self.run_update("--install")
        self.assert_refused_clean(result, "already names 0.1.0")
        self.assertIn(b"without --install", result.stderr)
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")

    def test_install_malformed_rules_refused_before_writes(self) -> None:
        self.make_target()
        for local_config in (b"rules: 3\n", b"- a list, not a mapping\n",
                             b"schema: x\nrules:\n    - oops\n"):
            with self.subTest(rules=local_config):
                self.make_project(files={"README.md": b"mine\n", "openspec/config.yaml": local_config},
                                  version=None)
                result = self.run_update("--install")
                self.assertEqual(result.returncode, 2, result.stdout.decode() + result.stderr.decode())
                self.assertIn(b"openspec/config.yaml", result.stderr)
                self.assertEqual((self.project / "openspec/config.yaml").read_bytes(), local_config)
                self.git(self.project, "reset", "-q", "--hard")
                self.git(self.project, "clean", "-qfd")

    def test_install_malformed_agents_refused_before_writes(self) -> None:
        self.make_target()
        local_agents = b"# x\n\n## Workflow\n\na\n\n## Workflow\n\ndup\n"
        self.make_project(files={"README.md": b"mine\n", "AGENTS.md": local_agents}, version=None)
        result = self.run_update("--install")
        self.assert_refused_clean(result, "more than one Workflow section")

    def test_install_refuses_release_without_managed_sections(self) -> None:
        self.make_target({"AGENTS.md": b"# no sections\n"})
        self.make_project(files={"AGENTS.md": b"# own\n"}, version=None)
        result = self.run_update("--install")
        self.assert_refused_clean(result, "release AGENTS.md has no Workflow section")

    def test_install_targets_an_older_release(self) -> None:
        self.make_target()
        self.git(self.source, "commit", "--allow-empty", "-qm", "release 3")
        self.tag(self.source, "v0.3.0")
        self.make_project(files={}, version=None)
        result = self.run_update("--install", "--to", "0.1.0")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")
        self.assertEqual((self.project / ".claude/skills/work-issues/workflow.txt").read_bytes(),
                         b"first line\nstable line\nlast line\n")
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)
        self.project = self.root / "versionless-project"
        self.make_project(files={}, version=None)
        result = self.run_update("--install", "--to", "9.9.9")
        self.assert_refused_clean(result, "unknown target release")

    def test_install_runs_from_a_clone_beside_the_repo(self) -> None:
        self.make_target({UPDATER: Path(SCRIPT).read_bytes()})
        self.make_project(files={"README.md": b"mine\n"}, version=None)
        clone = self.root / "switchyard"
        subprocess.run(["git", "clone", "--quiet", str(self.source), str(clone)], check=True,
                       env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(
            ["python3", "../switchyard/.claude/skills/work-issues/scripts/update-switchyard.py",
             "--install", "--source", "../switchyard"],
            cwd=self.project, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertIn(b"added: AGENTS.md", result.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)


if __name__ == "__main__":
    unittest.main()
