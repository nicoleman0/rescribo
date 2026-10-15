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
        (self.skill / "routing.md").write_text("# Routing\n")
        (self.skill / "roles/planner.md").write_text("role")
        self.up_hook = self.skill / "hooks/worktree-up.sh"
        self.up_hook.write_text("#!/bin/sh\necho hook-output\n[ \"${FAIL_HOOK:-}\" != 1 ]\n")
        self.up_hook.chmod(0o755)
        self.down_hook = self.skill / "hooks/worktree-down.sh"
        self.down_hook.write_text("#!/bin/sh\n[ \"${FAIL_HOOK:-}\" != 1 ]\n")
        self.down_hook.chmod(0o755)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for cli in ("claude", "codex", "opencode", "pi"):
            self.stub(cli, "exit 0")
        self.log = self.base / "calls.jsonl"
        self.stub("gh", 'echo "$*" >> "$CALL_LOG"\n[ "$1 $2" = "pr list" ] && [ "$3" = "--head" ] && [ "$5" = "--state" ] && [ "$6" = all ] && [ "$7" = "--json" ] && [ "$8" = "number,state" ] && [ "$9" = "--limit" ] && [ "${10}" = 1 ] || exit 23\n[ "${FAIL_GH:-}" != 1 ] || exit 2\nprintf \'%s\\n\' "${GH_RESULT:-[]}"')
        self.stub("herdr", 'echo "$*" >> "$CALL_LOG"\n[ "${FAIL_HERDR:-}" != 1 ] || exit 2\nif [ "$1 $2" = "agent list" ] && [ "$#" = 2 ]; then printf \'%s\\n\' "$HERDR_RESULT"; elif [ "$1 $2" = "agent start" ]; then [ "${FAIL_START:-}" != 1 ] || exit 2; case "$3" in planner-10|planner-8|implementer-10|reviewer-10) ;; *) exit 23 ;; esac; echo "agent start output"; elif [ "$1 $2" = "worktree create" ]; then printf \'%s\\n\' "$HERDR_CREATE_RESULT"; else exit 23; fi')
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

    def stub_teardown_git(self, branch, on_delete):
        real = shutil.which("git")
        origin = str(self.origin)
        self.stub("git", f'''if [ "$1 $2 $3" = "push origin --delete" ] && [ "$4" = "{branch}" ]; then
  {on_delete}
fi
exec "{real}" "$@"''')

    def test_teardown_tolerates_branch_deleted_between_check_and_push(self):
        self.assertEqual(self.script("setup-worktree.sh", "39", "race").returncode, 0)
        subprocess.run(["git", "-C", str(self.repo), "push", "-q", "origin", "race"], capture_output=True)
        # The wrapper deletes the ref right before its own push --delete runs,
        # so the push is rejected the way the bare repo rejects a missing ref.
        self.stub_teardown_git("race", f'"{shutil.which("git")}" -C "{self.origin}" update-ref -d refs/heads/race')
        down = self.script("teardown-worktree.sh", "39", "race")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertEqual(subprocess.run(["git", "ls-remote", "--heads", str(self.origin), "race"], capture_output=True, text=True).stdout, "")
        self.assertFalse((self.repo / ".claude/state/39.json").exists())

    def test_teardown_reports_failed_remote_delete_and_removes_record(self):
        self.assertEqual(self.script("setup-worktree.sh", "39", "race").returncode, 0)
        subprocess.run(["git", "-C", str(self.repo), "push", "-q", "origin", "race"], capture_output=True)
        self.stub_teardown_git("race", 'echo "push failed" >&2; exit 1')
        down = self.script("teardown-worktree.sh", "39", "race")
        self.assertNotEqual(down.returncode, 0)
        self.assertIn("race", down.stderr)
        self.assertIn("still exists", down.stderr)
        hinted = subprocess.run(["git", "ls-remote", "--heads", str(self.origin), "race"], capture_output=True, text=True).stdout
        self.assertIn("refs/heads/race", hinted)
        self.assertFalse((self.repo / ".claude/state/39.json").exists())

    def make_dirty(self, tree):
        # Modified, staged, and untracked files, as git's plain removal refuses.
        (tree / ".keep").write_text("changed\n")
        (tree / "staged.txt").write_text("x\n")
        (tree / "untracked.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(tree), "add", "staged.txt"], check=True)

    def test_teardown_refuses_dirty_worktree_before_the_hook(self):
        self.down_hook.write_text('#!/bin/sh\necho down >> "$MAIN_CHECKOUT/hook-log"\n')
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.make_dirty(tree)
        down = self.script("teardown-worktree.sh", "8", "topic")
        self.assertNotEqual(down.returncode, 0)
        self.assertIn("--abandon", down.stderr)
        self.assertIn("untracked.txt", down.stderr)
        self.assertIn(" M .keep", down.stderr)
        self.assertTrue((self.repo / ".claude/state/8.json").exists())
        self.assertTrue(tree.exists())
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "topic"], capture_output=True, text=True).stdout.count("topic"), 1)
        self.assertFalse((self.repo / "hook-log").exists())

    def test_teardown_rejects_unknown_options(self):
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.make_dirty(tree)
        down = self.script("teardown-worktree.sh", "--force", "8", "topic")
        self.assertEqual(down.returncode, 2)
        self.assertIn("Usage: teardown-worktree.sh", down.stderr)
        self.assertTrue((self.repo / ".claude/state/8.json").exists())
        self.assertTrue(tree.exists())

    def test_abandon_reports_and_discards_dirty_worktree(self):
        self.down_hook.write_text('#!/bin/sh\necho down >> "$MAIN_CHECKOUT/hook-log"\n')
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.make_dirty(tree)
        draft = subprocess.run(["git", "-C", str(tree), "commit", "-qm", "draft change", "staged.txt"], capture_output=True, text=True)
        self.assertEqual(draft.returncode, 0, draft.stderr)
        down = self.script("teardown-worktree.sh", "--abandon", "8", "topic")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertEqual(down.stderr, "")
        self.assertIn("?? untracked.txt", down.stdout)
        self.assertIn(" M .keep", down.stdout)
        self.assertIn("draft change", down.stdout)
        self.assertTrue((self.repo / "hook-log").exists())
        self.assertFalse((self.repo / ".claude/state/8.json").exists())
        self.assertFalse(tree.exists())
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "topic"], capture_output=True, text=True).stdout, "")
        self.assertEqual(subprocess.run(["git", "ls-remote", "--heads", str(self.origin), "topic"], capture_output=True, text=True).stdout, "")

    def test_abandon_deletes_the_remote_branch(self):
        self.assertEqual(self.script("setup-worktree.sh", "39", "race").returncode, 0)
        subprocess.run(["git", "-C", str(self.repo), "push", "-q", "origin", "race"], capture_output=True)
        down = self.script("teardown-worktree.sh", "--abandon", "39", "race")
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertEqual(subprocess.run(["git", "ls-remote", "--heads", str(self.origin), "race"], capture_output=True, text=True).stdout, "")
        self.assertFalse((self.repo / ".claude/state/39.json").exists())

    def stub_teardown_herdr(self, workspace, tree):
        # Stands in for `herdr worktree remove`, which takes the checkout with
        # it and leaves the local branch for `git branch -D`.
        self.stub("herdr", 'echo "$*" >> "$CALL_LOG"\nif [ "$1 $2" = "worktree list" ]; then printf \'%s\\n\' "$HERDR_LIST_RESULT"\nelif [ "$1 $2" = "worktree remove" ]; then git worktree remove --force "$HERDR_TREE"\nelse exit 23\nfi')
        env = self.env.copy()
        env["HERDR_ENV"] = "1"
        env["HERDR_LIST_RESULT"] = json.dumps({"result": {"worktrees": [{"branch": "topic", "open_workspace_id": workspace}]}})
        env["HERDR_TREE"] = str(tree)
        return env

    def test_abandon_forces_herdr_removal_on_dirty_worktree(self):
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.make_dirty(tree)
        env = self.stub_teardown_herdr("ws-open", tree)
        down = self.script("teardown-worktree.sh", "--abandon", "8", "topic", env=env)
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertIn("worktree remove --workspace ws-open --force", self.log.read_text())
        self.assertFalse(tree.exists())
        self.assertFalse((self.repo / ".claude/state/8.json").exists())
        self.assertEqual(subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "topic"], capture_output=True, text=True).stdout, "")

    def test_plain_teardown_refuses_dirty_herdr_worktree_before_removal(self):
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.make_dirty(tree)
        env = self.stub_teardown_herdr("ws-open", tree)
        down = self.script("teardown-worktree.sh", "8", "topic", env=env)
        self.assertNotEqual(down.returncode, 0)
        self.assertIn("--abandon", down.stderr)
        # The stub logs every herdr call, so nothing means teardown stopped first.
        self.assertNotIn("worktree remove", self.log.read_text() if self.log.exists() else "")
        self.assertTrue((self.repo / ".claude/state/8.json").exists())
        self.assertTrue(tree.exists())



    def test_setup_herdr_records_pane(self):
        env = self.env.copy(); env["HERDR_ENV"] = "1"
        env["HERDR_CREATE_RESULT"] = '{"result":{"root_pane":{"cwd":"' + str(self.base / "herdr-tree") + '","pane_id":"w9:p2","workspace_id":"ws9"}}}'
        self.stub("herdr", 'echo "$*" >> "$CALL_LOG"\nprintf \'%s\\n\' "$HERDR_CREATE_RESULT"')
        # Herdr is stubbed, so make the worktree it would have created.
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-qb", "topic", str(self.base / "herdr-tree")], check=True)
        result = self.script("setup-worktree.sh", "8", "topic", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        pushurl = subprocess.run(["git", "-C", str(self.base / "herdr-tree"), "config", "--worktree", "remote.origin.pushurl"], capture_output=True, text=True)
        self.assertEqual(pushurl.stdout.strip(), "workers-do-not-push")
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
        sessions = []
        for provider in ("claude", "codex", "opencode", "pi"):
            issue = str(8 + len(sessions))
            self.init(issue, branch="b", path=str(self.repo), runner="headless")
            result = self.script("start-worker.sh", issue, "planner", provider)
            self.assertEqual(result.returncode, 0, result.stderr)
            record = self.record(issue)
            self.assertEqual(record["worker"], "")
            self.assertRegex(record["session"], r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
            sessions.append(record["session"])
        self.assertEqual(len(sessions), len(set(sessions)))
        self.init("20", branch="b", path=str(self.repo), runner="headless")
        first = self.script("start-worker.sh", "20", "planner", "pi")
        first_session = self.get("20", "session")
        second = self.script("start-worker.sh", "20", "implementer", "pi")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(first_session, self.get("20", "session"))
        self.init("10", branch="b", path=str(self.repo), runner="herdr", pane="w1:p1")
        herdr_env = self.env.copy(); herdr_env["HERDR_ENV"] = "1"
        result = self.script("start-worker.sh", "10", "planner", "pi", "--", "--agent", "x", env=herdr_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [f"path={self.repo}", "pane=w1:p1", "name=planner-10"])
        self.assertEqual(self.get("10", "worker"), "planner-10")
        self.assertIn("agent start planner-10 --kind pi --pane w1:p1 -- --agent x", self.log.read_text())
        result = self.script("start-worker.sh", "10", "planner", "pi", "--turns", env=herdr_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(self.get("10", "session"), r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
        self.assertEqual(self.record("10")["worker"], "")
        self.assertEqual(self.record("10")["role"], "planner")
        self.assertIn("pane=w1:p1", result.stdout)
        self.assertIn("session=", result.stdout)
        calls = self.log.read_text()
        self.assertEqual(calls.count("agent start"), 1)
        self.init("21", branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "21", "planner", "pi", "--turns").returncode, 0)
        before = self.record("10")
        fail_env = herdr_env.copy(); fail_env["FAIL_START"] = "1"
        failed = self.script("start-worker.sh", "10", "planner", "claude", env=fail_env)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.record("10"), before)

    def test_start_failures_do_not_mutate(self):
        self.init(branch="b", path=str(self.repo), runner="headless", role="planner", backend="codex", session="old")
        before = self.record()
        for args in [("8", "unknown", "claude"), ("8", "planner", "bad"), ("8", "planner", "ClaUde"), ("8", "planner", "foo/bar"), ("8", "planner", "eval"), ("99", "planner", "claude")]:
            result = self.script("start-worker.sh", *args)
            self.assertNotEqual(result.returncode, 0)
            if args[2] != "claude":
                self.assertIn(args[2], result.stderr)
        self.assertEqual(self.record(), before)

    def test_start_without_routing_file_succeeds(self):
        self.init(branch="b", path=str(self.repo), runner="headless", role="planner", backend="codex", session="old")
        (self.skill / "routing.md").unlink()
        result = self.script("start-worker.sh", "8", "planner", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.get("8", "backend"), "claude")

    def test_worktree_cannot_push_and_scope_is_checked(self):
        git = lambda *args, cwd=self.repo: subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
        self.assertEqual(git("push", "-q", "origin", "HEAD:main").returncode, 0)
        git("fetch", "-q", "origin")
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        missing = self.script("check-scope.sh", "8")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("owned", missing.stderr)
        self.state("set", "8", "owned=src/ docs/guide.md")
        for name in ["src/a.py", "docs/guide.md", "openspec/changes/x/tasks.md"]:
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_text("x")
        git("add", "-A", cwd=tree); git("commit", "-qm", "in scope", cwd=tree)
        result = self.script("check-scope.sh", "8")
        self.assertEqual(result.returncode, 0, result.stderr)
        (tree / "README.md").write_text("x"); (tree / "srcs.py").write_text("x")
        git("add", "-A", cwd=tree); git("commit", "-qm", "out of scope", cwd=tree)
        result = self.script("check-scope.sh", "8")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.split(), ["README.md", "srcs.py"])

        blocked = git("push", "origin", "topic", cwd=tree)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("workers-do-not-push", blocked.stderr)
        self.assertEqual(git("ls-remote", "--heads", "origin", "topic").stdout, "")
        self.assertEqual(git("push", "-q", "origin", "topic").returncode, 0)
        self.assertIn("refs/heads/topic", git("ls-remote", "--heads", "origin", "topic").stdout)
        self.assertEqual(self.script("teardown-worktree.sh", "8", "topic").returncode, 0)

    def test_check_scope_reports_all_files_when_owned_is_blank(self):
        bash = "/bin/bash"
        version = subprocess.run([bash, "-c", "echo $BASH_VERSION"], capture_output=True, text=True).stdout.strip()
        if not version.startswith("3."):
            self.skipTest(f"test needs bash 3; /bin/bash is {version or 'unknown'}")
        git = lambda *args, cwd=self.repo: subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
        self.assertEqual(git("push", "-q", "origin", "HEAD:main").returncode, 0)
        git("fetch", "-q", "origin")
        self.assertEqual(self.script("setup-worktree.sh", "8", "topic").returncode, 0)
        tree = Path(self.record()["path"])
        self.state("set", "8", "owned= ")
        (tree / "README.md").write_text("x")
        added = git("add", "-A", cwd=tree)
        committed = git("commit", "-qm", "out of scope", cwd=tree)
        result = subprocess.run([bash, str(self.skill / "scripts/check-scope.sh"), "8"], cwd=self.repo, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout + added.stderr + committed.stderr)
        self.assertEqual(result.stdout.split(), ["README.md"])
        self.assertNotIn("unbound variable", result.stderr)

    def test_reviewer_runs_on_another_provider(self):
        self.init(branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "8", "planner", "claude").returncode, 0)
        before = self.record()
        failed = self.script("start-worker.sh", "8", "reviewer", "codex")
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("no implementer has run", failed.stderr)
        self.assertEqual(self.record(), before)

        self.assertEqual(self.script("start-worker.sh", "8", "implementer", "claude").returncode, 0)
        self.assertEqual(self.get("8", "implementer_backend"), "claude")
        before = self.record()
        for backend, reason in [("claude", "another provider")]:
            failed = self.script("start-worker.sh", "8", "reviewer", backend)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(reason, failed.stderr)
            self.assertEqual(self.record(), before)

        self.assertEqual(self.script("start-worker.sh", "8", "reviewer", "codex").returncode, 0)
        self.assertEqual(self.record()["role"], "reviewer")
        self.assertEqual(self.record()["backend"], "codex")
        self.assertEqual(self.get("8", "implementer_backend"), "claude")
        status = self.state("status")
        self.assertRegex(status.stdout, r"8\s+b\s+reviewer\s+codex")

        same = self.env.copy(); same["SWITCHYARD_SAME_PROVIDER"] = "1"
        result = self.script("start-worker.sh", "8", "reviewer", "claude", env=same)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()["backend"], "claude")
        self.assertEqual(self.script("start-worker.sh", "8", "reviewer", "opencode", env=same).returncode, 0)

    def test_opencode_same_provider_reviewer_needs_override(self):
        self.init(branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "8", "implementer", "opencode").returncode, 0)

        result = self.script("start-worker.sh", "8", "reviewer", "opencode")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("another provider", result.stderr)

        same = self.env.copy()
        same["SWITCHYARD_SAME_PROVIDER"] = "1"
        result = self.script("start-worker.sh", "8", "reviewer", "opencode", env=same)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()["backend"], "opencode")

    def test_opencode_reviewer_after_claude_needs_no_override(self):
        self.init(branch="b", path=str(self.repo), runner="headless")
        self.assertEqual(self.script("start-worker.sh", "8", "implementer", "claude").returncode, 0)

        result = self.script("start-worker.sh", "8", "reviewer", "opencode")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()["backend"], "opencode")

    def test_reviewer_starts_in_herdr_pane(self):
        self.init("10", branch="b", path=str(self.repo), runner="herdr", pane="w1:p1")
        herdr_env = self.env.copy(); herdr_env["HERDR_ENV"] = "1"
        self.assertEqual(self.script("start-worker.sh", "10", "implementer", "codex", env=herdr_env).returncode, 0)
        result = self.script("start-worker.sh", "10", "reviewer", "claude", "--", "--agent", "issue-reviewer", env=herdr_env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.get("10", "worker"), "reviewer-10")
        self.assertIn("agent start reviewer-10 --kind claude --pane w1:p1 -- --agent issue-reviewer", self.log.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
