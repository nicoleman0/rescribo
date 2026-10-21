# Project routing

This file belongs to the project. The updater adds it when missing and never changes it. Every value here is an example: edit it to choose providers, models, effort, flags, and commands. What the maintainer names in a session wins over this file. Row selection rules are in `SKILL.md`.

A provider is named after its CLI command. To add one, add a Providers row and a Workers row for each role it should run.

## Workers

| Role | Provider | Flags | Use |
|---|---|---|---|
| Planner | claude | `--agent issue-planner --model opus --effort high --permission-mode auto` | |
| Planner | codex | `-m gpt-5.6-sol -c model_reasoning_effort=high --approve-for-me` | |
| Planner | pi | | when named |
| Implementer | claude | `--agent issue-implementer --model sonnet --effort medium --permission-mode auto` | |
| Implementer | claude | `--agent issue-implementer --model opus --effort high --permission-mode auto` | escalation |
| Implementer | codex | `-m gpt-6-luna -c model_reasoning_effort=medium --approve-for-me` | |
| Implementer | opencode | `--model opencode-go/glm-5.3-flash --auto` | |
| Implementer | pi | | when named |
| Reviewer | claude | `--agent issue-reviewer --model opus --effort high --permission-mode auto` | |
| Reviewer | codex | `-m gpt-5.6-sol -c model_reasoning_effort=high --approve-for-me` | |
| Reviewer | pi | | when named |

## Providers

| Provider | On Herdr | End | First turn | Later turns |
|---|---|---|---|---|
| claude | agent | `/exit` | `claude -p --session-id <session> <flags> "<prompt>"` | `claude -p --resume <session> <flags> "<prompt>"` |
| codex | agent | `/exit` | `codex exec <flags> "<prompt>"` | `codex exec resume --last <flags> "<prompt>"` |
| opencode | turns | | `opencode run <flags> --session ses_<session> "<prompt>"` | the same command |
| pi | agent | `/quit` | `pi -p <flags> --session .switchyard/sessions/<session>.jsonl "<prompt>"` | the same command |

The runner files explain these columns and placeholders.

Provider notes:
- claude: the status line shows usage used. Pin a model with `--model <alias or id>`.
- codex: the status line shows usage left ("5h N% left"). Later turns forget the model, so pass the row's flags again, and the pinned model if there is one. `codex exec resume` rejects `--approve-for-me`; pass `-c approvals_reviewer=auto_review` in its place. `--last` picks the newest session for the current folder, so run it from the worktree. Pin a model with `-m <model>`.
- opencode: interactive mode ignores model settings and reopens the last model picked, so it runs as turns on Herdr. Session IDs must start with `ses`. No known way to read usage from a script. Pin a model with `--model <provider/model>`.
- pi: no permission prompts, so no approval flag. `--session` needs a file path; an id pi did not create fails. A model the key cannot reach exits 1 with a 404, so check `pi --list-models` against a real turn. A key with a per-minute token limit below pi's base request fails every turn with a 413, so try a real turn in the repo before relying on a model. No usage window to read. With no `--model`, pi uses the model from its own settings; a project pins one by adding `--model <provider/id>` to the row.
- codex on Herdr: Codex may open on an update prompt. Dismiss it with `herdr agent send-keys <name> esc`, and tell the maintainer an update is available. Do not update Codex without asking.
- codex on Herdr: Codex asks questions in a picker. Open it with `herdr agent send-keys <name> shift+left`, move to "Other" with `down`, type a one-line pointer to the answers file with `herdr pane send-text <pane> "..."`, and submit with `enter`.

## Coordinator

Add a note for every CLI this project uses as a coordinator. Each note states how to start it on the main checkout, what it needs writable, how it asks for approval, and how it waits for a worker.

| Provider | Model | Effort |
|---|---|---|
| claude | `opus` | high |
| codex | | medium |
| opencode | | |

An empty Model cell means the CLI's own default. These values are examples. The maintainer sets them in their own session; each note says how.

Run as coordinator: Claude Code and Codex in regular use, and opencode in the proof for #41 on the headless runner.

### Coordinator notes

- **claude:** Start `claude` from the main checkout, inside Herdr if you use it. Set the values from the `claude` row of the Coordinator table at startup with `claude --model <model> --effort <level>`. The coordinator needs write access to the worktree folder named in the selected runner file. Claude Code permission prompts can request access, but merge only after the maintainer explicitly approves in the coordinator conversation. On headless, run each worker turn in the background with the Bash tool's background mode (`run_in_background`); a foreground command stops after 10 minutes, and Claude Code re-invokes the session when the background command exits. When Claude Code reports that the command exited, read the newest log in `<path>/.switchyard/turns/`. In Herdr, run `scripts/wait-agents.sh` in the background so the session resumes when it returns.
- **codex:** `codex -p coordinator` layers `~/.codex/coordinator.config.toml` over the user config. The file lives outside the repo, so create it once:

  ```toml
  model_reasoning_effort = "<Coordinator table effort>"
  approvals_reviewer = "user"
  ```

  Copy the values from the `codex` row of the Coordinator table in `switchyard/routing.md`. Add `model = "<Coordinator table model>"` only when that Model cell is not empty.

  `approvals_reviewer = "user"` sends approval requests to the maintainer, as Claude's permission prompts do. Without it they go to Codex's automatic reviewer, which decides case by case and has refused pushes. Workers keep `--approve-for-me`.

  The Codex sandbox can write the checkout, apart from `.git`, and nothing outside the checkout. Worktrees live outside it, so start Codex with the `--add-dir` the runner file names, which makes them writable for briefs and answers. Request everything else that writes outside the sandbox up front: the two worktree scripts, and git commands that change refs (`push`, `fetch`, `rebase`, `merge`). A sandboxed `git push` still reaches the remote but cannot record the upstream.

  At an approval prompt, the maintainer answers "Yes, proceed". "Don't ask again" saves an allow rule under `~/.codex/rules/`, which every Codex session reads, workers included. This setting does not replace explicit maintainer approval before a merge.

  Start Codex on the main checkout with `codex -p coordinator --add-dir <worktrees folder>`; the runner file names the folder.

  Run preflight outside the sandbox because it calls GitHub. Run `setup-worktree.sh` outside the sandbox because a failure halfway through leaves a worktree the script cannot resume. On headless, wait for the worker command to exit. In Herdr, run `scripts/wait-agents.sh` and wait for it to return.
- **opencode:** Start `opencode` from the main checkout for an interactive session, or use `opencode run --auto "<request>"` for one request. The coordinator needs write access to the worktree folder named in the selected runner file. In the proof for #41, `--auto` ran every command without asking, so the merge rule in `SKILL.md` is the only gate: merge only after the maintainer explicitly approves in the coordinator conversation. That proof session set up the worktree, wrote the brief, and started the planner, so with `--auto` the worktrees needed no extra setup. On the headless runner, a worker turn is a blocking command and the session waited for it to exit. Not tried: opencode as coordinator inside Herdr. Not tried: a session without `--auto`; opencode requires the `external_directory` permission for paths outside its working directory, and the worktrees are outside the main checkout. Interactive opencode reopens the last model picked, so the empty Model cell means that model.
