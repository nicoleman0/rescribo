# Tasks

## 1. Shared detail content

- [x] 1.1 In `frontend/src/features/follow-ups/follow-up-detail.tsx`, move the detail query, the loading, not found, access removed, and error states, and `ReadyState` around `FollowUpBody` out of `FollowUpDetailPanel` into a new exported `FollowUpDetailContent({ workspaceId, followUpId, layout })`, with `layout: 'panel' | 'page'`. `FollowUpDetailPanel` keeps its `section aria-label="Follow-up detail"` with `surface-raised` and the back link, and renders `FollowUpDetailContent layout="panel"`. Make no other change in this task; verify every test in `follow-up-detail.test.tsx` passes unchanged with `npm test -- follow-up-detail` from `frontend`.
- [x] 1.2 In the same file, add a `FollowUpLayoutContext` (default `'panel'`) provided by `FollowUpDetailContent`, a `SectionHeading` that renders `h3` in the panel and `h2` on the page, and a section class helper: the panel keeps `rounded-card border border-border p-4`, the page uses `problemCard` imported from `@/features/problems/problem-card`. Use them in `DraftSection`, `QueuedSection`, `SentSection`, `FailedSection`, `UncertainSection`, the draft `MessageSection` branch, `ContactSection`, `RecipientForm`, and `FollowUpHistory` (History drops its hard-coded `h2` and `id`, keeping `aria-labelledby` through `useId`). Do not edit any file under `features/problems/`. Verify with a test that the panel's History heading is level 3.
- [x] 1.3 Make `FollowUpSummary` render the title as `h1` on the page and `h2` in the panel. Make `FollowUpBody` lay out by layout: the panel keeps today's single column with `Separator`s; the page renders the summary full width, then a grid `lg:grid-cols-[minmax(0,1fr)_20rem]` with Message and Customer contact in the first column and Recipient (owners) and History in the second, no `Separator`s, and DOM order header, message, contact, recipient, history. Verify with a `FollowUpDetailContent layout="page"` test that the title is `h1` and section headings are `h2`.

## 2. Panel link and full page route

- [x] 2.1 In `FollowUpDetailPanel`, put the back link and a new "Open full page" link in one header row (`flex items-center justify-between gap-2`). "Open full page" is a ghost small `Button asChild` with `touchTarget` and the lucide `Maximize2` icon (`aria-hidden`), linking to `/follow-ups/${followUpId}/page` plus the current query string. Verify a test in `follow-up-detail.test.tsx` that renders at `/follow-ups/fu-1?bucket=needs_approval&page=2` and finds the link with that `href`.
- [x] 2.2 Add `frontend/src/features/follow-ups/follow-up-detail-page.tsx` exporting `FollowUpDetailPage`: read `followUpId` with `useParams` and the workspace with `useWorkspace`; render `div.animate-page-enter grid max-w-5xl gap-6`, a ghost small "Back to follow-ups" `Link` (`ArrowLeft` icon, `touchTarget`) to `/follow-ups` plus the current query string, and `FollowUpDetailContent layout="page" key={followUpId}`. Verify with a new `follow-up-detail-page.test.tsx`: the follow-up renders with an `h1` title; the back link keeps `?bucket=needs_approval&page=2`; a 404 shows "Follow-up not found" with the back link still present.
- [x] 2.3 In `frontend/src/App.tsx`, add `<Route path="follow-ups/:followUpId/page" element={<FollowUpDetailPage />} />` after the two follow-up routes. Change nothing else in the file. Verify `follow-ups-page.test.tsx` still passes and that `/follow-ups/:id` still renders the list and panel.

## 3. End-to-end and docs

- [x] 3.1 In `frontend/e2e/follow-ups.spec.ts`, add a test: open a follow-up from `/follow-ups?bucket=needs_approval`, choose "Open full page", expect the URL `/follow-ups/<id>/page?bucket=needs_approval`, the title as a level-1 heading and no follow-ups list, record a "Customer contacted" outcome and see it in History, run `axeViolations(page)` and expect `[]`, then choose "Back to follow-ups" and expect `bucket=needs_approval` with the list visible. Add a phone-width check (375px) for no horizontal overflow on the full page. Verify with `RESCRIBO_E2E_API_PORT=8102 RESCRIBO_E2E_FRONTEND_PORT=5102 task e2e`.
- [x] 3.2 Append a "Follow-up page" section to `frontend/DESIGN.md` (do not edit existing text): one detail component in two layouts, the page's two-column split, panel sections bordered inside the raised surface and page sections as resting cards, and heading levels per layout. Verify every name it mentions exists in code.
- [x] 3.3 In `.claude/skills/work-issues/scripts/shots.mjs`, after the `follow-up-detail` shot, click "Open full page", wait for `/follow-ups/[^/]+/page`, and shoot `follow-up-page`. Verify the script writes `follow-up-page-*.png` for all four variants.

## 4. Repository checks

- [x] 4.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `RESCRIBO_E2E_API_PORT=8102 RESCRIBO_E2E_FRONTEND_PORT=5102 task e2e`; verify all pass, including `motion.spec.ts` "follow-up switches reuse the panel slot".
- [x] 4.2 Take after screenshots into `.claude/shots/after`, check the panel and the full page in light and dark at desktop and phone width, and build `.claude/shots/compare.html` with `compare.py`.

## Workflow follow-up

- Sync the delta into `openspec/specs/web-interface/spec.md` and archive this change in the PR that completes issue #102.
