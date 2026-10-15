# Runner: headless

Use this outside Herdr. It needs only git and the worker CLIs.

`setup-worktree.sh` creates the worktree beside the checkout, in `<repo>.worktrees/<branch>`. The coordinator must be able to write to `../<repo>.worktrees`; its setup note is in the Coordinator section of `.claude/skills/work-issues/routing.md`.

Each worker turn is one command, run from the worktree. It blocks until the worker stops, and what it prints last is the worker's report. Later turns resume the same session, so answers keep their context.

Use the First turn or Later turns command from the provider's row in the Providers table of `.claude/skills/work-issues/routing.md`. For every provider, `<flags>` is the Flags cell of the worker's row in the Workers table, `<session>` is the value `start-worker.sh` printed, and `<prompt>` is the role prompt. Run the command from the worktree. If a row has no model flag, the CLI uses its own default unless the maintainer names a model.

| Verb | How |
|---|---|
| Start and prompt | Run `scripts/start-worker.sh <issue> <role> <provider>`, then use its printed `session` in the first-turn command with the role prompt. |
| Wait | The turn is over when the command exits. When the coordinator's harness stops long foreground commands, run the turn in the background and read its log when it exits. Follow the coordinator note in `routing.md` for harness-specific waiting. |
| Read | Create `<path>/.claude/turns/` first. Send each turn's output to `<path>/.claude/turns/<role>-<n>.log` and read the end of it. |
| End | Nothing to do. The next phase starts a new session, and so does each fix round. |
