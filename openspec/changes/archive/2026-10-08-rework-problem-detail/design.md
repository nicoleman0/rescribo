# Design

## Context

`problem-detail-page.tsx` stacks the header, the fix form or confirmed fix, the owner form, the GitHub issue section, linked reports, and activity in one column. Each linked report renders the inbox `Provenance` (a `section aria-label="Provenance"`) and `AssignReportForm` with its helper text. `problem-activity.tsx` prints `changed_fields` values as they come from the API, so `needs_review` shows raw, and `engineering_issue.*` events fall through to "updated the problem".

The activity API returns actor, action, time, report reference, and changed field names per entry. It does not return the reason metadata (for example `issue_closed` or `still_affected_outcome`). That is enough to group links and label fields without an API change.

`needs_review` is cleared only by `confirm_fix`, which runs from `open` or `in_progress`. A `fix_available` problem that needs review has no clearing action yet ([#113](https://github.com/nicoleman0/rescribo/issues/113)).

Inbox components (`AssignReportForm`, `TriageBadge`, `memberName`, `sourceLabel`, `formatDate`, `useMembers`, `useReportMutation`) belong to #107. This change imports them unchanged.

## Goals / Non-Goals

**Goals:**
- One screen height for a problem with six reports on desktop, before activity.
- No duplicate landmarks, so the full axe run passes on problem detail.

**Non-Goals:**
- Motion (#106) and the release link on the fix card (#103).
- Move and ungroup on this page. They stay in the inbox triage panel.
- Grouping across activity pages. Grouping works within the page the API returns.

## Decisions

### Layout

A two-column grid from the `lg` breakpoint: main column for linked reports and activity, a 20rem side column for Fix, GitHub issue, and Owner cards. Below `lg` the side column stacks under the banner, so the fix and owner stay above the report list on phones. Cards and the report list use `shadow-elevation-1`, as resting surfaces. The page widens from `max-w-4xl` to `max-w-5xl` to fit the side column.

The confirm-fix form moves into the Fix card. It keeps its labels and button names, so the existing flow is unchanged.

### Next-step banner

A `ProblemNextStep` component maps state and `needs_review` to a tone, a heading, a sentence, and optional links. It uses the tone background and foreground tokens and a matching lucide icon. It is a plain block with an `h2`, not a landmark or a live region, because it describes the loaded state rather than announcing a change.

| State | needs_review | Tone | Next step |
|---|---|---|---|
| open, in_progress | no | info, progress | Confirm the fix under Fix once it ships |
| open, in_progress | yes | warning | Something changed after the last review; check it, then confirm the fix |
| fix_available | no | success | Follow-ups are prepared; approve them in Follow-ups |
| fix_available | yes | warning | The GitHub issue or a customer outcome changed; check Follow-ups and the issue |
| not_planned | either | neutral | No fix is planned and no follow-ups are prepared |

Because the API does not return why the flag was set, the warning text names both causes. The tone mapping lives next to the existing `problemStateTones`, as DESIGN.md asks.

Alternative considered: a "Mark fix reviewed" button as in the mockup. Rejected until #113 adds the endpoint.

### Edit on demand

Owner and report assignee show as text with a Change button (`aria-expanded`, and an accessible name that includes the report title so rows stay distinguishable). The owner form, owned here, closes and returns focus to Change after a save, and stays open on an error so the pick and the error stay visible. Report assignee uses a small `ReportAssigneeEditor` wrapper in `features/problems/`. It shows the assignee as text, renders the unchanged inbox `AssignReportForm` on Change, and has its own Done button outside that form. Closing is always the member's choice, so a 409 or other error stays visible. `report-actions.tsx` is not modified; #107 is rewriting it. Closing on a server value change was rejected: a 409 also updates the cached report, which would close the form and hide the conflict.

### Compact rows

Each row shows the title link and `TriageBadge` (the spec requires "Linked" on this list), then customer and a one-line source: "Slack message by <author>" or "Manual entry by <submitter>", the same wording `Provenance` uses. The quote, permalink, and retry stay on the report page. "Confirm fix applies" and its note stay on rows where the report's follow-up revision differs from the problem's resolution revision.

### Activity

A pure `groupActivity(entries)` function folds consecutive `report.linked` entries (not moves) by the same actor, each within 10 minutes of the previous one, into one group. A group of two or more renders as "linked N reports" with a native `details` disclosure listing the report links, dated by its newest entry. A single entry renders as today. Unit tests cover grouping boundaries.

Field labels: `title`, `summary`, `owner`, `state` become words; `needs_review` reads "flagged the problem for review"; unknown names have underscores replaced with spaces. Engineering issue events read "linked a GitHub issue", "created a GitHub issue", and "unlinked the GitHub issue".

## Risks / Trade-offs

- [The full source is one click away instead of inline] → The row keeps the source line and links to the report, which shows the captured message.
- [A batch split across two activity pages shows as two groups] → Accepted; pages hold 25 entries and batches are usually smaller.
- [Warning text cannot name the exact cause] → It names both causes and links to both places to check.
