# Proposal

## Why

The GitHub issue draft shows its body under "Exact preview" as plain text. GitHub renders the body as Markdown, so a draft with a heading, a list, or a link looks different once published. Delivers #208.

## What Changes

- The preview renders the issue body as GitHub-flavoured Markdown: headings, emphasis, lists, task lists, tables, code, block quotes, and links.
- A single newline in the body shows as a line break, as it does in a GitHub issue.
- Raw HTML in the body shows as literal text. It is never rendered.
- Links open in a new tab. Only `http`, `https`, and `mailto` links are active.
- Images are not loaded. An image shows as a link with its alt text.
- The label stays "Exact preview". One line under it names what only GitHub adds: links for @mentions and #references, and a notification to each mentioned user.
- The operation marker stays a separate visible line.

## Capabilities

### New Capabilities

### Modified Capabilities
- `engineering-issues`: adds the Markdown rendering of the create preview

## Impact

- Frontend: new `frontend/src/components/markdown/` (renderer and its test), `github-issue-create.tsx` and its test, `frontend/e2e/github-issues.spec.ts`.
- Dependencies: `react-markdown`, `remark-gfm`, `remark-breaks` in `frontend/package.json` and `package-lock.json`. Nothing else is upgraded.
- Shared file, pending approval: one new "Markdown" section in `frontend/DESIGN.md`.
- No backend change, no API change, no migration.
