# Tasks

## 1. Breadcrumb link

- [x] 1.1 Add a test to the "Reduced motion" describe in `frontend/e2e/motion.spec.ts`: go to `/inbox/new`, get the "Inbox" link inside the navigation named "Breadcrumb", focus it from the keyboard, and assert `transition-duration` is `0s` and `outline-style` is `solid`. Run it and verify it fails before the fix with a `0.15s` duration
- [x] 1.2 In `frontend/src/components/ui/breadcrumb.tsx`, change `transition-colors` on `BreadcrumbLink` to `motion-safe:transition-colors`; verify the test from 1.1 passes

## 2. Sidebar rail

- [x] 2.1 Add `frontend/src/components/ui/sidebar.test.tsx`: stub `matchMedia` as `app-shell.test.tsx` does (`useIsMobile` needs it), render `SidebarRail` inside `SidebarProvider`, and assert the button has `motion-safe:transition-all` and not `transition-all`; verify it fails before the fix
- [x] 2.2 In `frontend/src/components/ui/sidebar.tsx`, change `transition-all` on `SidebarRail` to `motion-safe:transition-all`; verify the test from 2.1 passes
- [x] 2.3 Search `frontend/src/components/ui/` for `transition`, `transition-all`, and `transition-colors` without `motion-safe:`; verify only `sheet.tsx` `SheetContent` remains, as design.md records

## 3. Checks

- [x] 3.1 Run `task check test build schema-check` with PostgreSQL and Redis running; all pass
- [x] 3.2 Run `RESCRIBO_E2E_API_PORT=8239 RESCRIBO_E2E_FRONTEND_PORT=5239 task e2e`; all pass
- [x] 3.3 Run `npx @fission-ai/openspec validate --all --strict`; passes
- [x] 3.4 In the PR, list the gated elements, say that no still screenshot changes so there are no before or after shots, and say why `SheetContent` was left

## Workflow follow-up

- Archive the change in the PR that completes it.
