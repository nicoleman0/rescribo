# Tasks

## 1. Follow-up statuses

- [x] 1.1 Remove `contactStateOrder` and its `void`, and add a "Not prepared" delivery label next to the tone maps in `follow-ups-format.ts`; verify `npm run lint` and `npm run build` pass.
- [x] 1.2 Add `FollowUpStatuses`, a labelled "Delivery" and "Outcome" list, and use it in the follow-up row and the detail header; verify unit tests assert both labels, the "Not prepared" row, and the danger tone on failed delivery, and update the e2e assertion that read "Delivery: Sent".
- [x] 1.3 Lay out the row as title and metadata beside a fixed-width status column on desktop, stacked below `md`; verify in before/after screenshots at 1280px and 390px.
- [x] 1.4 Fold customer, fix, version, destination, and outcome note into one labelled list in the detail header; verify existing detail tests pass and the e2e still finds the customer label.

## 2. Follow-up list controls

- [x] 2.1 Restyle the bucket chips as one segmented control with mono counts and a sideways-scrolling track; verify the page test still selects buckets by `aria-pressed` and the 390px screenshot has no page overflow.
- [x] 2.2 Use the shared `Button` for the previous and next page controls; verify a page test reaches page 2.

## 3. Integration cards

- [x] 3.1 Add `ConnectionStatusBadge` in `connection-status.tsx`, mapping connection states and a missing connection to labels and tones (error is danger); verify a unit test covers all four.
- [x] 3.2 Render each provider in a `Card` with the name, a status badge, the details list, the repository for GitHub, and four labelled job counts, keeping every owner action in place; verify settings tests assert the badge, repository, and counts, and the settings e2e passes.

## 4. Documentation

- [x] 4.1 Append a "Follow-ups and settings" section to `frontend/DESIGN.md` covering labelled statuses and integration cards; verify every class and component it names exists.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `task e2e` on ports 8109 and 5109; verify all pass.
- [x] 5.2 Take after screenshots of follow-ups and settings in light and dark at 1280px and 390px, and build the comparison page.

## Workflow follow-up

- Archive this change in the PR that completes issue #109.
