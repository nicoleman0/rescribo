---
name: work-issues
description: How the coordinator session delivers GitHub issues in this repo. Each issue gets its own worktree, a planner that proposes the OpenSpec change and stops, and an implementer on Claude, Codex, or opencode that applies the reviewed change and commits it. Use whenever the user asks to work on, implement, or run one or more issues, or a milestone's next steps.
---

# Work issues

You are the coordinator. You run on the main checkout. You never implement an issue yourself. Your work is the judgment and the glue:
- splitting the work,
- writing briefs,
- reviewing plans and PRs,
- relaying questions to the maintainer,
- merging and cleaning up.

Agents do the planning and the building. Scripts do the mechanical steps. Paths below are relative to this skill's folder unless they start with `.claude/`.

## Runner

The runner is how you start a worker in its worktree, prompt it, wait for it, read its report, and end its session. Pick one per session and read its file:
- Inside Herdr (`HERDR_ENV=1`): `runners/herdr.md`. Prefer it. Workers run in panes the maintainer can watch.
- Anywhere else: `runners/headless.md`. Each worker turn is one CLI command.

The steps below say start, prompt, wait, read, and end. The runner file gives the commands.

## Routing

The maintainer starts the coordinator on the main checkout, on Claude or Codex. Workers get their role from `roles/planner.md` or `roles/implementer.md`, so every backend follows the same instructions. Each backend's model and effort are set in one place: the Claude profiles in `.claude/agents/`, the Codex coordinator profile below, and this table for the others.

| Role | Backend | Flags |
|---|---|---|
| Coordinator | Claude, Opus, high | the maintainer's session; the skill loads by name |
| Coordinator | Codex, `gpt-5.6-sol`, medium | the maintainer runs `codex -p coordinator`; `AGENTS.md` points the session here |
| Planner | Claude, `issue-planner` profile | `--agent issue-planner --permission-mode auto` |
| Planner | Codex, `gpt-5.6-sol`, high | `-m gpt-5.6-sol -c model_reasoning_effort=high --approve-for-me` |
| Implementer | Claude, `issue-implementer` profile | `--agent issue-implementer --permission-mode auto` |
| Implementer | Codex, `gpt-6-luna`, medium | `-m gpt-6-luna -c model_reasoning_effort=medium --approve-for-me` |
| Implementer | opencode, Kimi K3 | `--model opencode-go/kimi-k3 --auto` |

The planner runs on the coordinator's backend. Spread implementers across the providers to share the usage:
- Use the provider the maintainer names.
- Otherwise rotate Claude, Codex, then opencode. Leave out a provider whose CLI is not installed.
- Skip a provider when more than about 70% of its five-hour window is used. Claude's status line shows usage used, and Codex's shows usage left ("5h N% left"). There is no known way to read opencode's usage from a script, so ask the maintainer when in doubt.
- Say which backend each issue got.

Each phase starts a fresh session. The implementer reads the plan from disk, not from the planner's context, so the expensive context is not carried into the cheap phase.

Workers never push. Implementers commit and write `.claude/pr-body.md`, then stop, so nothing reaches the remote before the coordinator has reviewed it. The coordinator pushes and opens the PR.

Escalate a single issue only when the plan review shows judgment the plan cannot capture. To escalate, run that issue's implementer on Claude with `--agent issue-implementer --model opus --effort high`, and tell the maintainer you did it.

## Codex coordinator profile

`codex -p coordinator` layers `~/.codex/coordinator.config.toml` over the user config. The file lives outside the repo, so create it once:

```toml
model = "gpt-5.6-sol"
model_reasoning_effort = "medium"
approvals_reviewer = "user"
```

`approvals_reviewer = "user"` sends approval requests to the maintainer, as Claude's permission prompts do. Without it they go to Codex's automatic reviewer, which decides case by case and has refused pushes. Workers keep `--approve-for-me`.

The Codex sandbox can write the checkout, apart from `.git`, and nothing outside the checkout. Worktrees live outside it, so start Codex with the `--add-dir` the runner file names, which makes them writable for briefs and answers. Request everything else that writes outside the sandbox up front: the two worktree scripts, and git commands that change refs (`push`, `fetch`, `rebase`, `merge`). A sandboxed `git push` still reaches the remote but cannot record the upstream.

At an approval prompt, the maintainer answers "Yes, proceed". "Don't ask again" saves an allow rule under `~/.codex/rules/`, which every Codex session reads, workers included.

## Batch state

Issue records live in `.claude/state/<issue>.json` in the main checkout. `setup-worktree.sh`, `start-worker.sh`, and `teardown-worktree.sh` write or remove them. Run `python3 .claude/skills/work-issues/scripts/state.py status` first in a new coordinator session, then read each worker with the runner's Read command. On headless, read the newest log in `<path>/.claude/turns/`.

## Before starting

1. Read the issues and `AGENTS.md`. Check the issues against the code. For each one, write down anything the issue leaves undecided, and ask the maintainer before any agent starts.
2. Split the issues by ownership. Each issue owns folders that no other issue in the batch edits. Issues that touch the same files run one after another, not in parallel. Run first the one whose result the others build on.
3. Make sure the shared services `AGENTS.md` names are up in the main checkout.

## Per issue

1. **Set up.** Run `scripts/setup-worktree.sh <issue> <branch>`. It records the issue and prints the worktree path, the runner's handles, and the isolation values from the project's `hooks/worktree-up.sh`. Keep them for the brief. On Codex, run it outside the sandbox: a sandbox failure halfway leaves a worktree the script cannot resume.
2. **Brief.** Copy `brief-template.md` to `<path>/.claude/brief.md` and fill every `{placeholder}`. Under the coordinator notes, put:
   - the decisions already made,
   - what is out of scope and which issue owns it,
   - any known traps.
   `.claude/` is git-ignored apart from agents, skills, and commands.
3. **Plan.** Start the planner with its routing-table flags, then prompt it: `Read .claude/skills/work-issues/roles/planner.md, then .claude/brief.md, and plan issue #<issue>.` The role path is in the prompt because only Claude loads it from a profile.
4. **Review the plan.**
   - Check it against the code and the specs. Verify any claim it makes about the code or the data before you rely on it.
   - Answer what you can.
   - Bring product decisions to the maintainer: anything that changes behaviour the issue does not settle, or that reaches past the paths the issue owns.
   - Write the answers to `<path>/.claude/answers/plan.md`.
5. **Implement.** End the planner's session. Pick the implementer backend from the routing table and start it in the same worktree. Then prompt it: `Read .claude/skills/work-issues/roles/implementer.md, then .claude/brief.md and .claude/answers/, and implement the change for issue #<issue>.`
6. **Watch.** Wait for the worker, then read its report. Answer it with a file in `.claude/answers/` and a one-line prompt that points to the file.

## Open the PR

When the implementer reports its commit, check the scope and code below first. Then, from its worktree:
1. Push with `git push -u origin <branch>`. On Codex, request the push outside the sandbox, so the prompt goes to the maintainer.
2. Fill the Screenshots section of `.claude/pr-body.md`. If your harness can publish a page, as Claude Code's Artifact tool can, publish `<path>/.claude/shots/compare.html` and put the link there. Otherwise write that the comparison page was not published, and give its local path.
3. Run `gh pr create --milestone <milestone> --body-file <path>/.claude/pr-body.md`.

## PR review

Before the maintainer sees a PR, check:
- **Scope:** `git diff --stat origin/main...origin/<branch>`. Only owned paths should change, plus appended sections in shared docs.
- **Writing:** the PR body and commits follow the writing rules in `AGENTS.md`.
- **Code:** check DRY, by looking for knowledge copied from a shared component. Check that removed or reordered behaviour was intended. Check that the tests cover the change.
- **Screenshots:** the comparison page shows every affected screen in light and dark. Check the local file when it was not published.

Send fixes back to the implementer as an answers file. With several PRs in flight, merge every branch into a throwaway worktree off `origin/main`. Resolve the append-only conflicts with `scripts/union-resolve.py`, run every check there, then remove that worktree.

## Merge and clean up

Merge only when the maintainer approves. Squash-merge one PR with `gh pr merge <pr> --squash`, without `--delete-branch`. Then end its worker's session and run `scripts/teardown-worktree.sh <issue> <branch>`. It runs the project's `hooks/worktree-down.sh`, removes the worktree, deletes the local and remote branch, and removes the record.

For each PR still open:
1. Rebase its branch in its worktree onto `origin/main`.
2. Run `scripts/union-resolve.py` on each conflicted append-only file. In zsh, pass the files as separate arguments, not one variable.
3. Run every check in `AGENTS.md`.
4. Push with `--force-with-lease`.
5. Wait for CI, then merge it and tear it down the same way.
