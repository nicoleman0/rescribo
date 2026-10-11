import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HOOK_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = HOOK_DIR.parent / "scripts"
sys.path.insert(0, str(HOOK_DIR))
import redis_index


class RedisIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.state = self.root / ".claude" / "state"
        self.state.mkdir(parents=True)
        self.env = {**os.environ, "MAIN_CHECKOUT": str(self.root)}

    def tearDown(self):
        self.temp.cleanup()

    def record(self, issue, **fields):
        path = self.state / f"{issue}.json"
        path.write_text(json.dumps({"issue": str(issue), **fields}))

    def run_index(self, *args, check=False):
        return subprocess.run(
            [sys.executable, str(HOOK_DIR / "redis_index.py"), *map(str, args)],
            cwd=self.root, env=self.env, capture_output=True, text=True, check=check,
        )

    def test_choose_lowest_free_and_full_pool(self):
        self.assertEqual(redis_index.choose(set()), 1)
        self.assertEqual(redis_index.choose({1, 3}), 2)
        with self.assertRaises(ValueError):
            redis_index.choose(set(range(1, 16)))

    def test_claim_skips_records_and_is_idempotent(self):
        self.record(12, redis_index=1)
        self.record(13, redis_index=3)
        self.record(194)
        first = self.run_index("claim", 194)
        second = self.run_index("claim", 194)
        self.assertEqual(first.stdout.strip(), "2")
        self.assertEqual(second.stdout.strip(), "2")
        self.assertEqual(json.loads((self.state / "194.json").read_text())["redis_index"], "2")

    def test_full_pool_names_issues_without_writing(self):
        for index in range(1, 16):
            self.record(200 + index, redis_index=index)
        result = self.run_index("claim", 194)
        self.assertEqual(result.returncode, 1)
        self.assertIn("No Redis index is free", result.stderr)
        self.assertIn("201", result.stderr)
        self.assertFalse((self.state / "194.json").exists())

    def test_bad_and_duplicate_records_name_issue(self):
        self.record(10, redis_index=16)
        result = self.run_index("claim", 194)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Issue 10", result.stderr)
        (self.state / "10.json").unlink()
        self.record(11, redis_index=4)
        self.record(12, redis_index=4)
        result = self.run_index("claim", 194)
        self.assertEqual(result.returncode, 1)
        self.assertIn("issues 11 and 12", result.stderr)

    def test_held_value_and_missing_record_or_field(self):
        self.record(14, redis_index=7)
        self.assertEqual(self.run_index("held", 14).stdout.strip(), "7")
        self.assertEqual(self.run_index("held", 15).stdout, "")
        self.record(15)
        self.assertEqual(self.run_index("held", 15).stdout, "")

    def test_concurrent_claims_are_unique(self):
        for issue in range(15):
            self.record(300 + issue)
        processes = [
            subprocess.Popen(
                [sys.executable, str(HOOK_DIR / "redis_index.py"), "claim", str(300 + issue)],
                cwd=self.root, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for issue in range(15)
        ]
        results = [process.communicate() + (process.returncode,) for process in processes]
        indexes = [int(stdout.strip()) for stdout, stderr, code in results if code == 0]
        self.assertEqual(len(indexes), 15, results)
        self.assertEqual(set(indexes), set(range(1, 16)))
        overflow = self.run_index("claim", 999)
        self.assertEqual(overflow.returncode, 1)

    def test_hooks_write_and_flush_the_recorded_index(self):
        hook_dir = self.root / ".claude" / "skills" / "work-issues" / "hooks"
        hook_dir.mkdir(parents=True)
        for name in ("redis_index.py", "worktree-up.sh", "worktree-down.sh"):
            shutil.copy2(HOOK_DIR / name, hook_dir / name)
        (self.root / ".claude" / "skills" / "work-issues" / "scripts").mkdir(parents=True)
        shutil.copy2(SCRIPTS_DIR / "state.py", self.root / ".claude" / "skills" / "work-issues" / "scripts" / "state.py")
        (self.root / ".env").write_text(
            "RESCRIBO_DATABASE_URL=postgresql://u:p@localhost/db\n"
            "RESCRIBO_REDIS_URL=redis://localhost:6379/0\n"
            "DJANGO_CSRF_TRUSTED_ORIGINS=http://localhost:5173\n"
            "RESCRIBO_PUBLIC_BASE_URL=http://localhost:5173\n"
        )
        worktree = self.root / "worktree"
        worktree.mkdir()
        self.record(194)
        log = self.root / "calls.log"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for executable in ("docker", "task"):
            path = bin_dir / executable
            path.write_text("#!/bin/sh\nprintf '%s\\n' \"$0 $*\" >> \"$CALL_LOG\"\n")
            path.chmod(0o755)
        common = {
            **self.env,
            "ISSUE": "194", "BRANCH": "194-unique-redis-index",
            "WORKTREE": str(worktree), "CALL_LOG": str(log),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
        }
        up = subprocess.run(["bash", str(hook_dir / "worktree-up.sh")], cwd=self.root,
                            env=common, capture_output=True, text=True)
        self.assertEqual(up.returncode, 0, up.stderr)
        self.assertIn("redis_index=1", up.stdout)
        self.assertIn("/1\n", (worktree / ".env").read_text())
        # 194 would have selected 15 under the old modulo rule.
        down = subprocess.run(["bash", str(hook_dir / "worktree-down.sh")], cwd=self.root,
                              env=common, capture_output=True, text=True)
        self.assertEqual(down.returncode, 0, down.stderr)
        self.assertIn("compose exec -T redis redis-cli -n 1 flushdb", log.read_text())

        (worktree / ".env").write_text("RESCRIBO_REDIS_URL=redis://localhost:6379/8\n")
        log.write_text("")
        mismatch = subprocess.run(["bash", str(hook_dir / "worktree-down.sh")], cwd=self.root,
                                  env=common, capture_output=True, text=True)
        self.assertEqual(mismatch.returncode, 1)
        self.assertIn("record holds Redis index 1", mismatch.stderr)
        self.assertIn("state.py set 194 redis_index=8", mismatch.stderr)
        self.assertEqual(log.read_text(), "")

        self.record(194)
        log.write_text("")
        no_index = subprocess.run(["bash", str(hook_dir / "worktree-down.sh")], cwd=self.root,
                                  env=common, capture_output=True, text=True)
        self.assertEqual(no_index.returncode, 0, no_index.stderr)
        calls = log.read_text()
        self.assertIn("dropdb -U", calls)
        self.assertNotIn("redis-cli", calls)
        self.assertIn("no recorded Redis index", no_index.stderr)


if __name__ == "__main__":
    unittest.main()
