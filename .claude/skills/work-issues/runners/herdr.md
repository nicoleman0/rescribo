# Runner: Herdr

Use this when the coordinator runs inside Herdr (`HERDR_ENV=1`). Each worker is an interactive agent in its own pane, so the maintainer can watch it and step in.

`setup-worktree.sh` creates the worktree under `~/.herdr/worktrees/<repo>` and prints its `pane` and `workspace`. The coordinator must be able to write to `~/.herdr/worktrees/<repo>`; its setup note is in the Coordinator section of `.claude/skills/work-issues/routing.md`.

| Verb | Command |
|---|---|
| Start an agent | `scripts/start-worker.sh <issue> <role> <provider> -- <flags>` when the provider's On Herdr cell is `agent` |
| Start a turns provider | `scripts/start-worker.sh <issue> <role> <provider> --turns` when its On Herdr cell is `turns` |
| Prompt | `herdr agent prompt <name> "<one line>"` |
| Wait | `scripts/wait-agents.sh <name>...` |
| Read | `herdr agent read <name> --source recent-unwrapped --lines 80` |
| End | Send the provider's End cell to the agent |

Read the provider's commands, flags, and End value from `.claude/skills/work-issues/routing.md`. The script names agents `<role>-<issue>`. A name is free again once its agent has exited, so fix rounds reuse `implementer-<issue>` and `reviewer-<issue>`. Herdr rejects names that start with a digit; names must start with a lowercase letter.

Multi-line prompt text does not submit reliably. Put the content in a file and prompt with one line that points to it.

`wait-agents.sh` returns when a named agent is `idle`, `done`, `blocked`, or `unknown`. Follow the coordinator note in `routing.md` for harness-specific waiting.

## Providers that run as turns

If a provider's On Herdr cell is `turns`, run its First turn or Later turns command from `routing.md` in the pane:

```sh
herdr pane run <pane> "clear; <provider turn command>; echo \"TURN-DONE-<issue>-<turn> exit=\$?\""
```

Use the printed pane and session for each turn. Herdr's agent states do not apply to a turns provider. Use a new `<turn>` number each time, because a reused marker matches the old output. A turn is over when `herdr pane read <pane> --source visible` shows that turn's marker. A provider whose Herdr kind is unsupported by Herdr fails at start; set its On Herdr cell to `turns` in `routing.md`.
