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

Agents do the planning, the building, and the review of the diff. Scripts do the mechanical steps. Paths below are relative to this skill's folder unless they start with `switchyard/` or a dot.

## Runner

The runner is how you start a worker in its worktree, prompt it, wait for it, read its report, and end its session. Pick one per session and read its file:
- Inside Herdr (`HERDR_ENV=1`): `runners/herdr.md`. Prefer it. Workers run in panes the maintainer can watch.
- Anywhere else: `runners/headless.md`. Each worker turn is one CLI command.

The steps below say start, prompt, wait, read, and end. The runner file gives the commands.

## Routing

The providers, models, effort, flags, and commands for workers live in `switchyard/routing.md`. That file is the project's to edit, and its values are examples. Its Workers table is the routing table. Its Providers table holds each provider's commands.

Who decides, in this order:
1. What the maintainer names in the session: a provider, a model, a size, a row, or a command.
2. The row in `routing.md`.
3. Your own choice, when there is no usable row, no Providers row for the provider, or no file. Pick a provider, a model, and the command to run. Tell the maintainer what you chose and why before the worker starts. Do not wait for approval.

When the maintainer names a model, use the row the issue's size picks for that provider and role, with the model replaced. When the maintainer names a size, it replaces yours. When the maintainer names a row or a command, use it as named. When the row has no model flag and the maintainer names a model, add the model flag using the syntax in that provider's note in `routing.md`. Otherwise use the provider's own default.

- A row is usable when its provider's CLI is installed and the provider is under the usage threshold. If its first turn fails to start or reach its model, skip that provider for the batch, move to the next usable row, and tell the maintainer which provider failed and the error.
- Planner: use the Planner row for your provider. If there is none, use the first Planner row.
- Implementers: rotate through providers with an Implementer row, in the order they first appear. Leave out a provider whose CLI is not installed.
- Once a provider is chosen for a role, the size picks the row (see Size).
- A row marked `when named` is used only when the maintainer names its provider. A Use cell may hold a size and `when named` together, such as `large, when named`.
- Skip a provider when more than about 70% of its usage window is used. The provider notes in `routing.md` say how to read each one. Ask the maintainer when a provider has no note or its note says usage cannot be read.
- At each sizing, say it in one line per issue: the size, and each role's provider, model, and effort from the chosen row. When the second size differs from the first, say both. Do not wait for approval.

The reviewer uses the first Reviewer row whose provider differs from the implementer's. When there is none, or it is not usable, review on the implementer's provider with `SWITCHYARD_SAME_PROVIDER=1` on that `start-worker.sh` command. Tell the maintainer once per batch that the review is not independent, and write "same provider, not independent" in the PR body's Review section. A choice under rule 3 still prefers another provider than the implementer's.

### Size

Size every issue `small`, `medium`, or `large`, twice:
- Before the planner starts, from your read of the issue against the code (Before starting, step 1). The planner uses this size.
- After the plan review, from the reviewed change: its Impact list, tasks, design decisions, and `answers/plan.md`. The implementer, its fix rounds, and the reviewer use this size. A fix round does not re-size.

Criteria:
- `small`: one concern in one place. The issue states the exact result, and the fix follows from reading the code. Examples: a wording or config change, a bug with a known cause in one function. No new interface, data format, or dependency.
- `large`: any one of these:
  - the work spans several components or owned folders;
  - it changes a data format, stored data, a public interface, or anything other code, projects, or users depend on;
  - a mistake could lose data, open a security hole, or break concurrency;
  - the plan leaves judgment the plan cannot capture.
- `medium`: everything else.

Between two sizes, take the larger. An under-powered worker costs a fix round; a larger row costs some usage.

A Workers row names a size in its Use cell. Size picks a whole row, model and effort together, as the project wrote it. Never edit a row's flags to change effort. Once a provider is chosen for a role, take:
1. the first row for that role and provider whose Use cell names the size;
2. otherwise the first row with no size, the default;
3. otherwise, when every row names a size and none matches, the first row for that role and provider. Tell the maintainer.

A Use cell of `escalation`, from an older `routing.md`, counts as `large`. A row names one size; for two sizes, write two rows. A file with no sized rows picks its default row for every size.

Record the sizes and rows with `state.py set`, passing each key as one quoted argument (see Per issue, steps 3, 4, 5, and 7).

Each phase starts a fresh session, fix rounds included. Every handoff is a file in the worktree: the brief, the answers, the change, and the review. A worker reads them from disk, not from another session's context or from your summary, so the expensive context is not carried into the cheap phase.

Workers never push. Implementers commit and write `.switchyard/pr-body.md`, then stop, so nothing reaches the remote before the review passes. `setup-worktree.sh` disables the push URL in each worktree, so a push works only from the main checkout. The coordinator pushes from there and opens the PR.

## Coordinator

The coordinator must be able to read `AGENTS.md` and this skill, run the skill's scripts, write to issue worktrees, and push from the main checkout. It must get explicit maintainer approval before merging. These requirements apply even when the CLI runs commands without permission prompts. Follow the matching coordinator note in `switchyard/routing.md` for setup, permissions, and waiting behavior.

## Batch state

Issue records live in `.switchyard/state/<issue>.json` in the main checkout. `setup-worktree.sh`, `start-worker.sh`, and `teardown-worktree.sh` write or remove them. Run `python3 switchyard/scripts/state.py status` first in a new coordinator session, then read each worker with the runner's Read command. On headless, read the newest log in `<path>/.switchyard/turns/`.

## Before starting

Run `scripts/preflight.sh <provider>...` first, passing the provider names in `routing.md`. It checks the requirements and says how to fix each missing one. Stop on a non-zero exit and tell the maintainer what is missing. Pass its warnings on.

1. Read the issues and `AGENTS.md`. Check the issues against the code. For each one, write down anything the issue leaves undecided, and ask the maintainer before any agent starts.
2. Split the issues by ownership. Each issue owns folders that no other issue in the batch edits. Issues that touch the same files run one after another, not in parallel. Run first the one whose result the others build on.
3. Make sure the shared services `AGENTS.md` names are up in the main checkout.

## Per issue

1. **Set up.** Run `scripts/setup-worktree.sh <issue> <branch>`. It records the issue and prints the worktree path, the runner's handles, and the isolation values from the project's `hooks/worktree-up.sh`. Keep them for the brief.
2. **Brief.** Copy `brief-template.md` to `<path>/.switchyard/brief.md` and fill every `{placeholder}`. Under the coordinator notes, put:
   - the decisions already made,
   - what is out of scope and which issue owns it,
   - any known traps.
   `.switchyard/` holds the ignored runtime files.

   Record the owned paths for the scope check: `python3 scripts/state.py set <issue> "owned=<path> <path>"`. Separate them with spaces and end folders with `/`.
3. **Plan.** Size the issue from your Before starting read. Record it: `python3 scripts/state.py set <issue> plan_size=<size>`. Pick the planner row for that size from `switchyard/routing.md` and record it: `python3 scripts/state.py set <issue> "planner_row=<provider> <flags>"`. Start the planner with those flags, then prompt it: `Read switchyard/roles/planner.md, then .switchyard/brief.md, and plan issue #<issue>.` Include the role path so every provider can read the same instructions.
4. **Review the plan.**
   - Read the change on disk: the proposal, the design, the spec delta, and the tasks. The planner's last message is only its list of questions.
   - Check the change against the code and the specs. Verify any claim it makes about the code or the data before you rely on it.
   - A change with `skip_specs: true` has no spec delta. Check that the planner set the flag only when the work changes no observable behaviour.
   - Answer what you can.
   - Bring product decisions to the maintainer: anything that changes behaviour the issue does not settle, or that reaches past the paths the issue owns.
   - Write the answers to `<path>/.switchyard/answers/plan.md`.
   - Size the reviewed change again and record it: `python3 scripts/state.py set <issue> size=<size>`. Tell the maintainer.
5. **Implement.** End the planner's session. Pick the implementer provider from the routing table in `switchyard/routing.md`, then the row for `size`. Record it: `python3 scripts/state.py set <issue> "implementer_row=<provider> <flags>"`. Start it in the same worktree. Then prompt it: `Read switchyard/roles/implementer.md, then .switchyard/brief.md and .switchyard/answers/, and implement the change for issue #<issue>.`
6. **Watch.** Wait for the worker, then read its report. Answer it with a file in `.switchyard/answers/` and a one-line prompt that points to the file.
7. **Review.** When the implementer reports its commit, end its session. Start the reviewer on another usable provider when available. Otherwise set `SWITCHYARD_SAME_PROVIDER=1` and use the implementer's provider. Pick the row for `size` and pass its flags from `switchyard/routing.md`. Record it: `python3 scripts/state.py set <issue> "reviewer_row=<provider> <flags>"`. Then prompt it: `Read switchyard/roles/reviewer.md and follow it for issue #<issue>.` Wait for it, then read the newest file in `<path>/.switchyard/reviews/`.

## Act on the verdict

The reviewer checks the diff against the change. Read its review, not the diff. Open the diff only to rule on a finding the implementer disputes or a question the reviewer raises.

- **`Verdict: pass`:** open the PR.
- **`Verdict: changes requested`:** end the reviewer's session and start a new implementer session. Prompt it: `Read switchyard/roles/implementer.md, then .switchyard/brief.md, .switchyard/answers/, and the newest file in .switchyard/reviews/, and fix the findings for issue #<issue>.` Do not restate the findings. Pick its row for `size` without re-sizing, and record `implementer_row` again. Then run step 7 again with a new reviewer session.
- **A second `changes requested`:** stop. Bring the open findings to the maintainer.
- **Questions for the coordinator:** answer what you can in `.switchyard/answers/`, and bring product decisions to the maintainer. If an answer changes the change, run a fix round.

## Open the PR

After `Verdict: pass`:
1. Run `scripts/check-scope.sh <issue>`. It lists the files the branch changed outside its owned paths. The change's files under `openspec/` are always in scope. Rule on each listed file: accept an appended section in a shared doc, and send anything else back as a fix round.
2. From the main checkout, push with `git push -u origin <branch>`.
3. Fill the Review section of `.switchyard/pr-body.md` with the reviewer's provider, the verdict, and the number of rounds. Copy the Where to look list from the passing review to the top of the PR body, under a `## Where to look` heading.
4. Fill the Screenshots section. If your harness can publish a page, as Claude Code's Artifact tool can, publish `<path>/.switchyard/shots/compare.html` and put the link there. Otherwise write that the comparison page was not published, and give its local path.
5. Run `gh pr create --head <branch> --body-file <path>/.switchyard/pr-body.md`. Add `--milestone <milestone>` when the brief names one.

## Several PRs

With several PRs in flight, merge every branch into a throwaway worktree off `origin/main`. Resolve the append-only conflicts with `scripts/union-resolve.py`, run every check there, then remove that worktree.

## Merge and clean up

Merge only after the maintainer explicitly approves. This rule applies on every CLI, including those that can run commands without a permission prompt. A CLI prompt is not maintainer approval. Squash-merge one PR with `gh pr merge <pr> --squash`, without `--delete-branch`. Then end its worker's session and run `scripts/teardown-worktree.sh <issue> <branch>`. It runs the project's `hooks/worktree-down.sh`, removes the worktree, deletes the local and remote branch, and removes the record. Teardown skips steps that are already done and still removes the record.

For each PR still open:
1. Rebase its branch in its worktree onto `origin/main`.
2. Run `scripts/union-resolve.py` on each conflicted append-only file. In zsh, pass the files as separate arguments, not one variable.
3. Run every check in `AGENTS.md`.
4. From the main checkout, push with `git push --force-with-lease origin <branch>`.
5. Wait for CI, then merge it and tear it down the same way.

## Abandon an issue

When an issue is dropped before its worktree is committed, run `scripts/teardown-worktree.sh --abandon <issue> <branch>`. It prints the uncommitted files and the local-only commits it is about to discard, then removes the worktree, the branch, and the record. Passing `--abandon` is the consent; it never prompts. Ordinary teardown stops instead of removing a dirty worktree.
