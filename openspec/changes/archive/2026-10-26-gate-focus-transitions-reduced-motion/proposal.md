# Proposal

## Why

Issue #239. Two focus targets in `frontend/src/components/ui/` have colour or all-property transitions that run under reduced motion. In Tailwind 4 both cover `outline-color`, so the focus outline fades in for members who asked for reduced motion. The `web-interface` requirement "Reduced motion" already forbids animated transitions in that mode, so the code diverges from the spec.

## What Changes

- `breadcrumb.tsx` `BreadcrumbLink`: `transition-colors` becomes `motion-safe:transition-colors`.
- `sidebar.tsx` `SidebarRail`: `transition-all` becomes `motion-safe:transition-all`.
- A sweep of every other `transition`, `transition-all`, and `transition-colors` in `frontend/src/components/ui/` found no other focus target that needs the gate. Details in design.md.
- A reduced-motion e2e test proves the breadcrumb link has no transition, and a unit test pins the rail's class.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change brings code in line with the existing "Reduced motion" requirement in `openspec/specs/web-interface/spec.md`, so the change sets `skip_specs: true`.

## Impact

- `frontend/src/components/ui/breadcrumb.tsx`, `frontend/src/components/ui/sidebar.tsx`.
- `frontend/e2e/motion.spec.ts` and a new `frontend/src/components/ui/sidebar.test.tsx`.
- Visible only as the absence of a 150 ms fade on focus and hover under reduced motion. No still screenshot changes, so no before or after shots.
