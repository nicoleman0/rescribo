# Runner: headless

Use this outside Herdr. It needs only git and the worker CLIs.

`setup-worktree.sh` creates the worktree beside the checkout, in `<repo>.worktrees/<branch>`. A Codex coordinator needs that folder writable: `--add-dir ../<repo>.worktrees`.

Each worker turn is one command, run from the worktree. It blocks until the worker stops, and what it prints last is the worker's report. Later turns resume the same session, so answers keep their context.

| Backend | First turn | Later turns |
|---|---|---|
| Claude | `claude -p --session-id <session> <flags> "<prompt>"` | `claude -p --resume <session> <flags> "<prompt>"` |
| Codex | `codex exec <flags> "<prompt>"` | `codex exec resume --last <flags> "<prompt>"` |
| opencode | `opencode run <flags> --session ses_issue<issue> "<prompt>"` | the same command |

| Verb | How |
|---|---|
| Start and prompt | Run `scripts/start-worker.sh <issue> <role> <backend>`, then use its printed `session` in the first-turn command with the role prompt. |
| Wait | The turn is over when the command exits. Run it in the background when your harness supports that. |
| Read | Send each turn's output to `<path>/.claude/turns/<role>-<n>.log` and read the end of it. |
| End | Nothing to do. The next phase starts a new session, and so does each fix round. |

Codex:
- `codex exec resume` forgets the model, so pass the routing table's `-m` and `-c` flags again.
- It rejects `--approve-for-me`. Pass `-c approvals_reviewer=auto_review` in its place.
- `--last` picks the newest session recorded for the current folder, so run it from the worktree.
