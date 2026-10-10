# Design

## Context

- `ConnectionSettings` (`frontend/src/features/settings/connection-settings.tsx`) renders one card per provider. The check button posts `connections/{provider}/refresh/` with the connection `version` through `action`, a `useSettingsAction` mutation it shares with the channel add and remove buttons.
- `useSettingsAction` invalidates the settings and session queries in `onSettled`. TanStack Query 5 awaits `onSettled` before the mutation leaves `pending`, so the refetched connection is on screen when the mutation reports success or error.
- `refresh_connection` (`backend/connections/services.py`) answers 204 with no body on a pass and sets the connection `active` with a new `last_success_at`. On a provider failure it sets the connection to `error` and answers 400 with a reason. A stale version answers 409. The demo workspace answers 400.
- A failure shows today in up to three places: the "Connection update failed" box at the bottom of the card (shared with channel actions, and below the channel list on the Slack card), the "Connection needs attention" box, and the "Needs attention" badge. The last two reflect the stored connection state.
- `formatDate` shows minutes only. `frontend/src/features/inbox/report-format.ts` is shared and not owned by this change.

## Goals / Non-Goals

**Goals:**
- One place beside the button for the outcome of a check, for both providers.
- A repeated check is visibly distinct.

**Non-Goals:**
- Any backend or API change.
- The "Connection needs attention" box and the status badge. They show connection state and stay as they are.
- Button sizes (#156), field errors (#146), the channel picker (#148).
- Hiding the check button in the demo workspace.

## Decisions

### D1. The check gets its own mutation
`const check = useSettingsAction(workspaceId)` drives the check button. `action` keeps the channel add and remove. A channel save must not read as a passed check, and a check failure must not show in the channel error box.
- Both mutations send `connection.version`, so every button that uses either is disabled while either is pending.
- Alternative: keep one mutation and remember which path ran. Rejected: more state to hold one fact that a second mutation already holds.

### D2. The mutation state is the only source for the outcome
A local `CheckResult` component in `connection-settings.tsx` renders from `check`:
- `isPending`: "Checking {name}…"
- `isSuccess` and `connection.status === 'active'`: "{name} connection is working. Checked at {time}."
- `isError`: "{name} check failed at {time}. {error.message}"
- otherwise nothing.

Success and error are exclusive states of one mutation, so the two results cannot show together, and a new check replaces the old result when it starts. No extra `useState`.
- The `active` guard hides a passed result if a later refetch shows the connection in `error`.

### D3. The time is `check.submittedAt`, shown to the second
The 204 has no body, so the server gives no check time. `submittedAt` is the mutation's own record of when the owner pressed the button.
- Format with a module-level `Intl.DateTimeFormat(undefined, { timeStyle: 'medium' })` in `connection-settings.tsx`, inside `<time dateTime={iso}>`. It has one use, so it does not go into the shared `report-format.ts`.
- Alternative: `connection.last_success_at` with seconds. Rejected: any later successful API call moves it, so "Checked at" would name a time when no check ran.

### D4. Placement and announcement
- Wrap the button and `CheckResult` in `flex flex-wrap items-center gap-x-3 gap-y-2`. The result sits beside the button on desktop and wraps under it on a phone. The button keeps its current classes.
- Pending and passed text render inside a `<p role="status">` that stays mounted while the button shows, so the text change is announced. Class `text-sm`, with the time in `text-muted-foreground`. `empty:hidden` keeps it out of the layout when blank.
- The failure renders as `<p role="alert" className="text-sm text-destructive">` in the same wrapper, the pattern `Field` and `github-issue-create.tsx` use for inline errors.
- No new colour, token, or component. Pending Q1 in the plan summary: plain text (this design) or `StatusBadge`.

### D5. "Connection update failed" covers channel actions only
It keeps rendering `action.error`. A failed check no longer appears there. After a provider failure the card shows the inline failure and the "Connection needs attention" box, where today it shows two boxes.

## Risks / Trade-offs

- `submittedAt` is the press time, not the completion time. A slow check shows a time a few seconds early. The owner reads it as "the check I just ran", which is the point.
- After a provider failure the inline reason and the "Connection needs attention" text can say nearly the same thing. The inline reason is still needed for failures that do not change the connection: a stale version, a network error.
- The e2e case stubs the refresh request. A real check in the e2e workspace would call Slack with the seeded fake credential, fail, set the connection to `error`, and cancel pending notifications that other specs use. Live verification stays with the manual check (#57).
