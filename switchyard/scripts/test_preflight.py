from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("preflight.sh").resolve()
COMPARE = Path(__file__).with_name("compare.py").resolve()
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

    def add_image_stub(self, name, is_im):  # type: (str, bool) -> None
        version = ""
        if name == "convert":
            # convert is only trusted when -version says ImageMagick.
            version = 'if [ "$1" = "-version" ]; then\n' \
                      '  echo "Version: ImageMagick 6.9.12-98 Q16 x86_64"\n' \
                      '  exit 0\n' \
                      'fi\n'
            if not is_im:
                version = 'if [ "$1" = "-version" ]; then\n  echo "not image magick"\n  exit 4\nfi\n'
        # Stubs log the name and create their last argument, so compare.py sees output.
        self.add(name, version + 'echo "$0" >> "$TOOL_LOG"\n'
                                 'for arg in "$@"; do :; done\n'
                                 ': > "$arg"\n')

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
            elif name == "python3":
                self.add(name, 'if [ -n "${CHECK_LOG:-}" ]; then printf "%s\\n" "$@" > "$CHECK_LOG"; fi\n'
                                'printf "%s" "${CHECK_OUTPUT:-}"\n'
                                'exit "${CHECK_STATUS:-0}"\n')
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

    def test_switchyard_release_check_statuses_and_updater_path(self):
        self.add_base("claude", "magick", "herdr")
        log = self.root / "python-args"
        result = self.run_check({"CHECK_LOG": str(log)})
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok       Switchyard release", result.stdout)
        args = log.read_text().splitlines()
        self.assertEqual(args[-1], "--check")
        self.assertEqual(Path(args[0]), SCRIPT.with_name("update-switchyard.py"))

        result = self.run_check({"CHECK_LOG": str(log), "CHECK_STATUS": "3",
                                 "CHECK_OUTPUT": "0.1.0 is behind the newest release, 0.2.0"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Switchyard release: 0.1.0 is behind the newest release, 0.2.0", result.stdout)
        self.assertIn("0 missing", result.stdout)
        self.assertEqual(sum("Switchyard release:" in line for line in result.stdout.splitlines()), 1)

        result = self.run_check({"CHECK_LOG": str(log), "CHECK_STATUS": "4",
                                 "CHECK_OUTPUT": "could not reach source"})
        self.assertNotIn("Switchyard release", result.stdout)
        self.assertNotIn("Switchyard release", result.stderr)

        result = self.run_check({"CHECK_LOG": str(log), "CHECK_STATUS": "2",
                                 "CHECK_OUTPUT": "no VERSION found"})
        self.assertEqual(result.returncode, 0)
        self.assertIn("warn     Switchyard release: could not check. no VERSION found", result.stdout)

    def test_switchyard_release_check_is_skipped_without_python(self):
        self.add_base("claude", "magick", "herdr")
        (self.bin / "python3").unlink()
        result = self.run_check()
        self.assertNotIn("Switchyard release", result.stdout)

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
        self.add_image_stub("convert", True)
        result = self.run_check()
        self.assertNotIn("warn     Image tool:", result.stdout)
        (self.bin / "convert").unlink()
        self.add_image_stub("convert", False)
        result = self.run_check()
        self.assertIn("warn     Image tool:", result.stdout)

    def run_compare(self):
        before = self.root / "before"
        after = self.root / "after"
        for directory in (before, after):
            directory.mkdir(exist_ok=True)
            (directory / "home-desktop.png").touch()
        spec = self.root / "spec.json"
        spec.write_text(json.dumps({
            "before": str(before), "after": str(after), "title": "t",
            "heading": "h", "intro": "i", "meta": "m",
            "screens": [["home-desktop", "", ""]],
        }))
        return subprocess.run(
            [sys.executable, str(COMPARE), str(spec), str(self.root / "out.html")],
            check=False, capture_output=True, text=True,
            env={"PATH": str(self.bin), "TOOL_LOG": str(self.root / "tool.log"), "HOME": str(self.home)},
        )

    def test_compare_and_preflight_agree_on_the_image_tool(self):
        # "convert!" marks a non-ImageMagick convert stub. The table is the
        # only place the two scripts' rule cases live.
        for stubs, expected in (
            ("sips,magick,convert", "sips"),
            ("magick,convert", "magick"),
            ("convert", "convert"),
            ("convert!", ""),
            ("", ""),
        ):
            with self.subTest(stubs=stubs):
                # Reset first, so a failing case leaves no state that breaks the next one.
                for path in self.bin.iterdir():
                    path.unlink()
                for stray in ("tool.log", "out.html", "spec.json"):
                    (self.root / stray).unlink(missing_ok=True)
                self.add_base("claude")
                for name in [s for s in stubs.split(",") if s]:
                    self.add_image_stub(name.rstrip("!"), not name.endswith("!"))
                preflight = self.run_check()
                compare = self.run_compare()
                self.assertEqual(
                    "ok       Image tool" in preflight.stdout, compare.returncode == 0,
                    preflight.stdout + compare.stderr,
                )
                self.assertEqual(expected, self.tool_log_name())

    def tool_log_name(self):  # type: () -> str
        # The agreed tool when exactly one ran, or "" when none did.
        log = self.root / "tool.log"
        if not log.exists():
            return ""
        names = {Path(line).name for line in log.read_text().splitlines()}
        return next(iter(names)) if len(names) == 1 else ""

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
        self.write_agents("Checks: python3 -m unittest discover -s switchyard/scripts -p 'test_*.py'.")
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
