# Proposal

Delivers GitHub issue #209 (milestone H. Product-grade UI).

## Why

`frontend/src/features/follow-ups/follow-up-detail.tsx` is 1,226 lines and holds 20 components. Its test file is 953 lines. A change to one part means reading all of it. #200 replaces the recipient form next and should touch one small file.

## What Changes

- `follow-up-detail.tsx` is split by concern into eight files under `features/follow-ups/`. Code moves as it is. The only edits are `export` keywords and import lines.
- `follow-up-detail.test.tsx` is split the same way into six test files and one fixtures file. Test bodies move as they are.
- `FollowUpDetailPanel` and `FollowUpDetailContent` keep their names and stay in `follow-up-detail.tsx`.

No behaviour, markup, class, or copy change. No backend, API, dependency, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

Only `frontend/src/features/follow-ups/`.

Source files after the split:

| File | Holds |
| --- | --- |
| `follow-up-detail.tsx` (kept) | `FollowUpDetailPanel`, `FollowUpDetailContent`, `FollowUpBody`, `FollowUpSummary`, `QUEUED_POLL_MS` |
| `follow-up-layout.ts` (new) | `FollowUpLayout`, `FollowUpLayoutContext`, `useSectionClass`, `wrapLongText` |
| `follow-up-section-heading.tsx` (new) | `SectionHeading` |
| `follow-up-message.tsx` (new) | `MessageSection`, `DraftSection`, `QueuedSection`, `SentSection`, `FailedSection`, `UncertainSection` |
| `follow-up-message-editor.tsx` (new) | `MessageEditor`, `ApproveButton`, `MessagePreview` |
| `follow-up-outcome.tsx` (new) | `ContactSection`, `RecordOutcomeForm`, `CorrectionForm`, `choicesFor` |
| `follow-up-recipient-form.tsx` (new) | `RecipientForm` |
| `follow-up-history.tsx` (new) | `FollowUpHistory`, `describeHistory` |

Test files after the split:

| File | Tests |
| --- | --- |
| `follow-up-detail.fixtures.tsx` (new) | shared helpers, no tests |
| `follow-up-detail.test.tsx` (kept) | 4 |
| `follow-up-message.test.tsx` (new) | 6 |
| `follow-up-message-editor.test.tsx` (new) | 5 |
| `follow-up-outcome.test.tsx` (new) | 11 |
| `follow-up-recipient-form.test.tsx` (new) | 4 |
| `follow-up-history.test.tsx` (new) | 2 |

The total stays at 32.
