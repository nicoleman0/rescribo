# Tasks

## 1. Tokens

- [x] 1.1 Add the six tone token sets and three elevation tokens to `src/styles/theme.css`, expose them in `@theme inline`, and remove `--linked*` and `--needs-review*`; verify `npm run build` and that `grep -r "linked-foreground\|needs-review" src` finds no class users.

## 2. Status badge

- [x] 2.1 Add `StatusBadge` with the six tones, a hidden dot, and `data-tone`; verify a unit test renders each tone with its label and an `aria-hidden` dot.
- [x] 2.2 Map triage, problem, and needs-review states to tones in `TriageBadge`, `ProblemStateBadge`, and `NeedsReviewBadge`; verify unit tests assert the tone for each state.
- [x] 2.3 Replace follow-up delivery and contact badge classes with tone maps rendered through `StatusBadge` in the list and detail; verify unit tests assert failed delivery is danger and existing follow-up tests pass.
- [x] 2.4 Show the six tones and the elevation levels in the UI gallery; verify the gallery renders in the browser.

## 3. Elevation and wordmark

- [x] 3.1 Move `Card` and the inbox, problems, and follow-ups lists to elevation 1, the report and follow-up detail panels and the auth card to elevation 2, and give `EmptyState` an explicit dashed border; verify in before/after screenshots.
- [x] 3.2 Render the wordmark from `--primary` with a forced-colours fallback and link it to `/inbox` in the sidebar; verify an app-shell test follows the link to the inbox.

## 4. Documentation

- [x] 4.1 Write the Quiet + craft direction, tone table, elevation scale, and wordmark rule into `frontend/DESIGN.md`; verify every token it names exists in `theme.css`.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `task e2e`; verify all pass.
- [x] 5.2 Take before/after Playwright screenshots of the inbox, problem detail, follow-ups, sign-in, and UI gallery in light (and dark, which stays light until #101).

## Workflow follow-up

- Archive this change in the PR that completes issue #110.
- Reference #110 from #101 and #106 to #109.
