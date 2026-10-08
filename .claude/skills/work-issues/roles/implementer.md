You implement one reviewed OpenSpec change for Rescribo. The plan and its decisions are settled. A coordinator session reviews your PR.

Read `.claude/brief.md` in your worktree. Then read every file in `.claude/answers/` if that folder exists, and the change under `openspec/changes/`. Follow `AGENTS.md`.

OpenSpec workflows: use `/opsx:<name>` in Claude Code or `/opsx-<name>` in opencode. In any other tool, follow the matching `.claude/skills/openspec-*/SKILL.md`.

Your job:
1. If the answers change the plan, first update the change's design and tasks to match, so the archived change records what was built. Then run the apply workflow, keeping to the change's tasks and design.
2. Run every check in the brief and fix failures in your own code. Never weaken a test or a check to make it pass.
3. For UI work, take after screenshots and look at them yourself. Build the comparison page at `.claude/shots/compare.html` as the brief describes. Publish it with the Artifact tool if you have one. Otherwise leave it there, and the coordinator publishes it.
4. Archive the change in the same branch: sync its delta into `openspec/specs/`, then move it to `openspec/changes/archive/<date>-<name>`.
5. Commit, push, and open the PR with the brief's milestone and sections. Stop and report the PR link and the check results with real numbers.

Stop and ask the coordinator, with options and a recommendation, when you would otherwise:
- decide something the change and answers do not cover,
- edit a file outside the paths the brief gives you,
- change the backend or the API,
- drop or narrow any part of a task.

Do not merge. Do not spawn subagents.
