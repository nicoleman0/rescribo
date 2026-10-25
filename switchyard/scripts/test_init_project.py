"""Tests for init-project.py against temporary git repositories."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("init-project.py").resolve()
GUIDE = "docs/WORKFLOW.md"
CHART = "docs/workflow.svg"
DELETED = [
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "docs/switchyard.svg",
    "docs/social-preview.png",
    "docs/pixelart.py",
]
README_CONTENT = """# Switchyard: an agent coordination framework

![A rail yard](docs/switchyard.svg)

[badge](https://github.com)

## The workflow

![A workflow chart](docs/workflow.svg)

Track the roles.

## License

MIT. See [LICENSE](LICENSE).
"""
EXPECTED_GUIDE = """# Switchyard: an agent coordination framework

[badge](https://github.com)

## The workflow

![A workflow chart](workflow.svg)

Track the roles.
"""
TEMPLATE_FILES = {
    "README.md": README_CONTENT.encode(),
    "CHANGELOG.md": b"# Changelog\n\nSwitchyard release notes.\n",
    "CONTRIBUTING.md": b"# Contributing\n\nSwitchyard's guide.\n",
    "LICENSE": b"MIT License\n\nCopyright Switchyard.\n",
    "docs/switchyard.svg": b"<svg></svg>\n",
    "docs/social-preview.png": b"png\n",
    "docs/pixelart.py": b"print('banner')\n",
    CHART: b"<svg></svg>\n",
    "create-switchyard/package.json": b"{}\n",
    "create-switchyard/bin/create-switchyard.mjs": b"// bin\n",
}
PACKAGE = "create-switchyard"


class InitProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="test-init-project-")
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.env = os.environ.copy()
        self.env.update({
            "GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test User", "GIT_COMMITTER_EMAIL": "test@example.com",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        })

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> None:
        result = subprocess.run(["git", *args], cwd=self.project, env=self.env, capture_output=True, text=True)
        if result.returncode:
            self.fail(result.stderr)

    def fresh_project(self) -> None:
        self.write_template()
        self.git("init", "-q")
        self.git("config", "user.name", "Test User")
        self.git("config", "user.email", "test@example.com")
        self.git("add", "-A")
        self.git("commit", "-qm", "template")

    def write_template(self) -> None:
        for name, content in TEMPLATE_FILES.items():
            path = self.project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def run_init(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.project, env=self.env, capture_output=True, text=True)

    def assert_absent_after_init(self, result: subprocess.CompletedProcess) -> None:
        for name in DELETED:
            self.assertFalse((self.project / name).exists(), name)
            self.assertIn(f"deleted   {name}", result.stdout)

    def test_moves_guide_and_deletes_the_list(self):
        self.fresh_project()
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertEqual((self.project / GUIDE).read_text(), EXPECTED_GUIDE)
        self.assertTrue((self.project / CHART).exists())
        self.assert_absent_after_init(result)

        self.assertIn("moved     README.md -> docs/WORKFLOW.md", result.stdout)
        self.assertIn(f"kept      {CHART}", result.stdout)
        self.assertNotIn("skipped", result.stdout)
        self.assertIn("Add your own README.md.", result.stdout)
        self.assertIn("Add your own LICENSE.", result.stdout)
        self.assertIn("Project section of AGENTS.md", result.stdout)
        self.assertIn("no commits", result.stdout)

    def test_deletes_the_package_folder(self):
        self.fresh_project()
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / PACKAGE).exists())
        self.assertIn(f"deleted   {PACKAGE}\n", result.stdout)

    def test_uncommitted_change_under_the_package_keeps_it(self):
        self.fresh_project()
        (self.project / PACKAGE / "package.json").write_text('{"edited": true}\n')
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"skipped   {PACKAGE} (uncommitted changes)", result.stdout)
        self.assertTrue((self.project / PACKAGE / "package.json").exists())

    def test_new_untracked_file_under_the_package_keeps_it(self):
        self.fresh_project()
        (self.project / PACKAGE / "notes.md").write_text("mine\n")
        result = self.run_init()
        self.assertIn(f"skipped   {PACKAGE} (uncommitted changes)", result.stdout)
        self.assertTrue((self.project / PACKAGE / "notes.md").exists())

    def test_ignored_build_output_does_not_block_the_package_delete(self):
        self.write_template()
        (self.project / PACKAGE / ".gitignore").write_text("dist/\n")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "template")
        (self.project / PACKAGE / "dist").mkdir()
        (self.project / PACKAGE / "dist" / "release.bundle").write_bytes(b"x")
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"deleted   {PACKAGE}\n", result.stdout)
        self.assertFalse((self.project / PACKAGE).exists())

    def test_rerun_skips_absent_and_keeps_the_moved_guide(self):
        self.fresh_project()
        self.assertEqual(self.run_init().returncode, 0)
        guide_before = (self.project / GUIDE).read_bytes()
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("moved", result.stdout)
        self.assertNotIn("deleted   ", result.stdout)
        self.assertIn(f"skipped   README.md ({GUIDE} already exists)", result.stdout)
        for name in DELETED:
            self.assertIn(f"skipped   {name} (absent)", result.stdout)
        self.assertIn(f"skipped   {PACKAGE} (absent)", result.stdout)
        self.assertEqual(guide_before, (self.project / GUIDE).read_bytes())

    def test_existing_destination_is_not_overwritten(self):
        self.fresh_project()
        (self.project / "docs").mkdir(exist_ok=True)
        (self.project / GUIDE).write_text("own guide\n")
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"skipped   README.md ({GUIDE} already exists)", result.stdout)
        self.assertEqual((self.project / GUIDE).read_text(), "own guide\n")
        self.assertTrue((self.project / "README.md").exists())

    def test_uncommitted_changes_are_skipped(self):
        self.fresh_project()
        (self.project / "LICENSE").write_text("MIT License\n\nCopyright Switchyard.\n edited\n")
        (self.project / "CONTRIBUTING.md").write_bytes(b"staged edit\n")
        self.git("add", "CONTRIBUTING.md")
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)

        for name in ("LICENSE", "CONTRIBUTING.md"):
            self.assertIn(f"skipped   {name} (uncommitted changes)", result.stdout)
            self.assertTrue((self.project / name).exists(), name)
        self.assertTrue((self.project / GUIDE).exists())
        self.assertIn("moved     README.md -> docs/WORKFLOW.md", result.stdout)
        for name in ("CHANGELOG.md", "docs/switchyard.svg", "docs/social-preview.png", "docs/pixelart.py"):
            self.assertIn(f"deleted   {name}", result.stdout)

    def test_an_uncommitted_guide_is_not_moved(self):
        self.fresh_project()
        edited = "# Switchyard: an agent coordination framework\n\nmy notes\n"
        (self.project / "README.md").write_text(edited)
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped   README.md (uncommitted changes)", result.stdout)
        self.assertFalse((self.project / GUIDE).exists())
        self.assertEqual((self.project / "README.md").read_text(), edited)

    def assert_refused(self, deciding: str) -> None:
        before = {
            str(p.relative_to(self.project)): p.read_bytes()
            for p in self.project.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(self.project).parts
        }
        result = self.run_init()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not a fresh copy", result.stderr)
        self.assertIn(deciding, result.stderr)
        after = {
            str(p.relative_to(self.project)): p.read_bytes()
            for p in self.project.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(self.project).parts
        }
        self.assertEqual(before, after)

    def test_refuses_a_readme_that_is_not_the_guide(self):
        self.fresh_project()
        (self.project / "README.md").write_text("# My project\n")
        self.git("commit", "-qam", "own readme")
        self.assert_refused("README.md")

    def test_refuses_when_the_marker_is_not_on_the_first_line(self):
        self.fresh_project()
        (self.project / "README.md").write_text("\n# Switchyard: an agent coordination framework\n")
        self.git("commit", "-qam", "blank first line")
        self.assert_refused("README.md")

    def test_refuses_with_no_readme_and_no_guide(self):
        self.fresh_project()
        (self.project / "README.md").unlink()
        self.git("commit", "-qam", "no readme")
        self.assert_refused("README.md")

    def test_refuses_with_no_readme_and_a_foreign_guide(self):
        self.fresh_project()
        (self.project / "README.md").unlink()
        (self.project / "docs").mkdir(exist_ok=True)
        (self.project / GUIDE).write_text("# Our workflow\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "foreign guide")
        self.assert_refused(GUIDE)

    def test_a_reworded_tagline_still_passes(self):
        self.fresh_project()
        (self.project / "README.md").write_text("# Switchyard for teams\n\nBody.\n")
        self.git("commit", "-qam", "reworded")
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("moved     README.md -> docs/WORKFLOW.md", result.stdout)

    def test_a_clean_listed_path_is_still_deleted_when_another_is_uncommitted(self):
        # The git-status gate only skips the paths it catches, not the rest.
        self.fresh_project()
        (self.project / "LICENSE").write_bytes(b"MIT License\n\nCopyright Switchyard.\n edited\n")
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped   LICENSE (uncommitted changes)", result.stdout)
        for name in ("CHANGELOG.md", "CONTRIBUTING.md", "docs/switchyard.svg", "docs/social-preview.png", "docs/pixelart.py"):
            self.assertIn(f"deleted   {name}", result.stdout)

    def test_stops_outside_a_git_work_tree_before_any_change(self):
        self.write_template()
        result = self.run_init()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not inside a git work tree", result.stderr)
        for name, content in TEMPLATE_FILES.items():
            self.assertEqual((self.project / name).read_bytes(), content, name)

    def test_stops_without_git_and_without_changes(self):
        self.fresh_project()
        stub = self.root / "bin"
        stub.mkdir()
        env = self.env.copy()
        env["PATH"] = str(stub)
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.project, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("git is required", result.stderr)
        self.assertTrue((self.project / "README.md").exists())
        self.assertTrue((self.project / "LICENSE").exists())


if __name__ == "__main__":
    unittest.main()
