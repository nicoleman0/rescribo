# Design

## Context

- `GroupingActions` in `frontend/src/features/inbox/report-actions.tsx` holds `panel: 'link' | 'create' | null`. An open panel replaces the action row. `close(opener)` returns focus to the button that opened it, and `finish()` focuses the Triage heading after a save.
- The third button in the row calls `transition.mutate(linked ? 'unlink' : 'dismiss')` on the first click. The action is derived from the report state at click time.
- `ReportDetailPanel` is keyed by report id, so this state resets when the member opens another report.
- `_report_transition` in `backend/feedback/reports.py` cancels pending notifications on `unlink` only ([ADR 0004](../../../docs/adr/0004-report-notification-cancellation.md)). Only a `new` report can be dismissed, so Dismiss cancels nothing. A `409` returns the current report, and `useReportMutation` writes it to the cache.
- `ConfirmAction` in `frontend/src/features/settings/confirm-action.tsx` is the only confirm in the app. It owns a trigger button, the open state, a typed phrase, and a `useSettingsAction` mutation that posts the phrase. Its box, title, text, and Confirm and Cancel row are plain markup with no tie to settings. It is used for workspace, member, connection, and report deletion. `DeleteReport` renders it in the same report panel as the triage section.
- `Button` carries the 44px phone minimum itself (#178). `ConfirmAction` also sets `min-h-11` on its two buttons at every width.
- There is no dialog or modal primitive in `frontend/src/components/ui/`.

## Goals / Non-Goals

**Goals:**
- One confirm step for Ungroup and Dismiss, built from the same parts as the settings confirm.
- A repeated click or key press on the trigger never confirms.

**Non-Goals:**
- A typed phrase, an undo notice, or a confirm that shows only when a notification exists.
- Move to problem, Move to new problem, Save assignee, and Restore report.
- A dialog primitive.
- Any backend or API change. `ReportDetail` does not say whether an unsent notification exists, and the wording "any unsent employee notification" does not need it.
- Escape to cancel. The link and create panels beside it have no Escape handling, and the settings confirm must not change.

## Decisions

### D1. Inline step in place of the action row, not a dialog
`Panel` gains `'unlink'` and `'dismiss'`. The step replaces the action row, as the link and create panels do.
- It reuses `close(opener)` and `finish()`, so focus handling has one implementation in this file.
- It matches the delete-report confirm lower in the same panel.
- Alternative: a Radix `AlertDialog`. Rejected: it would be the first modal in the app, a new `ui` primitive, and a new elevation use for a minor, reversible action. Pending Q1.

### D2. Extract `ConfirmPanel`; `ConfirmAction` composes it
New `frontend/src/components/confirm/confirm-panel.tsx`. It is the form box, the title, the description, a `children` slot, and the Confirm and Cancel row, moved from `ConfirmAction` with the same classes.

Props: `title`, `description`, `confirmLabel`, `pendingLabel`, `isPending`, `confirmDisabled` (default false), `headingLevel` (3 or 4, default 3), `focusOnOpen` (default false), `onConfirm`, `onCancel`, `children`.

- `ConfirmAction` keeps its trigger, open state, typed phrase, and mutation. It passes the phrase `Field` and its `ErrorState` as `children`, `label` as both `title` and `confirmLabel`, and `confirmation !== phrase` as `confirmDisabled`. Its rendered markup and behaviour do not change, and the settings tests pass unedited.
- The inbox passes an `ActionError` as `children`.
- `headingLevel` exists because the settings title is an `h3` and the triage step sits under the `h3` "Triage", so it is an `h4`.
- The component imports only `Button`. It does not import from `components/forms/` (#146).
- Alternative: reuse `ConfirmAction` as it is. Rejected: it requires a phrase and posts through the settings mutation, so reuse means making both optional, which changes its contract more than extraction does.
- Alternative: a second box in `report-actions.tsx`. Rejected: it copies the markup the brief says not to copy.

### D3. The step keeps the settings look
Destructive border, destructive confirm button, and `min-h-11` buttons, for both actions. A confirm step looks one way in the app, and the same panel already shows that look for Delete report. The buttons are 44px at every width, so the phone minimum holds without a breakpoint.
- Trade-off: the step's buttons are taller than the 32px row buttons on desktop, and Ungroup's confirm button is red although its trigger is outline.

### D4. Focus goes to the step title when it opens
`focusOnOpen` gives the title `tabIndex={-1}` and `outline-none`, and focuses it in an effect on mount. This is the pattern the Triage heading already uses.
- A second Enter does nothing. Tab reaches the confirm button, then Cancel.
- A screen reader reads the question, and the description is next in reading order.
- Settings leaves `focusOnOpen` off, because its phrase field takes focus.
- Cancel calls `close(opener)` with a ref on the Ungroup or Dismiss button. Success calls `finish()`.
- Alternatives: focus Cancel, or focus the confirm button. Pending Q2.

### D5. The step holds the action it was opened for
The confirm button calls `transition.mutate(panel)`. It never reads `linked` again. Today's `linked ? 'unlink' : 'dismiss'` would turn a confirmed Ungroup into a Dismiss if another member ungrouped the report first.

### D6. A confirm step closes when the triage state changes
`GroupingActions` remembers the `triage_state` it last rendered. When it differs and a confirm step is open, it sets `panel` to `null` during render (React's adjust-state-on-prop-change pattern, no effect).
- The step cannot reopen by itself if the report later returns to the old state.
- Link and create panels are left alone, so their drafts survive as they do today.
- A `409` that leaves the state unchanged, such as a reassignment, keeps the step open. Confirming again sends the new `report.version`.

### D7. Errors show inside the step while it is open
- Open step: `ActionError` renders in the `children` slot, titled "The report was not updated". The block under the action row does not render at the same time.
- Closed step: the block under the row renders as today.
- Cancel and opening a step both call `transition.reset()`, so an old failure does not follow the member into or out of a step.
- The dismissed branch titles its error from `transition.variables`: "The report was not restored" only when the failed action was `restore`. Today it uses that title for any failure, which would be wrong after a Dismiss that lost a conflict.

### D8. Wording
| | Ungroup | Dismiss |
| --- | --- | --- |
| Title | Ungroup this report? | Dismiss this report? |
| Description | The report returns to New. Any unsent employee notification for it is cancelled. Sent history is kept. | The report is kept but not grouped or followed up. You can restore it later. |
| Confirm | Ungroup report | Dismiss report |

Pending text is "Saving…", as today. The trigger buttons keep the names "Ungroup" and "Dismiss" and no longer show "Saving…", because nothing is pending while the row shows. The hint under the linked row stays.

### D9. Restore does not ask
Restore is the undo for Dismiss and has no side effect.

## Risks / Trade-offs

- A double click lands its second click where the trigger was. The step starts with a title and description, so the confirm button sits lower than the trigger at 1280px and 375px. The e2e spec checks this with `dblclick`. If a layout puts the confirm or Cancel button under the trigger, stop and ask. Do not add a timer or a disabled delay.
- Playwright matches button names by substring, so `{ name: 'Ungroup' }` also matches "Ungroup report". The two never show together, but clicks on the trigger use `exact: true`.
- The title takes focus without a visible ring, as the Triage heading does.
- The link and create panels do not move focus when they open, so focus drops to the page. That is an existing gap and is not fixed here.
