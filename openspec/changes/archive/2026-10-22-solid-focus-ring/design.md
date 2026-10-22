## Context

See proposal.md for the problem. Facts that shape the approach, checked in the running app at `/sign-in`:

- `index.css` has an unlayered rule: `button:focus-visible, a:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px }`. Tailwind v4 puts utilities in a cascade layer, and unlayered CSS beats every layer. So the `outline-none` on `button.tsx` loses, and a focused button draws the outline, a `border-ring` border, and the 3px halo.
- `--ring` equals `--primary`. The contrast check already holds `--primary` to 4.5:1 on every surface, but holds `--ring` to 3:1 only on `--background`, `--card`, and `--raised`.
- Some focus targets sit in clipping containers. Status chips sit in an `overflow-x-auto` group with 2px padding, so anything drawn outside a chip is cut. List rows already use `ring-inset`.
- Existing solid indicators are 2px: the global rule, the skip link (`ring-2`), `<main>` (`ring-2`), inline links (`outline-2`), and sidebar items (`ring-2 ring-sidebar-ring`).

## Goals / Non-Goals

**Goals:**
- One focus indicator per element, drawn in `--ring` at full opacity.
- One definition of that indicator, used by the global rule and by components.

**Non-Goals:**
- The `aria-invalid` destructive ring (`ring-destructive/20`).
- Focus styles that are already solid: sidebar items, the skip link, `<main>`, inline links, menu and command items (these use a background change).
- Test files under `frontend/src` (#220).

## Decisions

### An outline, not a box-shadow ring

The utility draws `outline: 2px solid var(--ring)`. Alternatives: Tailwind's `ring-2 ring-ring`, which is a box-shadow.

- Box-shadows are removed in forced-colours mode; outlines stay. That is why Tailwind v4 replaced `outline-none` with `outline-hidden` for focus resets.
- The global `button`/`a` rule is already an outline. Using the same property means one look everywhere and no stacking.

### Width 2px, offset 2px outside or -2px inside

2px matches every solid indicator in the app and meets the WCAG 2.2 focus appearance area guideline. An outer offset of 2px leaves a gap of page colour between the control's border and the ring, so the ring is read against the surface, which the contrast check covers.

### Two utilities: `focus-ring` and `focus-ring-inset`

Defined with `@utility` in `frontend/src/styles/theme.css`, beside the other custom utilities. They carry no state, so callers pick the state with a variant: `focus-visible:focus-ring`, `has-focus-visible:focus-ring-inset`, `has-[[data-slot=input-group-control]:focus-visible]:focus-ring`.

- `focus-ring`: standalone controls. Inputs, textarea, native select, input group, buttons, badges, the sidebar wordmark link.
- `focus-ring-inset`: things inside a clipping or tight container. List rows (report list, problems list, follow-ups list, problem picker options) and segmented options (status chips, follow-ups tabs, theme and palette options).

Alternatives: one utility plus `outline-offset` per caller (spreads the offset rule across files and relies on utility order); a CSS custom property only (no variant support).

### The global rule moves to the base layer

`index.css` keeps a rule for focused `button` and `a`, but in `@layer base`, built with `@apply focus-ring`. It still covers every button and link with no class of its own. A component utility now wins over it, so `focus-ring-inset` on a link row works, and `outline-hidden` on sidebar items leaves their single `ring-2`.

Side effect, checked: these button or link elements carry `outline-none` or `outline-hidden` and would lose the global outline. Each keeps one solid indicator:
- `button.tsx`, status chips, follow-ups tabs, report and follow-ups rows, wordmark link: switched to `focus-ring` or `focus-ring-inset` here.
- Sidebar items and the skip link: their own solid `ring-2`.
The other `outline-none`/`outline-hidden` elements are not buttons or links (dialog content, command list and items, menu items, the triage heading).

### Buttons and badges drop `border-ring`

`focus-visible:border-ring` and the halo go. The destructive button's `focus-visible:border-destructive/40 focus-visible:ring-destructive/20` and the destructive badge's `focus-visible:ring-destructive/20` go too: with no ring width they draw nothing but a border tint. Focus on a destructive button uses the same `--ring` outline as every other control. The `aria-invalid` classes stay.

### `input-group.tsx`

Replace `border-ring`, `ring-3`, and `ring-ring/50` on the control-focus variant with `focus-ring`. Keep the `in-data-[slot=combobox-content]` overrides unchanged. Gate `transition-colors` with `motion-safe:` so focused input groups do not fade under reduced motion, as required by `web-interface/spec.md:349` and `:671`.

### Command inputs

`CommandInput` wraps `CommandPrimitive.Input` in an `InputGroup`. Its input uses `data-slot="command-input"` and keeps `outline-hidden`, so the generic input-group control selector does not match it. Add a command-input focus selector to this `InputGroup` and apply `focus-ring-inset`.

The command surface clips overflow. The command palette dialog also clips overflow. An inset outline stays inside the input group in both the member picker popover and the command palette dialog. `CommandInput` is shared, so both inputs use the same indicator.

### Checks

In `frontend/e2e/theme-tokens.spec.ts`:
- Hold `--ring` to 3:1 over the full `SURFACES` list. Inset rings sit on `--muted` (hover) and `--selected`; the wordmark link sits on `--sidebar`.
- On `/sign-in`, Tab to the email input and to the submit button. Assert each has a solid 2px outline whose painted colour equals the painted `--ring`, at full alpha. This is what ties the #203 token check to what is drawn.
- In the member picker and command palette, focus the command input in light and dark themes. Assert the input group draws one 2px inset outline in the fully opaque `--ring` colour.

### Spec

`skip_specs: true`. "Readable text in every palette" already requires 3:1 for the focus ring, and its scenario "every checked pair meets its contrast threshold" covers the wider check. No new behaviour.

## Risks / Trade-offs

- [The outer ring is 4px outside the control and can be cut by a parent with overflow] → Clipped places use `focus-ring-inset`. The implementer tabs through Inbox, Problems, Follow-ups, Settings, the member picker, and command palette in both themes and notes any cut ring.
- [Inputs change from a soft halo to a ring with a gap] → It is the same look as buttons now. Before and after shots cannot show focus; the PR says so.
- [A later shadcn registry update to `button.tsx` or `badge.tsx` brings the halo back] → The DESIGN.md Focus section names the rule, and the e2e check on the sign-in button fails if the button draws something else.
