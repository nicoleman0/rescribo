# Proposal

Delivers GitHub issue #199, Add a command palette (milestone H. Product-grade UI).

## Why

`frontend/DESIGN.md` calls the app keyboard-first, but a member can only move between screens through the sidebar, and can only find a report or a problem through each page's own search. The reworked shell (#198) left a place in the header for a palette trigger.

## What Changes

- A command palette opens from a header trigger and from Cmd+K or Ctrl+K on every signed-in product screen.
- The palette goes to a screen, finds a report or a problem in the member's workspace, and changes the theme.
- The palette lists the app's keyboard shortcuts with their keys.
- Keyboard shortcuts are declared in one registry. The sidebar toggle (Cmd+B, Ctrl+B) moves into it and keeps working as before.
- The shadcn `Command` and `Dialog` primitives are added to `frontend/src/components/ui/` and styled from the theme tokens. #200 reuses `Command`.
- No backend or API change. Search uses the existing report and problem list endpoints with `q`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds requirements for the command palette, its screen, search, and theme commands, the shortcut list, and its keyboard and phone use. No existing requirement changes.

## Impact

- New: `frontend/src/components/ui/command.tsx`, `dialog.tsx`, `input-group.tsx`; `frontend/src/components/command-palette/`; `frontend/src/lib/shortcuts.ts`; `frontend/src/components/layout/navigation-items.ts`; `frontend/e2e/command-palette.spec.ts`.
- Changed: `frontend/src/components/layout/app-shell.tsx` (trigger, palette, sidebar shortcut), `frontend/src/components/ui/sidebar.tsx` (its key handler is removed), `frontend/src/dev/ui-gallery.tsx`, `frontend/DESIGN.md` (one new section).
- Dependency: `cmdk`, added by the shadcn CLI. `frontend/package.json` and `frontend/package-lock.json` also change in #208, so only this line is added.
- API: none. The OpenAPI contract does not change.
