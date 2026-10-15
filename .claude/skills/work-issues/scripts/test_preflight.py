from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("preflight.sh").resolve()
PLACEHOLDER = "Replace this section with your project's rules. Agents read it on every task."


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def add(self, name, body="exit 0\n"):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
        return path

    def run_check(self, extra_env=None, providers=(), cwd=None):
        env = {
            "PATH": str(self.bin),
            "HOME": str(self.home),
            "SHOTS_PACKAGE_DIR": str(self.root),
        }
        if extra_env:
            for key, value in extra_env.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
        return subprocess.run(
            ["/bin/bash", str(SCRIPT), *providers],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=str(cwd or self.root),
        )

    def write_agents(self, project=None):  # type: (str | None) -> None
        section = project or ""
        (self.root / "AGENTS.md").write_text(
            "# Working in this repository\n"
            "\n"
            "## Workflow\n"
            "\n"
            "- Deliver issues through the work-issues skill.\n"
            "\n"
            "## Project\n"
            "\n"
            f"{section}\n\n"
            "## Writing\n"
            "\n"
            "- Use plain, short sentences.\n"
        )

    def add_base(self, *extra):
        for name in ("git", "python3", "node", "npx", "gh", *extra):
            if name == "node":
                self.add(name, 'exit "${NODE_PLAYWRIGHT_STATUS:-0}"\n')
            elif name == "gh":
                self.add(name, 'exit "${GH_AUTH_STATUS:-0}"\n')
            else:
                self.add(name)

    def test_git_passes_and_missing_git_fails(self):
        self.add_base("claude", "magick", "herdr")
        self.add("sips")
        result = self.run_check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok       git", result.stdout)

        (self.bin / "git").unlink()
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("MISSING  git: not installed. Install Git with your system package manager.", result.stdout)

    def test_each_required_tool_has_a_fix_message(self):
        cases = (
            ("python3", "Python 3", "Install Python 3"),
            ("node", "Node.js", "Install Node.js"),
            ("npx", "Node.js", "Install Node.js"),
            ("gh", "GitHub CLI", "cli.github.com"),
        )
        for command, name, fix in cases:
            with self.subTest(command=command):
                self.add_base("claude", "magick", "herdr")
                (self.bin / command).unlink()
                result = self.run_check()
                self.assertEqual(result.returncode, 1)
                line = next(line for line in result.stdout.splitlines() if line.startswith("MISSING") and name in line)
                self.assertIn(fix, line)
                for path in self.bin.iterdir():
                    path.unlink()

    def test_gh_auth_status_and_missing_cli_report_once(self):
        self.add_base("claude", "magick", "herdr")
        self.assertEqual(self.run_check().returncode, 0)
        result = self.run_check({"GH_AUTH_STATUS": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("gh auth login", result.stdout)
        self.assertEqual(sum("GitHub CLI" in line for line in result.stdout.splitlines()), 1)

        (self.bin / "gh").unlink()
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(sum("GitHub CLI" in line for line in result.stdout.splitlines()), 1)

    def test_opencode_coordinator_does_not_need_a_coordinator_cli_check(self):
        self.add_base("opencode", "magick", "herdr")
        result = self.run_check()
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("Coordinator CLI", result.stdout)
        self.assertNotIn("Codex coordinator profile", result.stdout)

    def test_all_required_items_are_reported_and_counted(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        for item in ("git", "Python 3", "Node.js", "GitHub CLI"):
            self.assertTrue(any(line.startswith("MISSING") and item in line for line in result.stdout.splitlines()), item)
        self.assertIn("4 missing,", result.stdout)

    def test_optional_herdr_and_image_tool_warn_without_failing(self):
        self.add_base("claude")
        result = self.run_check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Herdr:", result.stdout)
        self.assertIn("warn     Image tool:", result.stdout)
        for image_tool in ("magick", "sips"):
            with self.subTest(image_tool=image_tool):
                self.add(image_tool)
                result = self.run_check()
                self.assertNotIn("warn     Image tool:", result.stdout)
                (self.bin / image_tool).unlink()

    def test_playwright_probe_and_missing_node_warning(self):
        self.add_base("claude", "magick", "herdr")
        result = self.run_check()
        self.assertIn("ok       Playwright", result.stdout)
        result = self.run_check({"NODE_PLAYWRIGHT_STATUS": "1"})
        self.assertIn("warn     Playwright:", result.stdout)
        (self.bin / "node").unlink()
        result = self.run_check()
        self.assertIn("MISSING  Node.js", result.stdout)
        self.assertIn("warn     Playwright: skipped", result.stdout)
        self.assertEqual(sum(line.startswith("MISSING  Node.js") for line in result.stdout.splitlines()), 1)

    def test_provider_checks_and_second_provider_warning(self):
        self.add_base("claude", "magick", "herdr")
        result = self.run_check(providers=("claude",))
        self.assertIn("ok       Provider claude", result.stdout)
        self.assertIn("warn     Second provider:", result.stdout)
        self.add("codex")
        result = self.run_check(providers=("claude", "codex"))
        self.assertIn("ok       Second provider", result.stdout)
        self.assertNotIn("warn     Second provider:", result.stdout)
        self.assertIn("ok       Provider codex", result.stdout)

    def test_missing_and_unrecognized_providers_are_warnings(self):
        self.add_base("claude", "magick", "herdr")
        result = self.run_check(providers=("claude", "pi", "aider"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Provider pi: not installed.", result.stdout)
        self.assertIn("warn     Provider aider: not installed.", result.stdout)
        self.assertIn("warn     Second provider: only claude is installed. The reviewer runs on the implementer's provider, so the review is not independent.", result.stdout)

    def test_builtin_provider_is_not_installed(self):
        self.add_base("claude", "magick", "herdr")
        result = self.run_check(providers=("eval",))
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Provider eval: not installed.", result.stdout)
        self.assertNotIn("ok       Provider eval", result.stdout)

    def test_no_provider_arguments_warn_without_second_provider_check(self):
        self.add_base("claude")
        result = self.run_check()
        self.assertIn("warn     Worker providers: none named", result.stdout)
        self.assertNotIn("Second provider", result.stdout)

    def test_named_but_uninstalled_providers_warn_and_batch_passes(self):
        self.add_base("claude", "magick", "herdr")
        result = self.run_check(providers=("pi", "aider"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Worker providers: none of the named providers is installed.", result.stdout)

    def test_full_pass_has_no_missing_or_warnings(self):
        self.add_base("claude", "codex", "herdr", "magick")
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("MISSING", result.stdout)
        self.assertFalse(any(line.startswith("warn ") for line in result.stdout.splitlines()))

    def test_placeholder_project_section_warns_but_does_not_fail(self):
        self.add_base("claude", "codex", "magick", "herdr")
        self.write_agents(PLACEHOLDER)
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertIn(
            "warn     AGENTS.md Project section: still the shipped placeholder. Fill it in with your checks, shared services, and conventions; every session reads it.",
            result.stdout,
        )
        self.assertIn("1 warning(s)", result.stdout)

    def test_edited_project_section_does_not_warn(self):
        self.add_base("claude", "codex", "magick", "herdr")
        self.write_agents("Checks: python3 -m unittest discover -s .claude/skills/work-issues/scripts -p 'test_*.py'.")
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("AGENTS.md Project", result.stdout)
        self.assertFalse(any(line.startswith("warn ") for line in result.stdout.splitlines()))

    def test_missing_project_section_and_missing_file_do_not_warn(self):
        self.add_base("claude", "codex", "magick", "herdr")
        self.write_agents()
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any(line.startswith("warn ") for line in result.stdout.splitlines()))

        (self.root / "AGENTS.md").unlink()
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(any(line.startswith("warn ") for line in result.stdout.splitlines()))

    def test_placeholder_outside_the_project_section_does_not_warn(self):
        self.add_base("claude", "codex", "magick", "herdr")
        (self.root / "AGENTS.md").write_text(
            "# Working in this repository\n"
            "\n"
            f"## Workflow\n\n{PLACEHOLDER}\n\n"
            "## Project\n\n"
            "Checks: python3 -m unittest.\n"
            "\n"
            "## Writing\n"
        )
        result = self.run_check(providers=("claude", "codex"))
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("AGENTS.md Project", result.stdout)
        self.assertFalse(any(line.startswith("warn ") for line in result.stdout.splitlines()))


if __name__ == "__main__":
    unittest.main()
