---
name: work-issues
description: How the coordinator session delivers GitHub issues in this repo. Each issue gets its own worktree, a planner that proposes the OpenSpec change and stops, an implementer on any provider the project lists that applies the reviewed change and commits it, and a reviewer that checks the commit against the change. Use whenever the user asks to work on, implement, or run one or more issues, or a milestone's next steps.
---

# Work issues

You are the coordinator. You run on the main checkout. You never implement an issue yourself. Your work is the judgment and the glue:
- splitting the work,
- writing briefs,
- reviewing plans,
- acting on review verdicts,
- relaying questions to the maintainer,
- merging and cleaning up.

Agents do the planning, the building, and the review of the diff. Scripts do the mechanical steps. Paths below are relative to this skill's folder unless they start with `.claude/`.

## Runner

The runner is how you start a worker in its worktree, prompt it, wait for it, read its report, and end its session. Pick one per session and read its file:
- Inside Herdr (`HERDR_ENV=1`): `runners/herdr.md`. Prefer it. Workers run in panes the maintainer can watch.
- Anywhere else: `runners/headless.md`. Each worker turn is one CLI command.

The steps below say start, prompt, wait, read, and end. The runner file gives the commands.

## Routing

The providers, models, effort, flags, and commands for workers live in `.claude/skills/work-issues/routing.md`. That file is the project's to edit, and its values are examples. Its Workers table is the routing table. Its Providers table holds each provider's commands.

Who decides, in this order:
1. What the maintainer names in the session: a provider, a model, or a command.
2. The row in `routing.md`.
3. Your own choice, when there is no usable row, no Providers row for the provider, or no file. Pick a provider, a model, and the command to run. Tell the maintainer what you chose and why before the worker starts. Do not wait for approval.

When the maintainer names a model, use that provider's row for the role with the model replaced. When the row has no model flag and the maintainer names a model, add the model flag using the syntax in that provider's note in `routing.md`. Otherwise use the provider's own default.

- A row is usable when its provider's CLI is installed and the provider is under the usage threshold. If its first turn fails to start or reach its model, skip that provider for the batch, move to the next usable row, and tell the maintainer which provider failed and the error.
- Planner: use the Planner row for your provider. If there is none, use the first Planner row.
- Implementers: rotate through providers with an Implementer row, in the order they first appear. Leave out a provider whose CLI is not installed.
- The first row for a role and provider is the default. Use a later row only when its Use cell says so or the maintainer names it.
- A row marked `when named` is used only when the maintainer names its provider.
- Skip a provider when more than about 70% of its usage window is used. The provider notes in `routing.md` say how to read each one. Ask the maintainer when a provider has no note or its note says usage cannot be read.
- Say which provider and model each issue got.

The reviewer uses the first Reviewer row whose provider differs from the implementer's. When there is none, or it is not usable, review on the implementer's provider with `SWITCHYARD_SAME_PROVIDER=1` on that `start-worker.sh` command. Tell the maintainer once per batch that the review is not independent, and write "same provider, not independent" in the PR body's Review section. A choice under rule 3 still prefers another provider than the implementer's.

For escalation, use the Implementer row marked `escalation`. Without one, follow the order above.

Each phase starts a fresh session, fix rounds included. Every handoff is a file in the worktree: the brief, the answers, the change, and the review. A worker reads them from disk, not from another session's context or from your summary, so the expensive context is not carried into the cheap phase.

Workers never push. Implementers commit and write `.claude/pr-body.md`, then stop, so nothing reaches the remote before the review passes. `setup-worktree.sh` disables the push URL in each worktree, so a push works only from the main checkout. The coordinator pushes from there and opens the PR.

Escalate a single issue only when the plan review shows judgment the plan cannot capture. To escalate, run that issue's implementer with the `escalation` row's flags, and tell the maintainer you did it.

## Coordinator

The coordinator must be able to read `AGENTS.md` and this skill, run the skill's scripts, write to issue worktrees, and push from the main checkout. It must get explicit maintainer approval before merging. These requirements apply even when the CLI runs commands without permission prompts. Follow the matching coordinator note in `.claude/skills/work-issues/routing.md` for setup, permissions, and waiting behavior.

## Batch state

Issue records live in `.claude/state/<issue>.json` in the main checkout. `setup-worktree.sh`, `start-worker.sh`, and `teardown-worktree.sh` write or remove them. Run `python3 .claude/skills/work-issues/scripts/state.py status` first in a new coordinator session, then read each worker with the runner's Read command. On headless, read the newest log in `<path>/.claude/turns/`.

## Before starting

Run `scripts/preflight.sh <provider>...` first, passing the provider names in `routing.md`. It checks the requirements and says how to fix each missing one. Stop on a non-zero exit and tell the maintainer what is missing. Pass its warnings on.

1. Read the issues and `AGENTS.md`. Check the issues against the code. For each one, write down anything the issue leaves undecided, and ask the maintainer before any agent starts.
2. Split the issues by ownership. Each issue owns folders that no other issue in the batch edits. Issues that touch the same files run one after another, not in parallel. Run first the one whose result the others build on.
3. Make sure the shared services `AGENTS.md` names are up in the main checkout.

## Per issue

1. **Set up.** Run `scripts/setup-worktree.sh <issue> <branch>`. It records the issue and prints the worktree path, the runner's handles, and the isolation values from the project's `hooks/worktree-up.sh`. Keep them for the brief.
2. **Brief.** Copy `brief-template.md` to `<path>/.claude/brief.md` and fill every `{placeholder}`. Under the coordinator notes, put:
   - the decisions already made,
   - what is out of scope and which issue owns it,
   - any known traps.
   `.claude/` is git-ignored apart from agents, skills, and commands.

   Record the owned paths for the scope check: `python3 scripts/state.py set <issue> "owned=<path> <path>"`. Separate them with spaces and end folders with `/`.
3. **Plan.** Start the planner with its routing-table flags from `.claude/skills/work-issues/routing.md`, then prompt it: `Read .claude/skills/work-issues/roles/planner.md, then .claude/brief.md, and plan issue #<issue>.` Include the role path so every provider can read the same instructions.
4. **Review the plan.**
   - Read the change on disk: the proposal, the design, the spec delta, and the tasks. The planner's last message is only its list of questions.
   - Check the change against the code and the specs. Verify any claim it makes about the code or the data before you rely on it.
   - Answer what you can.
   - Bring product decisions to the maintainer: anything that changes behaviour the issue does not settle, or that reaches past the paths the issue owns.
   - Write the answers to `<path>/.claude/answers/plan.md`.
5. **Implement.** End the planner's session. Pick the implementer provider from the routing table in `.claude/skills/work-issues/routing.md` and start it in the same worktree. Then prompt it: `Read .claude/skills/work-issues/roles/implementer.md, then .claude/brief.md and .claude/answers/, and implement the change for issue #<issue>.`
6. **Watch.** Wait for the worker, then read its report. Answer it with a file in `.claude/answers/` and a one-line prompt that points to the file.
7. **Review.** When the implementer reports its commit, end its session. Start the reviewer on another usable provider when available. Otherwise set `SWITCHYARD_SAME_PROVIDER=1` and use the implementer's provider. Pass the selected row's flags from `.claude/skills/work-issues/routing.md`, then prompt it: `Read .claude/skills/work-issues/roles/reviewer.md and follow it for issue #<issue>.` Wait for it, then read the newest file in `<path>/.claude/reviews/`.

## Act on the verdict

The reviewer checks the diff against the change. Read its review, not the diff. Open the diff only to rule on a finding the implementer disputes or a question the reviewer raises.

- **`Verdict: pass`:** open the PR.
- **`Verdict: changes requested`:** end the reviewer's session and start a new implementer session. Prompt it: `Read .claude/skills/work-issues/roles/implementer.md, then .claude/brief.md, .claude/answers/, and the newest file in .claude/reviews/, and fix the findings for issue #<issue>.` Do not restate the findings. Then run step 7 again with a new reviewer session.
- **A second `changes requested`:** stop. Bring the open findings to the maintainer.
- **Questions for the coordinator:** answer what you can in `.claude/answers/`, and bring product decisions to the maintainer. If an answer changes the change, run a fix round.

## Open the PR

After `Verdict: pass`:
1. Run `scripts/check-scope.sh <issue>`. It lists the files the branch changed outside its owned paths. The change's files under `openspec/` are always in scope. Rule on each listed file: accept an appended section in a shared doc, and send anything else back as a fix round.
2. From the main checkout, push with `git push -u origin <branch>`.
3. Fill the Review section of `.claude/pr-body.md` with the reviewer's provider, the verdict, and the number of rounds.
4. Fill the Screenshots section. If your harness can publish a page, as Claude Code's Artifact tool can, publish `<path>/.claude/shots/compare.html` and put the link there. Otherwise write that the comparison page was not published, and give its local path.
5. Run `gh pr create --head <branch> --body-file <path>/.claude/pr-body.md`. Add `--milestone <milestone>` when the brief names one.

## Several PRs

With several PRs in flight, merge every branch into a throwaway worktree off `origin/main`. Resolve the append-only conflicts with `scripts/union-resolve.py`, run every check there, then remove that worktree.

## Merge and clean up

Merge only after the maintainer explicitly approves. This rule applies on every CLI, including those that can run commands without a permission prompt. A CLI prompt is not maintainer approval. Squash-merge one PR with `gh pr merge <pr> --squash`, without `--delete-branch`. Then end its worker's session and run `scripts/teardown-worktree.sh <issue> <branch>`. It runs the project's `hooks/worktree-down.sh`, removes the worktree, deletes the local and remote branch, and removes the record.

For each PR still open:
1. Rebase its branch in its worktree onto `origin/main`.
2. Run `scripts/union-resolve.py` on each conflicted append-only file. In zsh, pass the files as separate arguments, not one variable.
3. Run every check in `AGENTS.md`.
4. From the main checkout, push with `git push --force-with-lease origin <branch>`.
5. Wait for CI, then merge it and tear it down the same way.

## Abandon an issue

When an issue is dropped before its worktree is committed, run `scripts/teardown-worktree.sh --abandon <issue> <branch>`. It prints the uncommitted files and the local-only commits it is about to discard, then removes the worktree, the branch, and the record. Passing `--abandon` is the consent; it never prompts. Ordinary teardown stops instead of removing a dirty worktree.
