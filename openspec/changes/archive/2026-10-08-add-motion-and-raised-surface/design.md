# Design

## Context

See proposal.md for why. Current state that shapes the approach:

- `index.css` already imports `tw-animate-css`, whose `enter` keyframes read `--tw-enter-opacity` and `--tw-enter-translate-x/y`. No screen animates today.
- No screen uses `QueryState`. Thirteen feature call sites render `LoadingState` and then their own ready markup.
- `/inbox` and `/inbox/:reportId` render the same `InboxPage`, so the page stays mounted when a report opens. The same holds for follow-ups. `ReportDetailPanel` and `FollowUpDetailPanel` are keyed by item id in the page, so they remount on every switch.
- The report panel is `lg:sticky` and is a direct grid item of an `items-start` grid.
- `Button` has `transition-all` and `active:not-aria-[haspopup]:translate-y-px`. `outline` (52 uses) is the app's secondary action; the `secondary` variant has 2 uses.
- `theme.test.ts` fails if a dark block misses a light token whose value contains `#` or `rgb`.
- In dark, `--muted` is `#1d1d26`, one step from the new raised `#1c1c25`. Ghost-button hover, problem-picker row hover, and the provenance quote fill use `bg-muted` inside raised panels.

## Goals / Non-Goals

**Goals:** one home for every motion value and rule (`theme.css`); motion reaches every screen through shared utilities and components, not per-feature copies; nothing animates under reduced motion.

**Non-Goals:** exit animations (unmounting stays instant), animating the shell, the sidebar, or the auth pages outside the card colour, animating screens outside `src/features/`, and any JS animation library.

## Decisions

### 1. Tokens and named motion utilities in `theme.css`

`:root` gets `--duration-fast: 100ms`, `--duration-base: 160ms`, `--duration-slow: 220ms`, `--ease-out-soft: cubic-bezier(0.2, 0.8, 0.2, 1)`, and `--stagger-step: 22ms`. They are not colours, so they live in `:root` only.

Each motion is one `@utility` in `theme.css`, wrapped in `@media (prefers-reduced-motion: no-preference)` and built on tw-animate's `enter` keyframes with `animation-fill-mode: backwards` (`both` for rows):

| Utility | What | Duration |
| --- | --- | --- |
| `animate-page-enter` | fade, 4px rise | slow |
| `animate-panel-enter` | fade, 12px slide from the end side | slow |
| `animate-content-enter` | fade | base |
| `stagger-rows` (on the `ul`) | each `> li` fades with a 4px rise, delay `min(n - 1, 10) × 22ms` via `:nth-child` | base |
| `transition-status` | `background-color`, `color` | base |
| `press` | `scale: 0.97` on `:active`, transition on scale | fast |

Why: feature code names an intent (`animate-panel-enter`), never a number, and reduced motion is handled once per utility instead of with `motion-safe:` on every call site.

Alternatives: Tailwind arbitrary values at each call site (spreads the numbers); a global `prefers-reduced-motion` rule that zeroes every animation (also stops the retry spinner and hides intent).

### 2. Row stagger with `:nth-child`, not an index prop

`stagger-rows` sets the delay per child position in CSS. A CSS animation runs once when an element is created, so rows kept by React key do not replay on refetch, and only newly inserted rows animate. The cap means rows 11 and later share the 220ms delay; they still animate.

Alternative: pass `index` to each row and set a `--row-index` inline style. It needs the same plumbing in three lists and a typed style cast, for the same result.

### 3. Skeleton to content: a `ReadyState` in the async-states module

Add `ReadyState` to `async-states.tsx`: a `div` that applies `animate-content-enter` and passes through `className` and other div props (`aria-busy`). `QueryState`'s ready branch renders it. Each feature replaces its ready div or fragment with `ReadyState`. Detail bodies keep their article inside it and the problem picker keeps its fieldset. Content uses backwards fill so placeholder opacity remains effective after the fade. It fades in because it mounts when the loading branch unmounts; with `keepPreviousData` it stays mounted across filter and page changes, so those do not replay it.

This is a fade-in of the content as the skeleton leaves, not an overlapping crossfade. A true crossfade keeps the skeleton mounted during an exit animation, which needs exit handling this change does not add.

Call sites: inbox, problems, and follow-ups lists; report and follow-up detail bodies; problem detail and its linked reports and activity; problem picker; settings connections, members, invitations, and Slack account. `require-auth.tsx` and `src/pages/*` are outside the paths this change owns and keep their instant swap.

### 4. Panel slide sits in an unkeyed slot

Each page renders the panel as:

```tsx
{reportId ? (
  <div className="animate-panel-enter lg:sticky lg:top-6">
    <ReportDetailPanel key={reportId} … />
  </div>
) : null}
```

The slot mounts when the selection goes from none to one, so it slides once. Switching items remounts only the keyed panel, whose body fades through `ReadyState` (decision 3). `lg:sticky lg:top-6` moves from the section to the slot, because a sticky child of a same-height wrapper does not stick; `lg:max-h-…` and `lg:overflow-y-auto` stay on the section. The follow-ups page gets the same slot without sticky.

On first open with a cached item, the slot fade and the body fade overlap. Both end at full opacity within 220ms, so the result reads as one fade.

Alternative: move the key inside the panel component. That changes the components' remount contract, which the drafts in `useReportDraft` rely on.

### 5. Page enter on each feature page root

`animate-page-enter` goes on the root `div` of `InboxPage`, `ManualReportPage`, `ProblemsPage`, `ProblemDetailPage`, `FollowUpsPage`, and `SettingsPage`. These roots mount only on a real route change. Keying the shell's `<main>` on pathname would remount the inbox on every selection and lose its state. Moving from one problem to another reuses `ProblemDetailPage` and does not replay; that is acceptable.

### 6. Press feedback becomes a scale

Replace `active:not-aria-[haspopup]:translate-y-px` with the `press` utility (scale 0.97, 100ms), still skipped for `aria-haspopup`. Replace `transition-all` with transitions on colour, border, and shadow at `--duration-fast`, so layout properties never animate. The maintainer's latest issue comment keeps "the press scale". 0.97 is the approved mockup value.

### 7. Raised surface and hairline shadow tokens

- `--raised`: light `#ffffff`, dark `#1c1c25`, exposed as `bg-raised`. The report panel, follow-up panel, and auth card swap `bg-card` for `bg-raised`.
- `--raised-muted`: light `#f4f4f7` (same as `--muted`), dark `#24242e`. A `surface-raised` utility sets `background: var(--raised)` and `--muted: var(--raised-muted)` for its subtree, so ghost hovers, picker hovers, and the quote fill stay one step above the raised surface. `@theme inline` compiles `bg-muted` to `var(--muted)`, so the scoped override reaches them.
- `--shadow-hairline`: light `0 1px 1px rgb(0 0 0 / 0.03)`, dark `0 1px 1px rgb(0 0 0 / 0.5)`, on the `outline` and `secondary` variants. Shadow changes are not motion, so they stay under reduced motion.

All three contain `#` or `rgb`, so the existing theme test enforces the dark block.

### 8. Status badge colour transition

`StatusBadge` and its dot get `transition-status`. Rows are keyed by id, so the same badge element changes tone and the transition plays. `toneSurfaceClasses` stays motion-free because the problem next-step banner shares it.

### 9. Tests and e2e

- Unit: `ReadyState` renders children with `animate-content-enter` and forwards `aria-busy`; `QueryState` ready uses it; `StatusBadge` carries `transition-status`; `Button` carries `press` and no `translate-y-px`; the theme test covers the new colour tokens unchanged.
- E2E (`e2e/motion.spec.ts`): with motion allowed, opening a report gives the slot an `enter` animation; tagging the slot node, opening another report keeps the same slot node while the section is new. Under `reducedMotion: 'reduce'`, the slot, rows, and page root have `animation-name: none` and a pressed button has no scale. In dark, the open report panel's background is `rgb(28, 28, 37)` and the list's is `rgb(23, 23, 31)`, and axe reports no contrast violations with the panel open.
- E2E also checks sticky placement while scrolling a long list, preserved scroll on selection, and press scale and hairline shadows in both gallery themes.
- `e2e/axe.ts` already disables animations. Other specs keep running with motion on; Playwright waits for a stable box before acting. The inbox and UI foundation specs use `test.use({ reducedMotion: 'reduce' })` because their axe scans sampled fading text below the contrast threshold. Other specs keep motion enabled; no sleeps were added.

## Risks / Trade-offs

- [On phones the list is `display: none` while a panel is open; showing it again restarts the row animations] → Accepted. It reads as returning to the list. No extra state to suppress it.
- [Overlapping fades (slot and body, list wrapper and rows) on first appearance] → Same easing and end state, all within 220ms plus stagger. Check in the browser that it reads as one motion.
- [`both` fill keeps rows invisible during the stagger delay] → Max 220ms. Input is not blocked; Playwright waits for stability.
- [`--raised-muted` adds a scoped override, a new pattern] → Confined to one utility in `theme.css` and documented in DESIGN.md.

## Migration Plan

Frontend only. Rollback is reverting the PR.
