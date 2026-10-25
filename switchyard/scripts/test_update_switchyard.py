"""Offline integration tests for update-switchyard.py."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("update-switchyard.py").resolve()
VERSION = "switchyard/VERSION"
ROUTING = "switchyard/routing.md"
PATHS = "switchyard/update-paths.txt"
CHANGELOG = "CHANGELOG.md"
UPDATER = "switchyard/scripts/update-switchyard.py"
COVERED = [
    ".claude/agents",
    ".claude/skills/work-issues/SKILL.md",
    "switchyard",
    ".github/ISSUE_TEMPLATE",
    ".github/workflows/switchyard.yml",
    ".gitignore",
    "AGENTS.md",
    "openspec/config.yaml",
]
UNDO_HEADER = b"To undo this run before you stage or commit, run:\n"
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
    b".switchyard/\n"
)
DEFAULT_FILES = {
    ".claude/agents/worker.md": b"worker v1\n",
    ".claude/skills/work-issues/SKILL.md": b"---\nname: work-issues\n---\nStub\n",
    "switchyard/workflow.txt": b"first line\nstable line\nlast line\n",
    ".github/ISSUE_TEMPLATE/issue.yml": b"issue\n",
    ".github/workflows/switchyard.yml": b"ci v1\n",
    ".gitignore": RELEASE_GITIGNORE,
    "AGENTS.md": RELEASE_AGENTS,
    "openspec/config.yaml": RELEASE_CONFIG,
    VERSION: b"0.1.0\n",
    PATHS: ("\n".join(COVERED) + "\n").encode(),
    "outside.txt": b"outside v1\n",
    CHANGELOG: (
        b"# Changelog\n\n"
        b"## [Unreleased]\n\n- upcoming\n\n"
        b"## [0.2.0] - 2026-10-11\n\n- second release\n\n"
        b"## [0.1.0] - 2026-10-10\n\n- first release\n\n"
        b"[Unreleased]: https://example.test/compare\n"
    ),
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

    def test_shipped_update_paths_names_the_claude_stub(self) -> None:
        shipped = Path(__file__).parents[2] / PATHS
        self.assertEqual(shipped.read_text().splitlines(), COVERED)
        self.assertIn(".claude/skills/work-issues/SKILL.md", shipped.read_text().splitlines())

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

    def run_check(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return self.run_update("--check", *args)

    def test_check_reports_current_behind_and_newer_versions(self) -> None:
        self.make_project()
        current = self.run_check()
        self.assertEqual(current.returncode, 0, current.stderr.decode())
        self.assertIn(b"0.1.0 is the newest release", current.stdout)

        self.make_target()
        behind = self.run_check()
        self.assertEqual(behind.returncode, 3)
        self.assertIn(b"0.1.0", behind.stdout)
        self.assertIn(b"0.2.0", behind.stdout)
        self.assertIn(b"npm init switchyard@latest update", behind.stdout)

        (self.project / VERSION).write_text("0.3.0\n")
        newer = self.run_check()
        self.assertEqual(newer.returncode, 0)
        self.assertIn(b"0.3.0 is newer than the newest release, 0.2.0", newer.stdout)

    def test_check_refuses_missing_or_malformed_version(self) -> None:
        self.make_project(version=None)
        missing = self.run_check()
        self.assertEqual(missing.returncode, 2)
        self.assertIn(b"no VERSION found; nothing to compare", missing.stderr)

        (self.project / VERSION).write_text("latest\n")
        malformed = self.run_check()
        self.assertEqual(malformed.returncode, 2)
        self.assertIn(b"invalid VERSION", malformed.stderr)

    def test_check_refuses_update_options(self) -> None:
        self.make_project()
        for option in (("--install",), ("--from", "0.1.0"), ("--to", "0.1.0"), ("--dry-run",)):
            with self.subTest(option=option):
                result = self.run_check(*option)
                self.assertEqual(result.returncode, 2)
                self.assertIn(b"--check cannot be combined", result.stderr)

    def test_help_lists_check_flag(self) -> None:
        result = subprocess.run(["python3", str(SCRIPT), "--help"], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"--check", result.stdout)
        self.assertIn(b"nothing", result.stdout)

    def test_check_allows_dirty_tree_without_writing(self) -> None:
        self.make_project()
        (self.project / "local.txt").write_text("dirty\n")
        before = self.git(self.project, "status", "--porcelain", "--untracked-files=all").stdout
        result = self.run_check()
        after = self.git(self.project, "status", "--porcelain", "--untracked-files=all").stdout
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(after, before)

    def test_check_refuses_outside_git_work_tree(self) -> None:
        outside = self.root / "outside-check"
        outside.mkdir()
        result = self.run_update("--check", cwd=outside)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"inside a git work tree", result.stderr)

    def test_check_reports_unreachable_source_and_empty_releases(self) -> None:
        self.make_project()
        unreachable = self.run_check("--source", str(self.root / "missing-source"))
        self.assertEqual(unreachable.returncode, 4)
        self.assertIn(b"could not reach", unreachable.stderr)

        empty = self.root / "empty-source"
        self.init_repo(empty)
        self.commit(empty, "no tags")
        no_releases = self.run_check("--source", str(empty))
        self.assertEqual(no_releases.returncode, 2)
        self.assertIn(b"source has no release tags", no_releases.stderr)

    def test_remote_release_timeout_kills_git_process_group(self) -> None:
        module_spec = importlib.util.spec_from_file_location("update_switchyard", SCRIPT)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        try:
            module_spec.loader.exec_module(module)
        finally:
            del sys.modules[module_spec.name]
        git_bin = self.root / "slow-bin"
        git_bin.mkdir()
        stub = git_bin / "git"
        stub.write_text("#!/bin/sh\nsleep 30\n")
        stub.chmod(0o755)
        started = time.monotonic()
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(git_bin) + os.pathsep + previous_path
        try:
            releases, reason = module.remote_releases("unused", 0.5)
        finally:
            os.environ["PATH"] = previous_path
        self.assertIsNone(releases)
        self.assertIn("timed out after 0.5s", reason)
        self.assertLess(time.monotonic() - started, 5)

    def before_undo(self, stdout: bytes) -> bytes:
        """The output of a real run without its undo block."""
        match = re.search(rb"Not undone: |\n" + re.escape(UNDO_HEADER), stdout)
        return stdout if match is None else stdout[:match.start()]

    def undo_commands(self, stdout: bytes) -> str:
        self.assertIn(UNDO_HEADER, stdout)
        return stdout.split(UNDO_HEADER, 1)[1].decode()

    def snapshot(self) -> tuple[bytes, list[str]]:
        dirs = sorted(path.relative_to(self.project).as_posix() for path in self.project.rglob("*")
                      if path.is_dir() and ".git" not in path.relative_to(self.project).parts)
        return self.git(self.project, "status", "--porcelain", "--untracked-files=all").stdout, dirs

    def assert_undo_restores(self, result: subprocess.CompletedProcess[bytes], before: tuple[bytes, list[str]]) -> None:
        undo = subprocess.run(["sh", "-c", self.undo_commands(result.stdout)], cwd=self.project,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(undo.returncode, 0, undo.stderr.decode())
        self.assertEqual(self.snapshot(), before)

    def assert_refused_clean(self, result: subprocess.CompletedProcess[bytes], message: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout.decode() + result.stderr.decode())
        self.assertIn(message, result.stderr.decode())
        status = self.git(self.project, "status", "--porcelain").stdout
        self.assertEqual(status, b"")

    def test_unedited_file_updates_and_version_names_target(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nnew last line\n"})
        self.make_project()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(),
                         b"first line\nstable line\nnew last line\n")
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertIn(b"updated: switchyard/workflow.txt", result.stdout)

    def test_undo_restores_updated_removed_and_added_files(self) -> None:
        self.make_target({".github/workflows/switchyard.yml": b"ci v2\n",
                          "switchyard/workflow.txt": None,
                          "switchyard/sub/new file.txt": b"new\n",
                          "switchyard/it's new.txt": b"quote\n"})
        self.make_project()
        before = self.snapshot()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        commands = self.undo_commands(result.stdout)
        self.assertIn("git restore -- ", commands)
        self.assertIn("'switchyard/sub/new file.txt'", commands)
        self.assertIn("rmdir -- switchyard/sub", commands)
        self.assertNotIn("#", commands)
        self.assert_undo_restores(result, before)
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")

    def test_undo_deletes_version_when_project_had_none(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nnew last line\n"})
        self.make_project(version=None)
        before = self.snapshot()
        result = self.run_update("--from", "0.1.0")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn("rm -- ", self.undo_commands(result.stdout))
        self.assertIn(VERSION, self.undo_commands(result.stdout))
        self.assert_undo_restores(result, before)
        self.assertFalse((self.project / VERSION).exists())

    def test_undo_after_install_into_empty_repo_leaves_nothing(self) -> None:
        self.make_target()
        self.make_project(files={"README.md": b"mine\n"}, version=None)
        before = self.snapshot()
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assert_undo_restores(result, before)
        again = self.run_update("--install")
        self.assertEqual(again.returncode, 0, again.stderr.decode())
        self.assertIn(("Next: run " + INIT_COMMAND).encode(), again.stdout)

    def test_undo_after_install_restores_tracked_agents_file(self) -> None:
        self.make_target()
        self.make_project(files={"AGENTS.md": b"# Mine\n\nrules\n"}, version=None)
        before = self.snapshot()
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertNotEqual((self.project / "AGENTS.md").read_bytes(), b"# Mine\n\nrules\n")
        self.assertIn("git restore -- AGENTS.md", self.undo_commands(result.stdout))
        self.assert_undo_restores(result, before)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), b"# Mine\n\nrules\n")

    def test_conflict_run_prints_undo_and_exits_one(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"upstream\nstable line\nlast line\n"})
        files = {**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                 "switchyard/workflow.txt": b"local\nstable line\nlast line\n"}
        self.make_project(files=files)
        before = self.snapshot()
        result = self.run_update()
        self.assertEqual(result.returncode, 1, result.stderr.decode())
        self.assertIn(b"conflict: switchyard/workflow.txt", result.stdout)
        self.assert_undo_restores(result, before)

    def test_untracked_merged_file_is_not_undone(self) -> None:
        self.make_target()
        self.make_project(files={"README.md": b"mine\n"}, version=None)
        (self.project / "AGENTS.md").write_bytes(b"# Mine\n\nrules\n")
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        note = b"Not undone: AGENTS.md was not tracked by git; restore it by hand."
        self.assertIn(note, result.stdout)
        self.assertLess(result.stdout.index(note), result.stdout.index(UNDO_HEADER))
        self.assertNotIn("AGENTS.md", self.undo_commands(result.stdout))

    def test_already_at_prints_no_undo(self) -> None:
        self.make_target()
        self.make_project(version=b"0.2.0\n")
        self.assertNotIn(UNDO_HEADER, self.run_update().stdout)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores directory permissions")
    def test_failed_write_prints_undo_for_finished_writes_and_exits_two(self) -> None:
        self.make_target({"switchyard/a/new.txt": b"new\n",
                          "switchyard/b.txt": b"b v2\n",
                          "switchyard/z/locked.txt": b"locked\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/b.txt": b"b v1\n", "switchyard/z/keep.txt": b"keep\n"})
        self.source.joinpath("switchyard/b.txt").write_bytes(b"b v2\n")
        locked = self.project / "switchyard/z"
        before = self.snapshot()
        locked.chmod(0o555)
        try:
            result = self.run_update("--from", "0.1.0")
        finally:
            locked.chmod(0o755)
        self.assertEqual(result.returncode, 2, result.stdout.decode())
        self.assertIn("update-switchyard:", result.stderr.decode())
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")
        commands = self.undo_commands(result.stdout)
        for name in ("switchyard/b.txt", "switchyard/a/new.txt", "rmdir -- switchyard/a"):
            self.assertIn(name, commands)
        self.assertNotIn("locked.txt", commands)
        self.assert_undo_restores(result, before)

    def test_release_notes_cover_selected_releases_newest_first(self) -> None:
        self.make_target()
        self.make_project()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"Release notes, 0.1.0 to 0.2.0:\n\n## [0.2.0]", result.stdout)
        self.assertNotIn(b"## [0.1.0]", result.stdout)
        self.assertNotIn(b"Unreleased", result.stdout)
        self.assertNotIn(b"[Unreleased]:", result.stdout)
        self.assertEqual((self.project / CHANGELOG).read_bytes(), DEFAULT_FILES[CHANGELOG])

    def test_release_notes_order_and_target_limit(self) -> None:
        self.make_target()
        self.source.joinpath(CHANGELOG).write_bytes(
            DEFAULT_FILES[CHANGELOG].replace(
                b"## [Unreleased]",
                b"## [0.3.0] - 2026-10-24\n\n- third release\n\n## [Unreleased]",
            )
        )
        self.commit(self.source, "third release")
        self.tag(self.source, "v0.3.0")
        self.make_project()
        result = self.run_update("--to", "0.3.0")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertLess(result.stdout.index(b"## [0.3.0]"), result.stdout.index(b"## [0.2.0]"))
        self.assertNotIn(b"## [0.1.0]", result.stdout)

        other = self.root / "project-to-0.2.0"
        self.project = other
        self.make_project()
        result = self.run_update("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"## [0.2.0]", result.stdout)
        self.assertNotIn(b"## [0.3.0]", result.stdout)

    def test_release_notes_are_in_dry_run_before_final_line(self) -> None:
        self.make_target()
        self.make_project()
        dry_run = self.run_update("--dry-run")
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr.decode())
        self.assertIn(b"Release notes, 0.1.0 to 0.2.0:", dry_run.stdout)
        self.assertTrue(dry_run.stdout.endswith(b"Dry run: nothing was written.\n"))
        real_run = self.run_update()
        self.assertEqual(real_run.returncode, 0, real_run.stderr.decode())
        self.assertEqual(dry_run.stdout, self.before_undo(real_run.stdout) + b"Dry run: nothing was written.\n")
        self.assertNotIn(UNDO_HEADER, dry_run.stdout)

    def test_already_at_has_no_release_notes_and_install_has_no_release_notes(self) -> None:
        self.make_target()
        self.make_project(version=b"0.2.0\n")
        already = self.run_update()
        self.assertEqual(already.stdout, b"Already at 0.2.0\n")

        install_project = self.root / "install-project"
        self.project = install_project
        self.make_project(files={"README.md": b"mine\n"}, version=None)
        installed = self.run_update("--install")
        self.assertEqual(installed.returncode, 0, installed.stderr.decode())
        self.assertNotIn(b"Release notes", installed.stdout)
        self.assertFalse((self.project / CHANGELOG).exists())

    def test_unavailable_release_notes_do_not_change_update_status(self) -> None:
        cases = (
            ("missing", None, b"has no CHANGELOG.md", 0),
            ("unknown heading", b"## [0.2.0] - date\n\n## Foo\n", b"unknown heading: ## Foo", 0),
            ("missing target section", b"## [Unreleased]\n\n## [0.1.0] - date\n", b"has no 0.2.0 section", 0),
            ("non-UTF-8", b"\xff", b"is not UTF-8", 0),
        )
        for name, changelog, reason, expected_status in cases:
            with self.subTest(name=name):
                shutil.rmtree(self.source)
                self.init_repo(self.source)
                self.write_files(self.source, DEFAULT_FILES)
                self.commit(self.source, "base")
                self.tag(self.source, "v0.1.0")
                self.project = self.root / f"project-{name.replace(' ', '-')}"
                changes = {CHANGELOG: changelog}
                self.make_target(changes)
                self.make_project()
                result = self.run_update()
                self.assertEqual(result.returncode, expected_status, result.stderr.decode())
                self.assertEqual(result.stdout.count(b"Release notes unavailable:"), 1)
                self.assertIn(reason, result.stdout)
                self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")

    def test_unavailable_release_notes_preserve_conflict_status(self) -> None:
        self.make_target({CHANGELOG: None,
                          "switchyard/workflow.txt": b"upstream\nstable line\nlast line\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/workflow.txt": b"local\nstable line\nlast line\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1, result.stderr.decode())
        self.assertIn(b"Release notes unavailable:", result.stdout)
        self.assertIn(b"conflict: switchyard/workflow.txt", result.stdout)

    def test_dry_run_reports_conflict_without_writing(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"upstream\nstable line\nlast line\n",
                          ".github/workflows/switchyard.yml": b"ci v2\n"})
        files = {**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                 "switchyard/workflow.txt": b"local\nstable line\nlast line\n"}
        self.make_project(files=files)

        dry_run = self.run_update("--dry-run")
        self.assertEqual(dry_run.returncode, 1, dry_run.stderr.decode())
        self.assertTrue(dry_run.stdout.endswith(b"Dry run: nothing was written.\n"))
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")
        self.assertEqual((self.project / VERSION).read_bytes(), b"0.1.0\n")

        real_run = self.run_update()
        self.assertEqual(real_run.returncode, 1, real_run.stderr.decode())
        self.assertEqual(dry_run.stdout, self.before_undo(real_run.stdout) + b"Dry run: nothing was written.\n")
        self.assertNotIn(UNDO_HEADER, dry_run.stdout)

    def test_clean_dry_run_exits_zero(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nnew last line\n"})
        self.make_project()
        result = self.run_update("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(result.stdout.endswith(b"Dry run: nothing was written.\n"))
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")
        self.assertEqual((self.project / VERSION).read_bytes(), b"0.1.0\n")

    def test_dry_run_already_at_target_reports_only_current_release(self) -> None:
        self.make_target()
        self.make_project(version=b"0.2.0\n")

        result = self.run_update("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"Already at 0.2.0\n")
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")
        self.assertEqual((self.project / VERSION).read_bytes(), b"0.2.0\n")

    def test_dry_run_refuses_dirty_project_without_writing(self) -> None:
        self.make_target()
        self.make_project()
        workflow = self.project / "switchyard/workflow.txt"
        workflow.write_bytes(b"dirty\n")
        before = workflow.read_bytes()
        result = self.run_update("--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"uncommitted changes", result.stderr)
        self.assertEqual(workflow.read_bytes(), before)
        self.assertEqual((self.project / VERSION).read_bytes(), b"0.1.0\n")

    def test_dry_run_binary_merge_refuses_without_writing(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"other changed\n",
                          ".claude/agents/worker.md": b"\0upstream\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/agents/worker.md": b"\0local\n"})
        before = self.git(self.project, "status", "--porcelain").stdout
        workflow = (self.project / "switchyard/workflow.txt").read_bytes()
        result = self.run_update("--dry-run")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"cannot merge", result.stderr)
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, before)
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), workflow)
        self.assertEqual((self.project / VERSION).read_bytes(), b"0.1.0\n")

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
        self.make_target({ROUTING: b"example v2\n", "switchyard/workflow.txt": b"new content\n"})
        files = {k: v for k, v in DEFAULT_FILES.items() if k not in ("outside.txt", ROUTING)}
        self.make_project(files=files)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / ROUTING).read_bytes(), b"example v2\n")
        self.assertIn(("added: " + ROUTING).encode(), result.stdout)
        self.assertIn(b"updated: switchyard/workflow.txt", result.stdout)

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
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nupstream last\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/workflow.txt": b"local first\nstable line\nlast line\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn(b"local first\nstable line\nupstream last\n", (self.project / "switchyard/workflow.txt").read_bytes())
        self.assertIn(b"merged: switchyard/workflow.txt", result.stdout)

    def test_same_line_conflict_has_both_sides_and_base(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"upstream\nstable line\nlast line\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/workflow.txt": b"local\nstable line\nlast line\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        text = (self.project / "switchyard/workflow.txt").read_text()
        for marker in ("<<<<<<< yours", "||||||| switchyard 0.1.0", "=======", ">>>>>>> switchyard 0.2.0", "local", "upstream"):
            self.assertIn(marker, text)
        self.assertIn(b"conflict: switchyard/workflow.txt", result.stdout)

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
        target = self.source / "switchyard/workflow.txt"
        target.chmod(0o755)
        self.commit(self.source, "make workflow executable")
        self.tag(self.source, "v0.2.0")
        for edited in (False, True):
            with self.subTest(edited=edited):
                if edited:
                    self.project = self.root / "edited-project"
                files = {key: value for key, value in DEFAULT_FILES.items() if key != "outside.txt"}
                if edited:
                    files["switchyard/workflow.txt"] = b"local content\n"
                self.make_project(files=files)
                result = self.run_update()
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertTrue(os.access(self.project / "switchyard/workflow.txt", os.X_OK))
                self.assertIn(b"updated: switchyard/workflow.txt", result.stdout)
                expected = b"local content\n" if edited else DEFAULT_FILES["switchyard/workflow.txt"]
                self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), expected)

    def test_both_sides_add_same_path_conflicts(self) -> None:
        self.make_target({"switchyard/new.txt": b"upstream\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/new.txt": b"local\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"conflict: switchyard/new.txt", result.stdout)
        self.assertIn(b"local", (self.project / "switchyard/new.txt").read_bytes())
        self.assertIn(b"upstream", (self.project / "switchyard/new.txt").read_bytes())

    def test_unedited_upstream_deletion_removes_file(self) -> None:
        self.make_target({"switchyard/workflow.txt": None})
        self.make_project()
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertFalse((self.project / "switchyard/workflow.txt").exists())
        self.assertIn(b"removed: switchyard/workflow.txt", result.stdout)

    def test_locally_edited_upstream_deletion_is_kept(self) -> None:
        self.make_target({"switchyard/workflow.txt": None})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/workflow.txt": b"local edit\n"})
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), b"local edit\n")
        self.assertIn(b"kept: switchyard/workflow.txt", result.stdout)

    def test_locally_deleted_upstream_edit_is_kept(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"upstream edit\n"})
        self.make_project()
        (self.project / "switchyard/workflow.txt").unlink()
        self.commit(self.project, "delete locally")
        result = self.run_update()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.project / "switchyard/workflow.txt").exists())
        self.assertIn(b"kept: switchyard/workflow.txt", result.stdout)

    def test_unchanged_files_outside_paths_and_second_run(self) -> None:
        self.make_target({"outside.txt": b"outside v2\n"})
        local = b"my project edit\n"
        self.make_project(files={**DEFAULT_FILES,
                                 "switchyard/workflow.txt": local})
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), local)
        self.assertEqual((self.project / "outside.txt").read_bytes(), b"outside v1\n")
        self.commit(self.project, "accept update")
        again = self.run_update()
        self.assertEqual(again.returncode, 0)
        self.assertIn(b"Already at 0.2.0", again.stdout)

    def test_modes_follow_new_and_merged_upstream_modes(self) -> None:
        new_file = self.source / "switchyard/new-exec.sh"
        new_file.write_text("#!/bin/sh\n")
        new_file.chmod(0o755)
        self.make_target({"switchyard/workflow.txt":
                          b"first line\nstable line\nupstream last\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 "switchyard/workflow.txt":
                                 b"local first\nstable line\nlast line\n"})
        edited = self.project / "switchyard/workflow.txt"
        edited.chmod(0o755)
        self.git(self.project, "add", str(edited.relative_to(self.project)))
        self.git(self.project, "commit", "-qm", "make edited hook executable")
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertTrue(os.access(self.project / "switchyard/new-exec.sh", os.X_OK))
        self.assertTrue(os.access(edited, os.X_OK))
        self.assertIn(b"local first\nstable line\nupstream last\n", edited.read_bytes())

    def test_sparse_existing_repo_is_not_populated(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nupdated\n"})
        self.make_project(files={".claude/agents/local.md": b"agent\n",
                                 "switchyard/workflow.txt": DEFAULT_FILES["switchyard/workflow.txt"],
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
        (self.project / "switchyard/workflow.txt").write_text("dirty\n")
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
        self.assert_refused_clean(result, "predates the switchyard/ layout")

    def test_base_before_switchyard_layout_is_refused(self) -> None:
        (self.source / PATHS).unlink()
        self.commit(self.source, "old layout")
        self.tag(self.source, "v0.0.1")
        self.make_project(version=b"0.0.1\n")
        result = self.run_update("--to", "0.1.0")
        self.assert_refused_clean(result, "v0.0.1 predates the switchyard/ layout")

    def test_local_directory_and_symlink_are_refused(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"changed\n"})
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind):
                self.make_project()
                path = self.project / "switchyard/workflow.txt"
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
        self.make_target({"switchyard/workflow.txt": b"changed\n"})
        self.make_project()
        workflow = self.project / "switchyard"
        saved = self.root / "workflow-directory"
        workflow.rename(saved)
        workflow.symlink_to(saved, target_is_directory=True)
        self.commit(self.project, "replace workflow directory with symlink")
        result = self.run_update()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"not a real directory", result.stderr)
        self.assertEqual((saved / "workflow.txt").read_bytes(),
                         DEFAULT_FILES["switchyard/workflow.txt"])

    def test_binary_merge_refuses_before_writing_other_files(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"other changed\n",
                          ".claude/agents/worker.md": b"\0upstream\n"})
        self.make_project(files={**{k: v for k, v in DEFAULT_FILES.items() if k != "outside.txt"},
                                 ".claude/agents/worker.md": b"\0local\n"})
        before = (self.project / "switchyard/workflow.txt").read_bytes()
        result = self.run_update()
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"cannot merge", result.stderr)
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), before)
        self.assertEqual((self.project / VERSION).read_text(), "0.1.0\n")

    def test_version_prefixes_and_project_tags_are_unchanged(self) -> None:
        self.make_target({"switchyard/workflow.txt": b"first line\nstable line\nupdated\n"})
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
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(), expected)
        self.assertEqual((other / "switchyard/workflow.txt").read_bytes(), expected)

    def test_non_regular_upstream_entry_is_refused(self) -> None:
        self.make_target()
        link = self.source / "switchyard/link"
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
        for path in (".claude/agents/worker.md", "switchyard/workflow.txt", PATHS,
                     ".github/ISSUE_TEMPLATE/issue.yml", ".github/workflows/switchyard.yml",
                     "AGENTS.md", ".gitignore", "openspec/config.yaml"):
            self.assertIn(("added: " + path).encode(), result.stdout, path)
        self.assertIn(b"added: 9", result.stdout)
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertEqual((self.project / "README.md").read_bytes(), b"mine\n")
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b".switchyard/\n")
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

    def test_install_dry_run_reports_without_creating_files(self) -> None:
        self.make_target()
        self.make_project(files={"README.md": b"mine\n"}, version=None)

        dry_run = self.run_update("--install", "--dry-run")
        self.assertEqual(dry_run.returncode, 0, dry_run.stdout.decode() + dry_run.stderr.decode())
        self.assertTrue(dry_run.stdout.endswith(b"Dry run: nothing was written.\n"))
        self.assertEqual(self.git(self.project, "status", "--porcelain").stdout, b"")
        self.assertFalse((self.project / VERSION).exists())
        self.assertEqual(sorted(path.relative_to(self.project).as_posix()
                                for path in self.project.rglob("*")
                                if path.is_file() and ".git" not in path.relative_to(self.project).parts),
                         ["README.md"])

        real_run = self.run_update("--install")
        self.assertEqual(real_run.returncode, 0, real_run.stderr.decode())
        self.assertEqual(dry_run.stdout, self.before_undo(real_run.stdout) + b"Dry run: nothing was written.\n")
        self.assertNotIn(UNDO_HEADER, dry_run.stdout)

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
                         b"node_modules/\n.env\n.switchyard/\n")
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
        self.make_project(files={".gitignore": b".env\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"merged: .gitignore", result.stdout)
        self.assertEqual((self.project / ".gitignore").read_bytes(),
                         b".env\n.switchyard/\n")

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
                                 "switchyard/workflow.txt": b"local hook\n"}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 1, result.stdout.decode() + result.stderr.decode())
        self.assertIn(b"conflict: switchyard/workflow.txt", result.stdout)
        text = (self.project / "switchyard/workflow.txt").read_bytes()
        for marker in (b"<<<<<<< yours", b"local hook", b"first line", b">>>>>>> switchyard 0.2.0"):
            self.assertIn(marker, text)

    def test_install_identical_ordinary_file_is_silent(self) -> None:
        self.make_target()
        self.make_project(files={"switchyard/workflow.txt":
                                 DEFAULT_FILES["switchyard/workflow.txt"]}, version=None)
        result = self.run_update("--install")
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertNotIn(b"workflow.txt", result.stdout)
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(),
                         DEFAULT_FILES["switchyard/workflow.txt"])

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
        self.assertEqual((self.project / "switchyard/workflow.txt").read_bytes(),
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
            ["python3", "../switchyard/switchyard/scripts/update-switchyard.py",
             "--install", "--source", "../switchyard"],
            cwd=self.project, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stdout.decode() + result.stderr.decode())
        self.assertEqual((self.project / VERSION).read_text(), "0.2.0\n")
        self.assertIn(b"added: AGENTS.md", result.stdout)
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), RELEASE_AGENTS)


if __name__ == "__main__":
    unittest.main()
