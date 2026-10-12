# Tasks

## 1. Renderer

- [x] 1.1 From `frontend`, run `npm install react-markdown remark-gfm remark-breaks`. The diff to `package.json` is three added lines. `package-lock.json` changes no existing package's version
- [x] 1.2 Add `frontend/src/components/markdown/markdown.tsx` per design decisions 1 and 2, rendering plain defaults. A first test in `markdown.test.tsx` asserts a heading, a list, and a line break from a single newline
- [x] 1.3 Add the `urlTransform` and the `a` and `img` overrides per decisions 4 and 5. Tests cover: an `https` link has `target="_blank"` and `rel="noopener noreferrer"`; `mailto` is active; `javascript:`, `data:`, `irc:`, and a relative URL render text with no `a`; an image renders no `img` and a link named by its alt text; an image with empty alt is named by its URL
- [x] 1.4 Tests for raw HTML per decision 3: `<details>`, `<script>`, `<img onerror>`, and an HTML comment each show as literal text, and the container holds no `details`, `script`, or `img` element
- [x] 1.5 Add `headingOffset` per decision 6. Tests cover: default `#` is `h1`; with offset 4, `#` is `h5` and `###` is `h6`
- [x] 1.6 Style every element per decision 7. Tests cover: a table sits in a horizontally scrolling wrapper; a task list renders two disabled checkboxes named "Done" and "Not done"; `~~x~~` renders `del`
- [x] 1.7 Export the renderer through a lazy shared component. Show plain text while it loads and after a load failure; add fallback and error-boundary coverage.

## 2. Preview

- [x] 2.1 In `github-issue-create.tsx`, replace the body `p` with `Markdown` per decision 8 and add the note per decision 9. Leave the label, title, and marker line unchanged
- [x] 2.2 Update `github-issue-create.test.tsx`: the existing assertions pass unchanged; add a case where the body is `## Steps\n\n1. One\n2. Two\n\ncc @octocat, see #12` and assert a heading named "Steps", a list with two items, the mention text unchanged, the note, and the marker line
- [x] 2.3 Fix the preview mock in `frontend/e2e/github-issues.spec.ts` per decision 10. The existing test passes with its assertions unchanged
- [x] 2.4 Add an e2e test in `github-issues.spec.ts` with a body holding a heading, a task list, a table, a long unbroken code line, a link, an image, and raw HTML. Assert: at 390px `document.documentElement.scrollWidth` is at most `clientWidth`; the link has the new-tab attributes; no request goes to the image host; the raw HTML shows as text; `axeViolations` is empty in light and dark
- [x] 2.5 Add a "Markdown" section to `frontend/DESIGN.md` per decision 11. Do not reword existing text

## 3. Checks

- [x] 3.1 `npx @fission-ai/openspec validate --all --strict`
- [x] 3.2 `task check test build schema-check` with PostgreSQL and Redis running. Note the built JS size before and after
- [x] 3.3 `RESCRIBO_E2E_API_PORT=8208 RESCRIBO_E2E_FRONTEND_PORT=5208 task e2e`
- [x] 3.4 Take the after shots into `.claude/shots/after`: run `shots.mjs`, then `.claude/shots/preview-shots.mjs`, which mocks the preview reply because the demo refuses GitHub actions. Build `.claude/shots/compare.html`
- [x] 3.5 Write the PR body per the brief. Under Decisions to review, list the answers to the five plan questions, the link schemes allowed, and the bundle size change
- [x] 3.6 Correct the archived footnote behavior and add the renderer load-failure scenario to the spec.

## Workflow follow-up

- Archive the change in the PR that completes it.
- Other screens that show user text with `whitespace-pre-wrap` and could adopt the renderer in a later issue: `inbox/report-detail.tsx`, `inbox/provenance.tsx`, `problems/problem-detail-page.tsx`, `follow-ups/follow-up-detail.tsx`. Not changed here.
