---
name: work-issues
description: How the coordinator session delivers GitHub issues in this repo. Each issue gets its own Herdr worktree, a Claude planner that proposes the change and stops, and an implementer on Claude, Codex, or opencode that applies the reviewed change and opens the PR. Use whenever the user asks to work on, implement, or run one or more issues, or a milestone's next steps.
---

# Work issues

You are the coordinator. You run on the main checkout. You never implement an issue yourself. Your work is the judgment and the glue:
- splitting the work,
- writing briefs,
- reviewing plans and PRs,
- relaying questions to the maintainer,
- merging and cleaning up.

Agents do the planning and the building. Scripts do the mechanical steps.

## Routing

The coordinator is always Claude Opus 5.5 at high effort, this session. Workers get their role from `roles/planner.md` or `roles/implementer.md`, so every backend follows the same instructions. Each backend's model and effort are set in one place: the Claude profiles in `.claude/agents/`, and the table below for the others.

| Role | Backend | Start command (after `herdr agent start <name> --kind <kind> --pane <pane> --`) |
|---|---|---|
| Planner | Claude, `issue-planner` profile | kind `claude`: `--agent issue-planner --permission-mode auto` |
| Implementer | Claude, `issue-implementer` profile | kind `claude`: `--agent issue-implementer --permission-mode auto` |
| Implementer | Codex, `gpt-6.1-sol`, medium | kind `codex`: `-m gpt-6.1-sol -c model_reasoning_effort=medium --approve-for-me` |
| Implementer | opencode, Kimi K3 | headless, not an agent session: see opencode below |

Planners always run on Claude, because plans need the most judgment. Spread implementers across the three providers to share the usage:
- Use the provider the maintainer names.
- Otherwise rotate Claude, Codex, then opencode. Skip a provider when more than about 70% of its five-hour window is used. Claude's status line shows usage used, and Codex's shows usage left ("5h N% left"). There is no known way to read opencode's usage from a script, so ask the maintainer when in doubt.
- Say which backend each issue got.

opencode's interactive mode ignores model settings and reopens the last model you picked, so the opencode implementer runs headless in its pane. Each turn is one `herdr pane run`, and every turn reuses one session, so answers keep their context:

```
herdr pane run <pane> "clear; opencode run --model opencode-go/kimi-k3 --auto --session ses_issue<issue> '<prompt>'; echo \"OPENCODE-DONE-<issue>-<turn> exit=\$?\""
```

Herdr's agent states do not apply to it. A turn is over when `herdr pane read <pane> --source visible` shows that turn's marker. Use a new `<turn>` number each time, because a reused marker matches the old output.

Codex may open on an update prompt. Dismiss it with `herdr agent send-keys <name> esc`, and tell the maintainer an update is available. Do not update Codex without asking.

Each phase starts a fresh session. The implementer reads the plan from disk, not from the planner's context, so the expensive context is not carried into the cheap phase.

Non-Claude implementers cannot publish artifacts. When the PR is open, publish `<path>/.claude/shots/compare.html` with the Artifact tool and put the link in the PR's Screenshots section.

Escalate a single issue only when the plan review shows judgment the plan cannot capture. To escalate, run that issue's implementer on Claude with `--agent issue-implementer --model opus --effort high`, and tell the maintainer you did it.

## Before starting

1. Read the issues, `AGENTS.md`, and `frontend/DESIGN.md`. Check the issues against the code. For each one, write down anything the issue leaves undecided, and ask the maintainer before any agent starts.
2. Split the issues by ownership. Each issue owns folders that no other issue in the batch edits. Issues that touch the same files run one after another, not in parallel. Run first the one whose result the others build on.
3. Make sure Postgres and Redis are up in the main checkout (`task services`). Make sure this session runs inside Herdr (`HERDR_ENV=1`).

## Per issue

1. **Set up.** Run `.claude/skills/work-issues/scripts/setup-worktree.sh <issue> <branch>`. It prints the path, pane, workspace, ports, database, and Redis index. Keep them for the brief and for teardown.
2. **Brief.** Copy `brief-template.md` to `<path>/.claude/brief.md` and fill every `{placeholder}`. Under the coordinator notes, put:
   - the decisions already made,
   - what is out of scope and which issue owns it,
   - any known traps.
   `.claude/` is git-ignored apart from agents, skills, and commands.
3. **Plan.** Start the planner with its routing-table command, then prompt it: `herdr agent prompt <name>-plan "Read .claude/brief.md and plan issue #<issue>."`
4. **Review the plan.**
   - Check it against the code and the specs. Verify any claim it makes about the backend or the seeded data before you rely on it.
   - Answer what you can.
   - Bring product decisions to the maintainer: anything that changes behaviour the issue does not settle, or that needs backend work.
   - Write the answers to `<path>/.claude/answers/plan.md`.
5. **Implement.** Send `/exit` to the planner. Pick the implementer backend from the routing table and start it in the same pane. Then prompt it: `herdr agent prompt <name>-build "Read .claude/skills/work-issues/roles/implementer.md, then .claude/brief.md and .claude/answers/, and implement the change for issue #<issue>."`. The role path is in the prompt because only Claude loads it from a profile.
6. **Watch.** Run a Monitor that prints agent states only when one becomes `idle`, `done`, `blocked`, or `unknown`. For a headless opencode turn, watch for its marker instead. When an agent stops, read its pane (`herdr agent read <name> --source recent-unwrapped --lines 80`). Answer it with a file in `.claude/answers/` and a one-line prompt that points to the file. Multi-line prompt text does not submit reliably.

## PR review

Before the maintainer sees a PR, check:
- **Scope:** `git diff --stat origin/main...origin/<branch>`. Only owned paths should change, plus appended sections in shared docs.
- **Attribution:** the PR body and commits have no AI attribution and no em-dashes.
- **Code:** check DRY, by looking for knowledge copied from a shared component. Check that removed or reordered actions were intended. Check that the tests cover the change.
- **Screenshots:** the comparison page shows every affected screen in light and dark.

Send fixes back to the implementer as an answers file. With several PRs in flight, merge every branch into a throwaway worktree off `origin/main`. Resolve the doc conflicts with `scripts/union-resolve.py`, run every check and e2e there, then remove that worktree.

## Merge and clean up

Merge only when the maintainer approves. Squash-merge one PR. Then send `/exit` to its agent and run `scripts/teardown-worktree.sh <issue> <branch> <workspace>`.

For each PR still open:
1. Rebase its branch in its worktree onto `origin/main`.
2. Run `scripts/union-resolve.py` on each conflicted doc file. In zsh, pass the files as separate arguments, not one variable.
3. Run validate, lint, typecheck, unit tests, and build.
4. Push with `--force-with-lease`.
5. Wait for CI, then merge it and tear it down the same way.
