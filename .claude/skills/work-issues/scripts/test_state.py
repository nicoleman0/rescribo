#!/usr/bin/env python3
"""Exercise batch-state commands in isolated temporary git repositories."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).parent
SOURCE_SKILL = SCRIPTS.parent


class Harness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.test"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / ".keep").write_text("x")
        subprocess.run(["git", "-C", str(self.repo), "add", ".keep"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True)
        self.origin = self.base / "origin.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.origin)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", str(self.origin)], check=True)
        self.skill = self.repo / ".claude/skills/work-issues"
        shutil.copytree(SOURCE_SKILL, self.skill)
        (self.skill / "roles/planner.md").write_text("role")
        self.up_hook = self.skill / "hooks/worktree-up.sh"
        self.up_hook.write_text("#!/bin/sh\necho hook-output\n[ \"${FAIL_HOOK:-}\" != 1 ]\n")
        self.up_hook.chmod(0o755)
        self.down_hook = self.skill / "hooks/worktree-down.sh"
        self.down_hook.write_text("#!/bin/sh\n[ \"${FAIL_HOOK:-}\" != 1 ]\n")
        self.down_hook.chmod(0o755)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.log = self.base / "calls.jsonl"
        self.stub("gh", 'echo "$*" >> "$CALL_LOG"\n[ "$1 $2" = "pr list" ] && [ "$3" = "--head" ] && [ "$5" = "--state" ] && [ "$6" = all ] && [ "$7" = "--json" ] && [ "$8" = "number,state" ] && [ "$9" = "--limit" ] && [ "${10}" = 1 ] || exit 23\n[ "${FAIL_GH:-}" != 1 ] || exit 2\nprintf \'%s\\n\' "${GH_RESULT:-[]}"')
        self.stub("herdr", 'echo "$*" >> "$CALL_LOG"\n[ "${FAIL_HERDR:-}" != 1 ] || exit 2\nif [ "$1 $2" = "agent list" ] && [ "$#" = 2 ]; then printf \'%s\\n\' "$HERDR_RESULT"; elif [ "$1 $2" = "agent start" ]; then [ "${FAIL_START:-}" != 1 ] || exit 2; [ "$3" = "planner-10" ] || [ "$3" = "planner-8" ] || exit 23; echo "agent start output"; elif [ "$1 $2" = "worktree create" ]; then printf \'%s\\n\' "$HERDR_CREATE_RESULT"; else exit 23; fi')
        self.env = os.environ.copy()
        self.env.update(PATH=f"{self.bin}:{self.env['PATH']}", CALL_LOG=str(self.log), TEST_WORKTREE=str(self.repo))
        self.env["HERDR_RESULT"] = '{"result":{"agents":[]}}'
        self.env["HERDR_CREATE_RESULT"] = '{"result":{"root_pane":{"cwd":"' + str(self.repo) + '","pane_id":"w1:p1","workspace_id":"ws1"}}}'
        self.env.pop("HERDR_ENV", None)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_cmd(self, *args, cwd=None, env=None, bash=False):
        command = [os.environ.get("TEST_BASH", "bash"), *args] if bash else ["python3", str(self.skill / "scripts/state.py"), *args]
        return subprocess.run(command, cwd=cwd or self.repo, env=env or self.env, capture_output=True, text=True)

    def state(self, *args):
        return self.run_cmd(*args)

    def get(self, issue, field):
        return self.state("get", issue, field).stdout.strip()

    def init(self, issue="8", **values):
        self.state("init", issue, *(f"{k}={v}" for k, v in values.items()))

    def script(self, name, *args, env=None):
        return self.run_cmd(str(self.skill / "scripts" / name), *args, env=env, bash=True)

    def record(self, issue="8"):
        return json.loads((self.repo / f".claude/state/{issue}.json").read_text())

    def test_commands_and_validation(self):
        self.init(branch="old")
        self.init(branch="new")
        self.assertEqual(self.get("8", "branch"), "new")
        self.assertEqual(self.state("set", "8", "path=/tmp").returncode, 0)
        self.assertEqual(self.get("8", "branch"), "new")
        for args in [("set", "99", "a=b"), ("get", "8", "missing"), ("init", "x", "a=b")]:
            result = self.state(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.state("init", "8", "empty=")
        self.assertNotEqual(self.state("get", "8", "empty").returncode, 0)
        self.assertEqual(len(self.state("get", "8", "empty").stderr.strip().splitlines()), 1)
        invalid = self.state("set", "8", "issue=9")
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual(len(invalid.stderr.strip().splitlines()), 1)
        self.assertEqual(self.state("rm", "500").returncode, 0)

    def test_record_uses_main_checkout_from_linked_worktree(self):
        branch = self.base / "linked"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-qb", "linked", str(branch)], check=True)
        result = subprocess.run(["python3", str(self.skill / "scripts/state.py"), "init", "42", "x=y"], cwd=branch, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.repo / ".claude/state/42.json").exists())

    def test_status_table_and_live_lookups(self):
        self.init("2", branch="b2", path=str(self.repo), runner="herdr", worker="planner-2", pane="p2", role="planner")
        self.init("10", branch="b10", path=str(self.repo), runner="headless", session="ses_issue10")
        self.env["HERDR_RESULT"] = '{"result":{"agents":[{"name":"planner-2","agent_status":"working"}]}}'
        self.env["GH_RESULT"] = '[{"number":12,"state":"OPEN"}]'
        result = self.state("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(result.stdout.index("2  "), result.stdout.index("10"))
        self.assertIn("working", result.stdout)
        self.assertIn("ses_issue10", result.stdout)
        self.assertIn("#12 open", result.stdout)

    def test_status_agent_ended_and_missing_worktree(self):
        self.init("2", branch="b2", path=str(self.repo), runner="herdr", worker="gone")
        self.init("3", branch="b3", path=str(self.base / "missing"), runner="headless")
        self.env["HERDR_RESULT"] = '{"result":{"agents":[]}}'
        result = self.state("status")
        self.assertIn("ended", result.stdout)
        self.assertIn("no worktree", result.stdout)
        self.assertIn("pr list", self.log.read_text())

    def test_setup_records_before_hook_and_teardown_removes_record(self):
        result = self.script("setup-worktree.sh", "8", "topic")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hook-output", result.stdout)
        self.assertEqual(self.get("8", "runner"), "headless")
        self.assertEqual(Path(self.record()["path"]), (self.base / "repo.worktrees/topic").resolve())
        down = self.script("teardown-worktree.sh", "8", "topic")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertFalse((self.repo / ".claude/state/8.json").exists())

    def test_setup_hook_failure_keeps_record_and_teardown_failure_keeps_record(self):
        env = self.env.copy(); env["FAIL_HOOK"] = "1"
        result = self.script("setup-worktree.sh", "8", "topic", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.get("8", "runner"), "headless")
        down = self.script("teardown-worktree.sh", "8", "topic", env=env)
        self.assertNotEqual(down.returncode, 0)
        self.assertTrue((self.repo / ".claude/state/8.json").exists())

    def test_teardown_without_record_succeeds(self):
        path = self.base / "repo.worktrees/topic"
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-qb", "topic", str(path)], check=True)
        result = self.script("teardown-worktree.sh", "77", "topic")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_herdr_records_pane(self):
        env = self.env.copy(); env["HERDR_ENV"] = "1"
        env["HERDR_CREATE_RESULT"] = '{"result":{"root_pane":{"cwd":"' + str(self.base / "herdr-tree") + '","pane_id":"w9:p2","workspace_id":"ws9"}}}'
        self.stub("herdr", 'echo "$*" >> "$CALL_LOG"\nprintf \'%s\\n\' "$HERDR_CREATE_RESULT"')
        result = self.script("setup-worktree.sh", "8", "topic", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.get("8", "runner"), "herdr")
        self.assertEqual(self.get("8", "pane"), "w9:p2")

    def test_status_empty_and_failed_lookups(self):
        self.assertIn("No issues in flight.", self.state("status").stdout)
        self.assertNotIn("agent list", self.log.read_text() if self.log.exists() else "")
        self.init(branch="b", path=str(self.repo), runner="herdr", worker="x")
        for failing in ("FAIL_GH", "FAIL_HERDR"):
            self.env.pop("FAIL_GH", None)
            self.env.pop("FAIL_HERDR", None)
            self.env[failing] = "1"
            result = self.state("status")
            self.assertEqual(result.returncode, 0)
            self.assertIn("?", result.stdout)
            self.assertTrue(result.stderr.strip())

    def test_start_worker_modes(self):
        self.init(branch="b", path=str(self.repo), runner="headless")
        result = self.script("start-worker.sh", "8", "planner", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        session = self.get("8", "session")
        self.assertEqual(len(session), 36)
        self.assertEqual(session, session.lower())
        self.init("9", branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "9", "planner", "codex").returncode, 0)
        self.assertEqual(self.record("9")["worker"], "")
        self.assertEqual(self.record("9")["session"], "")
        self.init("11", branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "11", "planner", "opencode").returncode, 0)
        self.assertEqual(self.get("11", "session"), "ses_issue11")
        self.init("10", branch="b", path=str(self.repo), runner="herdr", pane="w1:p1")
        herdr_env = self.env.copy(); herdr_env["HERDR_ENV"] = "1"
        result = self.script("start-worker.sh", "10", "planner", "claude", "--", "--agent", "x", env=herdr_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"path={self.repo}", "pane=w1:p1", "name=planner-10"])
        self.assertEqual(self.get("10", "worker"), "planner-10")
        self.assertIn("agent start planner-10 --kind claude --pane w1:p1 -- --agent x", self.log.read_text())
        result = self.script("start-worker.sh", "10", "planner", "opencode", env=herdr_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.get("10", "session"), "ses_issue10")
        self.assertEqual(self.record("10")["worker"], "")
        self.assertEqual(self.record("10")["role"], "planner")
        before = self.record("10")
        fail_env = herdr_env.copy(); fail_env["FAIL_START"] = "1"
        failed = self.script("start-worker.sh", "10", "planner", "claude", env=fail_env)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.record("10"), before)

    def test_start_failures_do_not_mutate(self):
        self.init(branch="b", path=str(self.repo), runner="headless", role="planner", backend="codex", session="old")
        before = self.record()
        for args in [("8", "unknown", "claude"), ("8", "planner", "bad"), ("99", "planner", "claude")]:
            self.assertNotEqual(self.script("start-worker.sh", *args).returncode, 0)
        self.assertEqual(self.record(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
