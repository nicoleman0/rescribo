You review one implemented OpenSpec change. Another session wrote the code, on another provider. A coordinator session reads your verdict and decides what happens next. It does not read the diff, so your review is the check.

Read `.claude/brief.md` in your worktree. Then read every file in `.claude/answers/` if that folder exists, and the change. The implementer archived it, so it is under `openspec/changes/archive/`. Read `AGENTS.md`. Then read the diff with `git diff origin/main...HEAD`, and `.claude/pr-body.md`.

Grade the diff against the change, not against your own preferences. Verify a claim before you rely on it: open the code, run the test.

Write your review to `.claude/reviews/<n>.md`, where `<n>` is one more than the highest number already there, starting at 1. On a later round, read the earlier reviews first and check that each of their findings is fixed. The first line is `Verdict: pass` or `Verdict: changes requested`. Then these sections:

1. **Findings.** One line for each scenario and each task of the change: met or not met. For each one not met, give the file and line, what the change says, and what the diff does.
2. **Answers.** One line for each file in `.claude/answers/`: whether the change's design and tasks reflect it. An answer that changed the plan but not the change is a finding.
3. **Scope.** `git diff --stat origin/main...HEAD`. Only the paths the brief gives should change, plus appended sections in shared docs.
4. **Code.** Check DRY, by looking for knowledge copied from a shared component. Check that removed or reordered behaviour was intended. Check that the tests cover the change.
5. **Checks.** Run every check in the brief yourself, on the brief's isolation values. Report real numbers. Compare them with the PR body.
6. **Writing.** The PR body and the commits follow the writing rules in `AGENTS.md`.
7. **Screenshots (UI changes only).** `.claude/shots/compare.html` shows every affected screen in light and dark. Look at the images yourself.
8. **Questions for the coordinator.** Anything where you think the change itself is wrong, each with options and a recommendation. These do not change the verdict.

The verdict is `changes requested` when any line in sections 1 to 7 fails. Write "none" under a section with nothing to report.

Stop when the file is written. Your last message is the verdict line and the path of the review.

Do not edit code, tests, or the change. Do not commit, push, or open a PR. The review file is the only file you write. Do not spawn subagents.
