# Design

## Context

Every component in `follow-up-detail.tsx` is private except `FollowUpDetailPanel` and `FollowUpDetailContent`. `follow-ups-page.tsx` and `follow-up-detail-page.tsx` import those two. All 32 tests render one of them through `renderWorkspaceRoutes` and assert on the whole tree.

## Decisions

1. **Imports point one way.** `follow-up-detail` imports the section files. `follow-up-message` imports `follow-up-message-editor`. Every section file imports the layout helpers it uses from `follow-up-layout`, and `follow-up-section-heading` when it needs it. No file imports `follow-up-detail`, so there is no cycle. The editor file imports only `follow-up-layout`: it has no heading.

2. **Shared layout helpers go in two files.** `react/only-export-components` warns when a `.tsx` file exports a component beside a hook or a context. The context, the hook, the type, and `wrapLongText` go in `follow-up-layout.ts`. `SectionHeading` goes in `follow-up-section-heading.tsx`. The feature has no lint warning today and keeps none.

3. **`MessagePreview` lives with the editor.** The editor and three message states use it. The states already import the editor file, so putting it there adds no file and no cycle. It moves again only if a later change needs it elsewhere.

4. **`RecipientForm` gets its own file**, as the maintainer decided. #200 replaces it.

5. **Tests keep rendering the whole detail.** Assertions must not change, so each new test file still renders `FollowUpDetailPanel` or `FollowUpDetailContent` through `routes`. The files are grouped by the concern each test asserts on, not by the component it mounts.

6. **Shared test helpers go in `follow-up-detail.fixtures.tsx`.** It holds `base`, `csrfPath`, `ada`, `grace`, `routes`, `notification`, `detail`, `stubDetail`, and `definitionOf`. The name does not match the Vitest `include` pattern (`src/**/*.test.{ts,tsx}`), so it is not run as a test file. Helpers used by one test file stay in that file: `messageRegion` in the message tests, and `outcomeDetail`, `stubOutcomes`, `outcomeSelect`, `noteBox`, `reasonBox` in the outcome tests.

7. **A test goes where its main assertion is.** Three tests touch two concerns:
   - "shows delivery as not prepared before a message exists" asserts the summary first. It stays in `follow-up-detail.test.tsx`.
   - "uses section-level headings for panel history" goes with the history tests.
   - "labels a delivered message in the demo as simulated" goes with the message tests.

8. **The move is checked by line comparison.** Tasks 3.1 and 3.2 compare the sorted lines of the old files with the new ones. Any line that is not an import must exist on both sides, apart from an added `export`. One exception, decided during implementation: Prettier reflowed two declarations in `follow-up-detail.fixtures.tsx`, `ada` and `detail`, because `export ` pushed them past 80 columns. Task 3.2 names them in its verify text.

## Risks

- A component moved with a missing import fails `tsc`, so the build catches it.
- An import left unused fails `tsc` (`noUnusedLocals`).
- Parallel work on `follow-up-detail.tsx` in another branch will conflict. #200 waits for this change for that reason.

## Out of scope

Improvements to the moved code. The implementer lists these in the PR body and changes none of them:

- `UncertainSection` renders a hidden "Copy the message to send by hand" label that nothing references, and calls `useId` only for it.
- `FollowUpBody` takes `layout` as a prop while its children read the same value from context.
- `FollowUpDetailContent` casts `notification` to `FollowUpNotification` three times.
- The test "shows the queued status and stops polling once sent" does not assert on polling.
- `RecordOutcomeForm` and `CorrectionForm` repeat the note field and its rule.
