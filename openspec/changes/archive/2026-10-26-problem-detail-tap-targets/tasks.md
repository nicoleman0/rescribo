# Tasks

## 1. Shared class

- [x] 1.1 Add `standaloneLink` to `frontend/src/features/problems/problem-card.ts`, composed from `inline-flex items-center` and `touchTarget` imported from `@/components/layout/touch-target`, with a one-line comment that it is for links not inside a sentence

## 2. Links and summary

- [x] 2.1 `problem-detail-page.tsx`: add `standaloneLink` to the linked report title link in `LinkedReports`, and to the release tag and Fix evidence links in `FixCard`
- [x] 2.2 `github-issue-status.tsx`: add `standaloneLink` to the issue link
- [x] 2.3 `github-issue-create.tsx`: add `standaloneLink` to "Open issue #N" and to the "Open workspace settings" link in `ConnectionGuidance`
- [x] 2.4 `problem-activity.tsx`: add `touchTarget` and `content-center` to the `<summary>`, keeping its `list-item` display so the disclosure triangle stays. Give the revealed report links `standaloneLink` only in the folded list, not in the sentence uses of `reportLink` and `problemLink`
- [x] 2.5 Leave the release picker's "Open settings" link unchanged; it is inside a sentence
- [x] 2.6 Check at 390 px with the dev servers that each changed target measures at least 44 px, the summary keeps its triangle, and at 1280 px the heights match the before shots

## 3. Tests and docs

- [x] 3.1 Add a test to `frontend/e2e/demo.spec.ts`: at 390 px, open "Password reset emails arrive after the link expires"; `expectTouchTarget` each linked report title, the "linked 6 reports" summary, the release link, and the GitHub issue link; open the summary and `expectTouchTarget` each revealed report link; assert no horizontal overflow
- [x] 3.2 Append one bullet under Layout rules in `frontend/DESIGN.md`, after the 44 px line, without rewording existing text: a standalone link (not inside a sentence) uses `touchTarget` with `inline-flex items-center` so the minimum applies; a link inside running text is exempt

## 4. Checks

- [x] 4.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass
- [x] 4.2 Run `RESCRIBO_E2E_API_PORT=8177 RESCRIBO_E2E_FRONTEND_PORT=5177 task e2e`; all pass
- [x] 4.3 Take after screenshots per the brief and build `.switchyard/shots/compare.html`
- [x] 4.4 Run `npx @fission-ai/openspec validate --all --strict`; passes

## Workflow follow-up

- Archive the change in the PR that completes it.
